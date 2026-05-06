"""Agent 1(文字)进程入口 — v3.0 ADR-001-rev。"""

from __future__ import annotations

import asyncio

from agents._common.consumer import AgentConsumer
from agents.text.handlers.extras import (
    analysis_handler,
    polish_handler,
    structured_writing_handler,
    summarization_handler,
    translation_handler,
)
from agents.text.handlers.long_writing import long_writing_handler
from agents.text.handlers.short_writing import short_writing_handler
from agents.text.handlers.version_compare import version_compare_handler
from agents.text.handlers.web_search import web_search_handler


async def main() -> None:
    consumer = AgentConsumer(
        agent_id="agent_1",
        handlers={
            "web_search": web_search_handler,
            "long_writing": long_writing_handler,
            "short_video_script": long_writing_handler,  # 同 handler,task_type 不同 → 路由不同模型
            "short_writing": short_writing_handler,
            "version_compare": version_compare_handler,
            # V1.5 扩展接口(handlers/extras.py)— task_type 各自走 LiteLLM 不同路由
            "structured_writing": structured_writing_handler,
            "summarization": summarization_handler,
            "analysis": analysis_handler,
            "translation": translation_handler,
            "polish": polish_handler,
        },
    )
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
