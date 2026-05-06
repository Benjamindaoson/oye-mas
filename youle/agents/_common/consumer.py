"""Redis Streams 消费循环 — 4 个 Agent 共用入口。

加固清单(铁律 12:失败 3 层兜底):
- **重试**:同一 msg_id 失败 ≤ MAX_RETRIES 次 → 退避后重新派给本 consumer
- **DLQ**:超过 MAX_RETRIES → 写 `agent_dlq:<agent_id>` 并 ack 原消息
- **超时取消**:每个 handler 包 `asyncio.wait_for(timeout=task.timeout_seconds)`
- **心跳**:常驻协程每 HEARTBEAT_INTERVAL 秒 set_status(working/idle)
- **优雅停机**:SIGTERM/SIGINT → 先停止读队列 → 等当前任务结束 → 退出
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
import structlog

from agents._common.boundary import assert_task_in_boundary
from agents._common.protocol import QUEUE_MAP, AgentId, AgentResult, AgentTask

log = structlog.get_logger(__name__)

HandlerType = Callable[[AgentTask], Awaitable[AgentResult]]

MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "2"))   # 重试 2 次,合计 3 次尝试
RETRY_BASE_SLEEP = float(os.getenv("AGENT_RETRY_BASE_SLEEP", "1.0"))
HEARTBEAT_INTERVAL = float(os.getenv("AGENT_HEARTBEAT_INTERVAL", "20"))


class AgentConsumer:
    def __init__(
        self,
        *,
        agent_id: AgentId,
        handlers: dict[str, HandlerType],
        consumer_name: str | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.handlers = handlers
        self.queue = QUEUE_MAP[agent_id]
        self.consumer_name = consumer_name or f"{agent_id}-{os.getpid()}"
        self.group = f"{agent_id}-group"
        self._redis: aioredis.Redis | None = None
        self._stop = asyncio.Event()
        self._inflight: int = 0
        self._last_user_id: UUID | None = None
        self._busy: bool = False

    async def _r(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
            )
            try:
                await self._redis.xgroup_create(self.queue, self.group, id="$", mkstream=True)
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
        return self._redis

    # ── 信号处理 ──
    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, self._stop.set)
            except NotImplementedError:
                # Windows 不支持 add_signal_handler — 静默跳过
                pass

    # ── 主循环 ──
    async def start(self) -> None:
        log.info("agent.consumer.start", agent_id=self.agent_id, queue=self.queue)
        self._install_signals()
        redis = await self._r()

        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        try:
            while not self._stop.is_set():
                try:
                    resp = await redis.xreadgroup(
                        self.group,
                        self.consumer_name,
                        streams={self.queue: ">"},
                        count=1,
                        block=5000,
                    )
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log.warning("agent.consumer.read_error", err=str(e))
                    await asyncio.sleep(1)
                    continue
                if not resp:
                    continue
                for _stream, messages in resp:
                    for msg_id, fields in messages:
                        await self._dispatch(redis, msg_id, fields)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except (asyncio.CancelledError, Exception):
                pass
            log.info("agent.consumer.stopped", agent_id=self.agent_id)

    async def _heartbeat_loop(self) -> None:
        """每 HEARTBEAT_INTERVAL 秒上报一次 Agent 状态(working/idle)。"""
        redis = await self._r()
        while not self._stop.is_set():
            try:
                payload = {
                    "agent_id": self.agent_id,
                    "status": "working" if self._busy else "idle",
                    "ts": datetime.now(UTC).isoformat(),
                    "consumer": self.consumer_name,
                    "user_id": str(self._last_user_id) if self._last_user_id else "",
                }
                await redis.xadd(
                    "agent_heartbeats",
                    payload,
                    maxlen=1000,
                    approximate=True,
                )
            except Exception as e:
                log.warning("agent.heartbeat.failed", err=str(e))
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                continue

    # ── 单条消息派发 ──
    async def _dispatch(
        self, redis: aioredis.Redis, msg_id: str, fields: dict[str, Any]
    ) -> None:
        attempt = int(fields.get("_attempt", 0) or 0)
        try:
            payload = json.loads(fields.get("data", "{}"))
            task = AgentTask.model_validate(payload)
            assert_task_in_boundary(self.agent_id, task)
            handler = self.handlers.get(task.task_type)
            if handler is None:
                raise ValueError(f"no handler for task_type={task.task_type}")

            self._busy = True
            self._last_user_id = task.user_id
            self._inflight += 1
            t0 = time.monotonic()
            try:
                # 铁律 12 失败 3 层兜底之第 1 层:超时
                result = await asyncio.wait_for(
                    handler(task),
                    timeout=max(10, task.timeout_seconds),
                )
            finally:
                self._busy = False
                self._inflight -= 1
            result.duration_ms = int((time.monotonic() - t0) * 1000)
            await redis.xadd(
                f"agent_results:{task.task_id}",
                {"data": result.model_dump_json()},
            )
            await redis.xack(self.queue, self.group, msg_id)
            log.info(
                "agent.consumer.completed",
                agent_id=self.agent_id,
                task_id=str(task.task_id),
                step_id=task.step_id,
                status=result.status,
                duration_ms=result.duration_ms,
            )
        except asyncio.TimeoutError:
            await self._retry_or_dlq(
                redis, msg_id, fields, attempt, error="timeout"
            )
        except Exception as e:
            log.exception(
                "agent.consumer.dispatch_error",
                err=str(e),
                attempt=attempt,
                msg_id=msg_id,
            )
            await self._retry_or_dlq(redis, msg_id, fields, attempt, error=str(e))

    async def _retry_or_dlq(
        self,
        redis: aioredis.Redis,
        msg_id: str,
        fields: dict[str, Any],
        attempt: int,
        *,
        error: str,
    ) -> None:
        """重试 ≤ MAX_RETRIES,否则进 DLQ 并 ack 原消息。"""
        if attempt < MAX_RETRIES:
            delay = RETRY_BASE_SLEEP * (2 ** attempt)
            new_fields = dict(fields)
            new_fields["_attempt"] = str(attempt + 1)
            new_fields["_last_error"] = error[:500]
            try:
                # 退避 + 重新入队(ack 原消息以释放 PEL)
                await asyncio.sleep(delay)
                await redis.xadd(self.queue, new_fields)
                await redis.xack(self.queue, self.group, msg_id)
                log.info(
                    "agent.consumer.retried",
                    agent_id=self.agent_id,
                    msg_id=msg_id,
                    attempt=attempt + 1,
                    delay=delay,
                )
            except Exception as e:
                log.warning("agent.consumer.retry_failed", err=str(e))
            return

        # 超出重试 → DLQ
        try:
            payload = fields.get("data", "{}")
            try:
                task_obj = json.loads(payload)
                task_id = task_obj.get("task_id")
                step_id = task_obj.get("step_id")
            except Exception:
                task_id = step_id = None
            await redis.xadd(
                f"agent_dlq:{self.agent_id}",
                {
                    "msg_id": msg_id,
                    "data": payload,
                    "error": error[:500],
                    "attempts": str(attempt + 1),
                    "ts": datetime.now(UTC).isoformat(),
                },
            )
            # 同时通知 runner:把该 step 标 failed,触发 Reflexion(由 runner 拉 task_id 失败回执)
            if task_id and step_id:
                fail_result = AgentResult(
                    task_id=UUID(task_id),
                    step_id=step_id,
                    status="failed",
                    error_detail={
                        "type": "max_retries_exceeded",
                        "attempts": attempt + 1,
                        "error": error[:500],
                    },
                )
                await redis.xadd(
                    f"agent_results:{task_id}",
                    {"data": fail_result.model_dump_json()},
                )
            await redis.xack(self.queue, self.group, msg_id)
            log.error(
                "agent.consumer.dlq",
                agent_id=self.agent_id,
                msg_id=msg_id,
                attempts=attempt + 1,
                error=error,
            )
        except Exception as e:
            log.warning("agent.consumer.dlq_write_failed", err=str(e))

    def stop(self) -> None:
        self._stop.set()
