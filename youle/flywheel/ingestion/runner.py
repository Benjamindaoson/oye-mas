"""信号 1:工作流完整轨迹 → Qdrant 镜像 + OSS 长存。

任务完成时,把 LangGraph state 序列化、提取 step / artifact / cost / duration、用 BGE-M3 生成 1024 维向量 → Qdrant。
"""

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
        try:
            resp = await redis.xread({"flywheel:signals": last_id}, block=5000, count=10)
        except asyncio.CancelledError:
            break
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                last_id = msg_id
                if fields.get("type") == "trace":
                    payload = json.loads(fields.get("payload", "{}"))
                    # TODO(flywheel-ingestion): BGE-M3 embed → Qdrant upsert + OSS 落 trace
                    log.debug("flywheel.ingestion", task_id=payload.get("task_id"))


if __name__ == "__main__":
    asyncio.run(main())
