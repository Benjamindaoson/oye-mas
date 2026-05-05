"""Redis Streams 消费循环 — 4 个 Agent 共用入口。

每个 Agent main.py 实例化 Consumer,注册自身的 task_handlers dict。
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
import structlog

from agents._common.boundary import assert_task_in_boundary
from agents._common.protocol import QUEUE_MAP, AgentId, AgentResult, AgentTask

log = structlog.get_logger(__name__)

HandlerType = Callable[[AgentTask], Awaitable[AgentResult]]


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
        self._stop = False

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

    async def start(self) -> None:
        log.info("agent.consumer.start", agent_id=self.agent_id, queue=self.queue)
        redis = await self._r()
        while not self._stop:
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

    async def _dispatch(
        self, redis: aioredis.Redis, msg_id: str, fields: dict[str, Any]
    ) -> None:
        try:
            payload = json.loads(fields.get("data", "{}"))
            task = AgentTask.model_validate(payload)
            assert_task_in_boundary(self.agent_id, task)
            handler = self.handlers.get(task.task_type)
            if handler is None:
                raise ValueError(f"no handler for task_type={task.task_type}")
            t0 = time.monotonic()
            result = await handler(task)
            result.duration_ms = int((time.monotonic() - t0) * 1000)
            await redis.xadd(
                f"agent_results:{task.task_id}",
                {"data": result.model_dump_json()},
            )
            await redis.xack(self.queue, self.group, msg_id)
        except Exception as e:
            log.exception("agent.consumer.dispatch_error", err=str(e))
            try:
                await redis.xadd(
                    f"agent_results:error",
                    {"msg_id": msg_id, "error": str(e)},
                )
                await redis.xack(self.queue, self.group, msg_id)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop = True
