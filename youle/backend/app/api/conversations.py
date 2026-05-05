"""会话 API(v3.0 ADR-014:三模式同群切换)。

注意:`derive-work-group` / `back-to-discuss` 已废弃,改用 `switch-work-mode`(铁律 17)。
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.db import get_session
from app.models.conversation import Conversation
from app.models.mode_switch_log import ModeSwitchLog
from app.schemas.ws import WSEventType

router = APIRouter()


WorkMode = Literal["plan", "ask", "auto"]
ConversationMode = Literal["main_session", "group", "private_chat"]


class ConversationCreate(BaseModel):
    mode: ConversationMode = "group"
    work_mode: WorkMode | None = None
    skill_id: UUID | None = None
    name: str | None = None


class ConversationOut(BaseModel):
    id: UUID
    name: str
    mode: ConversationMode
    work_mode: WorkMode | None
    status: str

    class Config:
        from_attributes = True


class SwitchWorkModeRequest(BaseModel):
    target: WorkMode
    triggered_by: Literal["user", "orchestrator"] = "user"


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[Conversation]:
    rows = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.last_message_at.desc().nulls_last())
    )
    return list(rows.scalars().all())


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    conv = Conversation(
        user_id=user_id,
        name=body.name or "新会话",
        mode=body.mode,
        work_mode=body.work_mode,
        skill_id=body.skill_id,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    return conv


@router.post("/{conversation_id}/switch-work-mode")
async def switch_work_mode(
    conversation_id: UUID,
    body: SwitchWorkModeRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    """v3.0 ADR-014:同群切换 plan/ask/auto。"""
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    if conv.mode != "group":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅群会话支持模式切换")

    from_mode = conv.work_mode
    conv.work_mode = body.target
    session.add(
        ModeSwitchLog(
            conversation_id=conv.id,
            from_mode=from_mode,
            to_mode=body.target,
            triggered_by=body.triggered_by,
        )
    )
    await session.commit()

    return {
        "conversation": ConversationOut.model_validate(conv).model_dump(),
        "ws_event": {
            "type": WSEventType.WORK_MODE_CHANGED,
            "conversation_id": str(conv.id),
            "from": from_mode,
            "to": body.target,
        },
    }
