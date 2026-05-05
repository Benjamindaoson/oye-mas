"""任务 API。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.task import Task
from app.orchestrator.interrupt import (
    InterruptClassification,
    V1_CLASSES,
    handle_interrupt,
)

router = APIRouter()


class TaskOut(BaseModel):
    id: UUID
    status: str
    skill_id: UUID | None
    progress: dict[str, Any]

    class Config:
        from_attributes = True


class AnswerClarificationRequest(BaseModel):
    clarification_id: str
    field: str
    value: Any


class InterruptRequest(BaseModel):
    interrupt_class: str  # A/B/C/D/E/F/G/H/I
    payload: dict[str, Any] | None = None


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: UUID, session: AsyncSession = Depends(get_session)) -> Task:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return task


@router.post("/{task_id}/answer-clarification")
async def answer_clarification(
    task_id: UUID,
    body: AnswerClarificationRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    fields = dict(task.collected_fields or {})
    fields[body.field] = body.value
    task.collected_fields = fields
    await session.commit()

    # 飞轮信号 2:聚合用户偏好(连续 3 次同选自动套用)
    from app.services.flywheel import flywheel

    await flywheel.emit_preference_update(
        session, user_id=task.user_id, fields={body.field: body.value}
    )
    return {"status": "accepted"}


class ConflictResolutionRequest(BaseModel):
    action: str  # queue / cancel_current / new_group


@router.post("/{task_id}/resolve-conflict")
async def resolve_conflict(
    task_id: UUID,
    body: ConflictResolutionRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """一群一任务冲突解决(v4 #231)。"""
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    if body.action == "cancel_current":
        from datetime import UTC, datetime

        task.status = "cancelled"
        task.cancelled_at = datetime.now(UTC)
        await session.commit()
        return {"status": "cancelled", "next": "send_message_again"}
    if body.action == "queue":
        # 简化:仅标记 hint;真排队由 runner 在当前完成后扫描 conversation 内 pending
        return {"status": "queued"}
    if body.action == "new_group":
        return {"status": "client_navigate", "next": "create_new_group"}
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"未知操作:{body.action}")


@router.post("/{task_id}/interrupt")
async def interrupt_task(
    task_id: UUID,
    body: InterruptRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    task = await session.get(Task, task_id)
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    if body.interrupt_class not in V1_CLASSES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"V1 不支持中断 {body.interrupt_class}(C/D 推迟 V2)",
        )
    classification = InterruptClassification(
        interrupt_class=body.interrupt_class,  # type: ignore[arg-type]
        reason=(body.payload or {}).get("reason", ""),
    )
    action = await handle_interrupt(
        classification, task_state={"task_id": str(task_id), **(body.payload or {})}
    )
    return {"status": "received", "interrupt_class": body.interrupt_class, "action": action}
