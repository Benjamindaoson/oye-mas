"""Agent 2(文档专员)进程入口 — v3.0 ADR-001-rev。"""

from __future__ import annotations

import asyncio

from agents._common.consumer import AgentConsumer
from agents.document.handlers.image_concat_long import image_concat_long_handler


async def main() -> None:
    consumer = AgentConsumer(
        agent_id="agent_2",
        handlers={
            "image_concat_long": image_concat_long_handler,
            # TODO(agent2-handlers): pptx_assemble / xlsx_assemble / docx_assemble / pdf_extract / pdf_ocr
        },
    )
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
