"""信号 2:用户偏好向量(256 维 BGE-base-zh)。"""

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
                if fields.get("type") == "preference":
                    payload = json.loads(fields.get("payload", "{}"))
                    # TODO(flywheel-preference): 文本拼接 → BGE-base-zh embed → 合并到 256 维 → Postgres
                    log.debug("flywheel.preference", user_id=payload.get("user_id"))


if __name__ == "__main__":
    asyncio.run(main())
