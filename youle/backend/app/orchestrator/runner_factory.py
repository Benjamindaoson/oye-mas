"""Runner 工厂 — 按 settings.USE_LANGGRAPH_RUNNER 切 TaskRunner / LangGraphTaskRunner。

调用方(api/tasks.py / api/messages.py / result_consumer.py)统一用本工厂拿 runner,
不直接 import 具体类。这样 V1.5 切换 LangGraph 不需要改任何调用点。

接口契约(两 runner 共同子集):
  - start(task_id) → 启动任务
  - resolve_hitl(task_id, gate_id, decision) → HITL 决议后续(LangGraph 用 resume)
  - handle_result(result) → Agent 回执推进(仅 TaskRunner;LangGraph 自己等 stream)

LangGraph runner 额外支持:
  - rollback_to_step(task_id, target_step_id, instruction)  ← V2 中断 C/D
  - get_state(task_id)
  - get_history(task_id) iter
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

log = structlog.get_logger(__name__)


class RunnerProtocol(Protocol):
    async def start(self, task_id: UUID) -> Any: ...


def make_runner(
    session: AsyncSession, *, dispatcher=None, publisher=None
) -> Any:
    """主入口。dev / staging 默认走 TaskRunner;开 USE_LANGGRAPH_RUNNER 切 LangGraph。"""
    if settings.USE_LANGGRAPH_RUNNER:
        from app.orchestrator.langgraph_runner import LangGraphTaskRunner

        return LangGraphTaskRunner(session, dispatcher=dispatcher, publisher=publisher)

    from app.orchestrator.runner import TaskRunner

    return TaskRunner(session, dispatcher=dispatcher, publisher=publisher)


def is_langgraph_active() -> bool:
    return settings.USE_LANGGRAPH_RUNNER
