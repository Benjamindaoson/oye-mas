"""数据飞轮服务(ADR-011 4 类信号沉淀必做)。

任务完成路径必须 emit 4 类信号:
  1. 工作流完整轨迹 → Postgres workflow_traces + Qdrant
  2. 用户偏好向量 → user_preferences.preference_vec
  3. 失败 → Reflexion → prompt_improvement_candidates
  4. 高满意度 → Skill 草稿 → skill_drafts
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workflow_trace import WorkflowTrace

log = structlog.get_logger(__name__)


class FlywheelService:
    @staticmethod
    async def emit_trace(
        session: AsyncSession,
        *,
        task_id: UUID,
        user_id: UUID,
        skill_id: UUID | None,
        skill_version: str | None,
        duration_ms: int | None,
        cost_usd: Decimal | None,
        user_satisfaction: int | None = None,
        failure_reason: str | None = None,
        rollback_count: int = 0,
        trace_oss_ref: str | None = None,
        qdrant_point_id: str | None = None,
    ) -> None:
        trace = WorkflowTrace(
            task_id=task_id,
            user_id=user_id,
            skill_id=skill_id,
            skill_version=skill_version,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
            user_satisfaction=user_satisfaction,
            failure_reason=failure_reason,
            rollback_count=rollback_count,
            trace_oss_ref=trace_oss_ref,
            qdrant_point_id=qdrant_point_id,
        )
        session.add(trace)
        await session.commit()
        log.debug("flywheel.trace.emit", task_id=str(task_id))

    @staticmethod
    async def emit_preference_update(
        session: AsyncSession,
        *,
        user_id: UUID,
        signal: dict[str, Any],
    ) -> None:
        # TODO(flywheel-pref): 接 BGE-base-zh embedding,合并到 256 维向量
        log.debug("flywheel.preference.emit", user_id=str(user_id), signal_keys=list(signal))

    @staticmethod
    async def emit_reflexion_candidate(
        session: AsyncSession,
        *,
        task_id: UUID,
        prompt_name: str,
        root_cause: str,
        section_to_improve: str,
        proposed_changes: list[dict[str, Any]],
    ) -> None:
        # TODO(flywheel-reflexion): pipeline 实现,先记录信号
        log.info(
            "flywheel.reflexion.candidate",
            task_id=str(task_id),
            prompt_name=prompt_name,
        )

    @staticmethod
    async def emit_skill_draft(
        session: AsyncSession,
        *,
        user_id: UUID,
        task_id: UUID,
        draft_yaml: str,
    ) -> None:
        # TODO(flywheel-draft): V1.5 创作者飞轮
        log.info("flywheel.skill_draft.emit", user_id=str(user_id), task_id=str(task_id))


flywheel = FlywheelService()
