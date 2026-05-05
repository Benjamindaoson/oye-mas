"""Brief 构建器(铁律 6:5 秒静默 + 累计 3 条触发)。"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID

import structlog

from app.orchestrator.mode_manager import update_brief

log = structlog.get_logger(__name__)


class BriefDebouncer:
    """对每个 conversation_id 做防抖批量更新。"""

    def __init__(self, *, silence_seconds: float = 5.0, batch_size: int = 3) -> None:
        self._buffers: dict[UUID, list[dict[str, str]]] = defaultdict(list)
        self._timers: dict[UUID, asyncio.Task[None]] = {}
        self._briefs: dict[UUID, dict[str, Any]] = {}
        self._silence = silence_seconds
        self._batch = batch_size
        self._lock = asyncio.Lock()

    async def push(self, conversation_id: UUID, message: dict[str, str]) -> None:
        async with self._lock:
            self._buffers[conversation_id].append(message)
            if len(self._buffers[conversation_id]) >= self._batch:
                await self._flush(conversation_id)
                return
            if conversation_id in self._timers:
                self._timers[conversation_id].cancel()
            self._timers[conversation_id] = asyncio.create_task(
                self._delayed_flush(conversation_id)
            )

    async def _delayed_flush(self, conversation_id: UUID) -> None:
        try:
            await asyncio.sleep(self._silence)
            async with self._lock:
                await self._flush(conversation_id)
        except asyncio.CancelledError:
            pass

    async def _flush(self, conversation_id: UUID) -> None:
        msgs = self._buffers.pop(conversation_id, [])
        self._timers.pop(conversation_id, None)
        if not msgs:
            return
        current = self._briefs.get(conversation_id, {"完成度": 0.0, "字段": {}, "决策日志": []})
        try:
            self._briefs[conversation_id] = await update_brief(
                current_brief=current, new_messages=msgs
            )
            log.debug("brief.flushed", conversation_id=str(conversation_id), msg_count=len(msgs))
        except Exception as e:
            log.warning("brief.flush_failed", err=str(e))


brief_debouncer = BriefDebouncer()
