"""Agent 2(文档专员)进程入口 — v3.0 ADR-001-rev。"""

from __future__ import annotations

import asyncio

from agents._common.consumer import AgentConsumer
from agents.document.handlers.extras import (
    docx_assemble_handler,
    pdf_extract_handler,
    pdf_ocr_handler,
    pptx_assemble_handler,
    xlsx_assemble_handler,
)
from agents.document.handlers.image_concat_long import image_concat_long_handler


async def main() -> None:
    consumer = AgentConsumer(
        agent_id="agent_2",
        handlers={
            "image_concat_long": image_concat_long_handler,
            # V1.5 扩展(handlers/extras.py)— 走 mcp-document-tools(铁律 13)
            "pptx_assemble": pptx_assemble_handler,
            "xlsx_assemble": xlsx_assemble_handler,
            "docx_assemble": docx_assemble_handler,
            "pdf_extract": pdf_extract_handler,
            "pdf_ocr": pdf_ocr_handler,
        },
    )
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
