"""Agent 3 style_extract — 从参考图提取风格指引。"""

from __future__ import annotations

import time
from uuid import uuid4

from agents._common import llm
from agents._common.oss_writer import put_text
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

SYSTEM = """你是设计师 Agent,从参考图提取风格指引。
维度:配色、构图、字体、氛围。输出结构化文字。"""


async def style_extract_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    ref = task.inputs.get("reference", "")
    style_pref = task.inputs.get("style_pref", task.parameters.get("style_pref", ""))
    resp = await llm.complete(
        task_type="style_extract",
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"参考图: {ref}\n用户偏好风格: {style_pref}"},
        ],
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
            type="structured",
            reference=oss_ref,
        ),
        cost_usd=resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=resp.model,
    )
