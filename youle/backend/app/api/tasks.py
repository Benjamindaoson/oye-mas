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
    return {"status": "accepted"}


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
