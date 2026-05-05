"""Agent 3(设计师)进程入口 — v3.0 ADR-001-rev。"""

from __future__ import annotations

import asyncio

from agents._common.consumer import AgentConsumer
from agents.image.handlers.batch_generate import batch_generate_handler
from agents.image.handlers.image_download import image_download_handler
from agents.image.handlers.image_quality_check import image_quality_check_handler
from agents.image.handlers.style_extract import style_extract_handler


async def main() -> None:
    consumer = AgentConsumer(
        agent_id="agent_3",
        handlers={
            "image_download": image_download_handler,
            "batch_generate": batch_generate_handler,
            "image_quality_check": image_quality_check_handler,
            "style_extract": style_extract_handler,
            # TODO(agent3): image_generate / image_edit / image_describe / background_remove / ...
        },
    )
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
