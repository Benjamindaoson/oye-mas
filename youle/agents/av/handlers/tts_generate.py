"""Agent 4 tts_generate — 走 LiteLLM 调 Volcengine TTS,产物落 OSS。"""

from __future__ import annotations

import time
from uuid import uuid4

from agents._common import llm
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef


async def tts_generate_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    text = task.inputs.get("text") or task.inputs.get("_prompt") or ""
    voice = task.parameters.get("voice", "female_warm")

    if not text:
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="failed",
            error_detail={"reason": "missing_text"},
        )

    # LiteLLM 把 audio 模型也走同一接口;真实 prod 用 audio/speech endpoint
    # 这里先打 chat completions 做兼容(LITELLM_MOCK 模式直接返回 mock 路径)
    resp = await llm.complete(
        task_type="tts_generate",
        messages=[{"role": "user", "content": text}],
        routing_hints=task.routing_hints,
    )

    oss_ref = f"oss://artifacts/{task.task_id}/{task.step_id}.mp3"
    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(),
            type="audio",
            reference=oss_ref,
            extra_metadata={"voice": voice, "char_count": len(text), "model": resp.model},
        ),
        cost_usd=resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=resp.model,
    )
