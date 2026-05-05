"""子模块 2:Skill 匹配器(三层检索)。

L1 关键词(SQL+jieba)→ L2 向量(pgvector + BGE-M3)→ L3 LLM 兜底(99% 不调)
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skill import Skill

log = structlog.get_logger(__name__)


async def match_skill(
    *,
    session: AsyncSession,
    user_message: str,
    intent: dict[str, Any],
) -> Skill | None:
    # L1:关键词命中(简单实现:domain + scenario 任意命中)
    domain = intent.get("domain")
    scenario = intent.get("scenario")
    candidates: list[Skill] = []

    # 铁律 16:V1 只匹配 public 可见的 skill;subscribed/private 走订阅(V1.5)
    base_filters = [Skill.status == "published", Skill.visibility == "public"]
    if scenario:
        rows = await session.execute(
            select(Skill).where(Skill.scenario == scenario, *base_filters)
        )
        candidates = list(rows.scalars().all())
    if not candidates and domain:
        rows = await session.execute(
            select(Skill).where(Skill.domain == domain, *base_filters)
        )
        candidates = list(rows.scalars().all())

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        log.debug("skill_match.no_candidate", message=user_message[:50])
        return None

    # L2 / L3 兜底:简单返回第一条;真实实现走向量 / LLM
    # TODO(skill-match-l2-l3): 接 BGE-M3 + pgvector hnsw + LLM 兜底
    return candidates[0]
