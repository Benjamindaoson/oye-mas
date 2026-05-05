"""Agent 4(影音师)进程入口 — v3.0 ADR-001-rev / ADR-005-rev。"""

from __future__ import annotations

import asyncio

from agents._common.consumer import AgentConsumer
from agents.av.handlers.bgm_select import bgm_select_handler
from agents.av.handlers.tts_generate import tts_generate_handler
from agents.av.handlers.video_compose import video_compose_handler


async def main() -> None:
    consumer = AgentConsumer(
        agent_id="agent_4",
        handlers={
            "bgm_select": bgm_select_handler,
            "tts_generate": tts_generate_handler,
            "video_compose": video_compose_handler,
            # TODO(agent4-handlers): text_to_video / image_to_video / subtitle_align / ...
        },
    )
    await consumer.start()


if __name__ == "__main__":
    asyncio.run(main())
