"""Runner 工厂 — 默认 LangGraph 单轨。

V1 自写 TaskRunner 仅作为兼容兜底(单测继续用),prod 全部走 LangGraph:
- 任务编排 → StateGraph + 节点 + Send fan-out
- 状态持久化 → AsyncPostgresSaver
- HITL 暂停/恢复 → interrupt() + Command(resume=...)
- WS streaming → astream_events v2
- Time travel(V2 中断 C/D)→ aget_state_history + aupdate_state

调用方(api/tasks.py / api/messages.py / api/hitl.py / result_consumer.py)
统一用本工厂拿 runner,不直接 import 具体类。

接口契约:
  - start(task_id)            启动任务
  - resume(task_id, decision) HITL 决议后续(LangGraph 原生 Command)
  - resolve_hitl(...)         兼容旧 API,内部转 resume
  - rollback_to_step(...)     V2 中断 C/D
  - get_state(task_id)        读当前 state
  - get_history(task_id)      checkpoint 历史
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
    """主入口 — 默认返回 LangGraphTaskRunner。

    `USE_LANGGRAPH_RUNNER=False` 仅用于:
    - 单测里需要测 V1 自写 TaskRunner 行为(test_runner_scheduler 等)
    - 紧急回滚兜底(prod 不应走到这条分支)
    """
    if settings.USE_LANGGRAPH_RUNNER:
        from app.orchestrator.langgraph_runner import LangGraphTaskRunner

        return LangGraphTaskRunner(session, dispatcher=dispatcher, publisher=publisher)

    log.warning("runner.legacy_taskrunner_active", reason="USE_LANGGRAPH_RUNNER=false")
    from app.orchestrator.runner import TaskRunner

    return TaskRunner(session, dispatcher=dispatcher, publisher=publisher)


def is_langgraph_active() -> bool:
    return settings.USE_LANGGRAPH_RUNNER
