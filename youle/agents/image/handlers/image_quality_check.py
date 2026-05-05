"""Agent 3 image_quality_check — vision 模型评分。"""

from __future__ import annotations

import json
import time
from uuid import uuid4

from agents._common import llm
from agents._common.oss_writer import put_json
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

SYSTEM = """你是设计师 Agent,评估图片质量。
维度:分辨率、主体清晰度、与文案/卖点相关度、风格一致性。
输出严格 JSON: {"score": 0.0-1.0, "issues": ["..."], "suggestion": "..."}"""


async def image_quality_check_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    ref = task.inputs.get("reference") or task.inputs.get("_prompt", "")
    resp = await llm.complete(
        task_type="image_quality_check",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"评估这张图: {ref}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    try:
        report = json.loads(resp.content)
    except json.JSONDecodeError:
        report = {"score": 0.5, "issues": ["parse_failed"], "suggestion": ""}

    oss_ref = await put_json(
        key=f"artifacts/{task.task_id}/{task.step_id}.json", payload=report
    )
    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(),
            type="quality_report",
            reference=oss_ref,
            extra_metadata={"score": report.get("score", 0)},
        ),
        cost_usd=resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=resp.model,
    )
