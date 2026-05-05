"""Agent 1 short_writing — 短文(标题、口播稿)。"""

from __future__ import annotations

import time
from uuid import uuid4

from agents._common import llm
from agents._common.oss_writer import put_text
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

SYSTEM = "你是文案师,直接产出短文,不寒暄、不解释。"


async def short_writing_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    prompt = task.inputs.get("_prompt") or task.inputs.get("prompt", "")
    resp = await llm.complete(
        task_type="short_writing",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        routing_hints=task.routing_hints,
        max_tokens=task.parameters.get("max_tokens", 200),
    )
    oss_ref = await put_text(
        key=f"artifacts/{task.task_id}/{task.step_id}.txt", content=resp.content
    )
    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(),
            type="text",
            reference=oss_ref,
            extra_metadata={"model": resp.model},
        ),
        cost_usd=resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=resp.model,
    )
