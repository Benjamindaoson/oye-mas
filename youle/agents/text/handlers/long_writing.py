"""Agent 1 long_writing handler — 真实走 LiteLLM 流式输出,产物落 OSS。"""

from __future__ import annotations

import time
from uuid import uuid4

import structlog

from agents._common import llm
from agents._common.oss_writer import put_text
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """你是「有了」产品的文案师 Agent,专门写长文(脚本、报告、长篇分析)。

## 输出原则
1. 流式输出,每段写完即推送
2. 不写过渡词、不写"以下是..."等寒暄
3. 严格遵循篇幅限制
"""


async def long_writing_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    user_prompt = task.inputs.get("_prompt") or task.inputs.get("prompt", "")
    if not user_prompt:
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="failed",
            error_detail={"reason": "missing_prompt"},
        )

    # 流式拼接(真实 stream 时同时通过 Redis 推 step_streaming WS 事件;此处简化为收尾再 emit)
    chunks: list[str] = []
    async for chunk in llm.stream(
        task_type=task.task_type,  # short_video_script / long_writing / ...
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        routing_hints=task.routing_hints,
        temperature=0.7,
    ):
        chunks.append(chunk)
    full_text = "".join(chunks)

    artifact_id = uuid4()
    oss_ref = await put_text(
        key=f"artifacts/{task.task_id}/{task.step_id}.txt", content=full_text
    )

    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=artifact_id,
            type="text",
            reference=oss_ref,
            extra_metadata={"length": len(full_text)},
        ),
        duration_ms=int((time.monotonic() - t0) * 1000),
    )
