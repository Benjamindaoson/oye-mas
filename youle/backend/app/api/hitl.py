"""HITL gate API(ADR-010)— 接 TaskRunner.resolve_hitl 真正推进/重派/取消。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.hitl_gate import HITLGate
from app.orchestrator.runner_factory import make_runner

router = APIRouter()


class HITLGateOut(BaseModel):
    id: UUID
    task_id: UUID
    step_id: str
    gate_type: str
    resolution: str | None

    class Config:
        from_attributes = True


class ApproveBody(BaseModel):
    user_choice: dict[str, Any] | None = None


class ModifyBody(BaseModel):
    target_step: str
    parameters: dict[str, Any] | None = None


class CancelBody(BaseModel):
    reason: str | None = None


@router.get("/{task_id}/hitl_gates", response_model=list[HITLGateOut])
async def list_gates(
    task_id: UUID, session: AsyncSession = Depends(get_session)
) -> list[HITLGate]:
    rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
    return list(rows.scalars().all())


@router.post("/{task_id}/hitl_gates/{gate_id}/approve")
async def approve_gate(
    task_id: UUID,
    gate_id: UUID,
    body: ApproveBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    runner = make_runner(session)
    dispatched = await runner.resolve_hitl(
        gate_id, resolution="approved", user_choice=body.user_choice
    )
    return {"status": "approved", "dispatched_next": dispatched}


@router.post("/{task_id}/hitl_gates/{gate_id}/modify")
async def modify_gate(
    task_id: UUID,
    gate_id: UUID,
    body: ModifyBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    runner = make_runner(session)
    dispatched = await runner.resolve_hitl(
        gate_id,
        resolution="modified",
        user_choice={"target_step": body.target_step, "parameters": body.parameters or {}},
    )
    return {"status": "modified", "redispatched": dispatched}


@router.post("/{task_id}/hitl_gates/{gate_id}/cancel")
async def cancel_gate(
    task_id: UUID,
    gate_id: UUID,
    body: CancelBody,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    runner = make_runner(session)
    await runner.resolve_hitl(
        gate_id, resolution="cancelled", user_choice={"reason": body.reason}
    )
    return {"status": "cancelled"}


@router.post("/{task_id}/hitl_gates/{gate_id}/rollback")
async def rollback_gate(task_id: UUID, gate_id: UUID) -> dict[str, str]:
    """V1 不实现(中断 C 是 V2,铁律 14)。"""
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED,
        "回滚到第 N 步(中断 C)推迟到 V2,V1 仅支持 接受/微调/取消",
    )
