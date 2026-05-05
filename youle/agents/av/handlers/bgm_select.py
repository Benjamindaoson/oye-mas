"""Agent 4 bgm_select — 从素材库匹配,无 LLM。"""

from __future__ import annotations

import os
import time
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agents._common.protocol import AgentResult, AgentTask, ArtifactRef


def _parse_duration(field: str | int) -> int:
    if isinstance(field, int):
        return field
    s = str(field).strip().lower().rstrip("s")
    return int(s) if s.isdigit() else 60


async def bgm_select_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    mood = task.parameters.get("mood", "neutral")
    duration_field = task.parameters.get("duration_field", "60s")
    duration = _parse_duration(duration_field)

    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://youle:youle_dev@postgres:5432/youle")
    engine = create_async_engine(db_url, pool_pre_ping=True)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)

    try:
        async with Session() as session:
            # 真实查询 bgm_library:同 mood + 时长接近(±10s)+ active
            stmt = select(
                # 用 text 列名规避 model 引入循环依赖
                # 这里直接 raw SQL 等价
                # noqa
            )
            from sqlalchemy import text as sa_text

            rows = await session.execute(
                sa_text(
                    """
                    SELECT id::text, title, oss_ref, duration
                    FROM bgm_library
                    WHERE mood = :mood AND is_active = TRUE
                      AND ABS(duration - :dur) < 15
                    ORDER BY usage_count ASC
                    LIMIT 1
                    """
                ),
                {"mood": mood, "dur": duration},
            )
            row = rows.first()
    finally:
        await engine.dispose()

    if row is None:
        # 兜底:没素材也不阻塞,返回 placeholder
        oss_ref = f"oss://bgm/placeholder_{mood}_{duration}s.mp3"
        meta = {"mood": mood, "duration": duration, "fallback": True}
    else:
        oss_ref = row.oss_ref
        meta = {
            "mood": mood,
            "duration": int(row.duration),
            "title": row.title,
            "bgm_id": row.id,
        }

    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(), type="audio", reference=oss_ref, extra_metadata=meta
        ),
        duration_ms=int((time.monotonic() - t0) * 1000),
    )
