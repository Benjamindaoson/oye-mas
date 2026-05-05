"""Skill 浏览 + 订阅 API(v4 §32 AI 学院 / §33 技能市场)。"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user_id
from app.db import get_session
from app.models.skill import Skill, UserSkillVisibility

router = APIRouter()
log = structlog.get_logger(__name__)


class SkillCard(BaseModel):
    id: UUID
    skill_id: str
    name: str
    description: str | None = None
    domain: str | None = None
    scenario: str | None = None
    version: str
    creator_type: str
    visibility: str
    keywords: list[str] = []
    subscribed: bool = False

    model_config = {"from_attributes": True}


@router.get("/skills", response_model=list[SkillCard])
async def list_skills(
    domain: str | None = None,
    scenario: str | None = None,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    stmt = select(Skill).where(Skill.status == "published", Skill.visibility == "public")
    if domain:
        stmt = stmt.where(Skill.domain == domain)
    if scenario:
        stmt = stmt.where(Skill.scenario == scenario)
    skills = list((await session.execute(stmt)).scalars().all())

    sub_rows = (
        await session.execute(
            select(UserSkillVisibility.skill_id).where(
                UserSkillVisibility.user_id == user_id,
                UserSkillVisibility.relationship == "subscribed",
            )
        )
    ).scalars().all()
    sub_set = {sk for sk in sub_rows}

    return [
        {
            "id": s.id,
            "skill_id": s.skill_id,
            "name": s.name,
            "description": s.description,
            "domain": s.domain,
            "scenario": s.scenario,
            "version": s.version,
            "creator_type": s.creator_type,
            "visibility": s.visibility,
            "keywords": list(s.keywords or []),
            "subscribed": s.id in sub_set,
        }
        for s in skills
    ]


@router.get("/skills/mine", response_model=list[SkillCard])
async def my_skills(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """已订阅 + 平台预置(免订阅可见)。"""
    rows = (
        await session.execute(
            select(Skill)
            .join(UserSkillVisibility, UserSkillVisibility.skill_id == Skill.id, isouter=True)
            .where(
                (UserSkillVisibility.user_id == user_id)
                | ((Skill.creator_type == "platform") & (Skill.visibility == "public"))
            )
            .distinct()
        )
    ).scalars().all()
    return [
        {
            "id": s.id,
            "skill_id": s.skill_id,
            "name": s.name,
            "description": s.description,
            "domain": s.domain,
            "scenario": s.scenario,
            "version": s.version,
            "creator_type": s.creator_type,
            "visibility": s.visibility,
            "keywords": list(s.keywords or []),
            "subscribed": True,
        }
        for s in rows
    ]


@router.post("/skills/{skill_id}/subscribe")
async def subscribe(
    skill_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    skill = await session.get(Skill, skill_id)
    if skill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Skill 不存在")
    stmt = (
        pg_insert(UserSkillVisibility)
        .values(user_id=user_id, skill_id=skill_id, relationship="subscribed")
        .on_conflict_do_nothing(index_elements=["user_id", "skill_id"])
    )
    await session.execute(stmt)
    await session.commit()
    return {"skill_id": str(skill_id), "status": "subscribed"}


@router.delete("/skills/{skill_id}/subscribe", status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    skill_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> None:
    row = (
        await session.execute(
            select(UserSkillVisibility).where(
                UserSkillVisibility.user_id == user_id,
                UserSkillVisibility.skill_id == skill_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    await session.delete(row)
    await session.commit()
