"""Agent 回执消费 reaper(后台任务)。

监听 Redis Streams `agent_results:*`,把回执喂给 TaskRunner.handle_result。
启动:由 main.py lifespan 注册为 asyncio.Task。
关停:set self._stop=True,wait task。

设计:
- 用 KEYS 扫一次活跃 stream(简单粗暴,V1 够用;V2 改用 keyspace notifications 或一个统一的 stream)
- 每个 task_id 维护 last_id,从那以后读
- 任务结束(completed/failed/cancelled)清理对应 last_id
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import SessionLocal
from app.orchestrator.runner import TaskRunner
from app.redis_client import get_redis
from app.schemas.agent import AgentResult

log = structlog.get_logger(__name__)


class ResultConsumer:
    def __init__(self, *, session_factory: async_sessionmaker | None = None) -> None:
        self._session_factory = session_factory or SessionLocal
        self._stop = False
        self._task: asyncio.Task[None] | None = None
        self._last_ids: dict[str, str] = {}

    def start(self) -> None:
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())
        log.info("result_consumer.started")

    async def stop(self) -> None:
        self._stop = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
            log.info("result_consumer.stopped")

    async def _loop(self) -> None:
        redis = await get_redis()
        while not self._stop:
            try:
                # 扫当前活跃的 result streams(KEYS 在 dev 规模下 OK;prod 切 SCAN)
                keys = await redis.keys("agent_results:*")
                if not keys:
                    await asyncio.sleep(2)
                    continue
                streams = {k: self._last_ids.get(k, "0") for k in keys}
                resp = await redis.xread(streams, block=2000, count=10)
                if not resp:
                    continue
                for stream, messages in resp:
                    for msg_id, fields in messages:
                        self._last_ids[stream] = msg_id
                        await self._handle_one(fields)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("result_consumer.loop_error", err=str(e))
                await asyncio.sleep(1)

    async def _handle_one(self, fields: dict[str, Any]) -> None:
        try:
            data = fields.get("data", "{}")
            result = AgentResult.model_validate_json(data)
        except Exception as e:
            log.warning("result_consumer.parse_failed", err=str(e), data=str(fields)[:200])
            return

        async with self._session_factory() as session:
            runner = TaskRunner(session)
            try:
                await runner.handle_result(result)
            except Exception as e:
                log.exception("result_consumer.handle_failed", task_id=str(result.task_id), err=str(e))


result_consumer = ResultConsumer()
