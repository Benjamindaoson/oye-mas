"""信号 3:失败 → Reflexion → prompt 改进候选(人审)。"""

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
                if fields.get("type") == "reflexion":
                    payload = json.loads(fields.get("payload", "{}"))
                    # TODO(flywheel-reflexion): 调 REFLEXION_SYSTEM_PROMPT → 写 prompt_improvement_candidates
                    log.debug("flywheel.reflexion", task_id=payload.get("task_id"))


if __name__ == "__main__":
    asyncio.run(main())
