"""数据飞轮 API(ADR-011 4 类信号)。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.skill_draft import SkillDraft
from app.models.user_preference import UserPreference

router = APIRouter()


@router.get("/users/{user_id}/preference_vector")
async def get_preference_vector(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    pref = await session.get(UserPreference, user_id)
    if pref is None:
        return {"preferences": {}, "preference_vec": None}
    return {
        "preferences": pref.preferences,
        "preference_vec": list(pref.preference_vec) if pref.preference_vec is not None else None,
    }


@router.get("/users/{user_id}/skill_drafts")
async def list_skill_drafts(
    user_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, object]]:
    rows = await session.execute(select(SkillDraft).where(SkillDraft.user_id == user_id))
    return [
        {"id": str(r.id), "name": r.name, "status": r.status, "created_at": r.created_at.isoformat()}
        for r in rows.scalars().all()
    ]


@router.post("/skill_drafts/{draft_id}/publish")
async def publish_skill_draft(draft_id: UUID) -> dict[str, str]:
    """V1.5 创作者飞轮 — V1 留接口不实现。"""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Skill 创作市场是 V1.5 范围")
