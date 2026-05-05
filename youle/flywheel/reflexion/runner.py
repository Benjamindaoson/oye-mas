"""信号 3:失败 / 用户负反馈 → Reflexion → prompt_improvement_candidates(人审)。

订阅 Redis Stream `flywheel:signals` 中 type=reflexion 的消息;
基于失败 task 的 trace 调 LLM 生成根因 + 改进建议;
写入 prompt_improvement_candidates 表(status='pending')。
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from uuid import UUID, uuid4

import redis.asyncio as aioredis
import structlog

from app.config.prompts import REFLEXION_SYSTEM_PROMPT
from app.db import SessionLocal
from app.models.prompt_improvement import PromptImprovementCandidate
from app.router import complete

log = structlog.get_logger(__name__)


async def _process(payload: dict[str, Any]) -> None:
    task_id = payload.get("task_id")
    prompt_name = payload.get("prompt_name") or "unknown"
    trace_excerpt = payload.get("trace_excerpt") or ""
    failure_reason = payload.get("failure_reason") or ""

    user_msg = (
        f"任务 ID:{task_id}\n"
        f"使用的 prompt:{prompt_name}\n"
        f"失败原因:{failure_reason}\n"
        f"轨迹片段:\n{trace_excerpt}"
    )

    try:
        resp = await complete(
            task_type="brief_update",
            messages=[
                {"role": "system", "content": REFLEXION_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=600,
        )
        data = json.loads(resp.content)
    except Exception as e:
        log.warning("flywheel.reflexion.llm_failed", err=str(e))
        return

    async with SessionLocal() as session:
        cand = PromptImprovementCandidate(
            id=uuid4(),
            prompt_name=prompt_name,
            failure_task_id=UUID(task_id) if task_id else None,
            root_cause=data.get("root_cause"),
            section_to_improve=data.get("section_to_improve"),
            current_text=data.get("current_text"),
            proposed_changes=data.get("proposed_changes"),
            expected_improvement=data.get("expected_improvement"),
            status="pending",
        )
        session.add(cand)
        await session.commit()
        log.info(
            "flywheel.reflexion.written",
            candidate_id=str(cand.id),
            prompt_name=prompt_name,
        )


async def main() -> None:
    redis = aioredis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    last_id = "$"  # 只接 runner 启动后的新事件
    while True:
        try:
            resp = await redis.xread(
                {"flywheel:signals": last_id}, block=5000, count=10
            )
        except Exception as e:
            log.warning("flywheel.reflexion.xread_failed", err=str(e))
            await asyncio.sleep(2)
            continue
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                last_id = msg_id
                if fields.get("type") != "reflexion":
                    continue
                try:
                    payload = json.loads(fields.get("payload", "{}"))
                except json.JSONDecodeError:
                    continue
                await _process(payload)


if __name__ == "__main__":
    asyncio.run(main())
