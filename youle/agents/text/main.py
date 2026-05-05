"""Agent 1(文字)进程入口 — v3.0 ADR-001-rev。"""

from __future__ import annotations

import asyncio

from agents._common.consumer import AgentConsumer
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
            # TODO(agent1-handlers): structured_writing / summarization / analysis / translation / polish
        },
    )
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
