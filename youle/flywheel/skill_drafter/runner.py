"""信号 4:高满意度 → Skill 草稿(创作者飞轮 V1.5)。"""

from __future__ import annotations

import asyncio
import json
import os

import redis.asyncio as aioredis
import structlog

log = structlog.get_logger(__name__)


async def main() -> None:
    redis = aioredis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
    last_id = "0"
    while True:
        resp = await redis.xread({"flywheel:signals": last_id}, block=5000, count=10)
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                last_id = msg_id
                if fields.get("type") == "skill_draft":
                    payload = json.loads(fields.get("payload", "{}"))
                    # TODO(flywheel-draft): 调 SKILL_DRAFTER_PROMPT → 写 skill_drafts
                    log.debug("flywheel.draft", task_id=payload.get("task_id"))


if __name__ == "__main__":
    asyncio.run(main())
