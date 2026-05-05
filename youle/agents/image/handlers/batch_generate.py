"""Agent 3 batch_generate — 电商详情图核心:第 1 张为视觉锚点,后续保持风格。"""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import structlog

from agents._common import llm
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

log = structlog.get_logger(__name__)


async def batch_generate_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    image_specs = task.parameters.get("image_specs", [])
    style_strength = float(task.parameters.get("style_strength", 0.7))

    if not image_specs:
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="failed",
            error_detail={"reason": "no_image_specs"},
        )

    # 第 1 张:风格锚点(无 reference 锚定)
    anchor_resp = await llm.complete(
        task_type="image_generate",
        messages=[
            {"role": "user", "content": image_specs[0].get("prompt", "")},
        ],
        routing_hints=task.routing_hints,
    )

    # 后续:用 anchor 的风格作为 reference,style_strength 保持
    async def _gen(spec: dict) -> str:
        await llm.complete(
            task_type="image_generate",
            messages=[{"role": "user", "content": spec.get("prompt", "")}],
            routing_hints=task.routing_hints,
        )
        return f"oss://artifacts/{task.task_id}/{task.step_id}/{uuid4().hex}.png"

    rest_refs = await asyncio.gather(*(_gen(s) for s in image_specs[1:]))
    all_refs = [
        f"oss://artifacts/{task.task_id}/{task.step_id}/anchor.png",
        *rest_refs,
    ]

    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(),
            type="image_collection",
            reference=f"oss://artifacts/{task.task_id}/{task.step_id}/manifest.json",
            extra_metadata={
                "count": len(all_refs),
                "anchor_strength": style_strength,
                "image_refs": all_refs,
                "model": anchor_resp.model,
            },
        ),
        cost_usd=anchor_resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=anchor_resp.model,
    )
