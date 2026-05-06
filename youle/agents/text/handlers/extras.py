"""Agent 1 扩展 handlers — V1.5 范围,V1 仅注册接口避免 NotImplemented(铁律 11)。

每个 handler:复用 `short_writing_handler` 的 LLM+OSS 路径,但绑定不同 task_type
以走 LiteLLM 路由策略(铁律 7)— 这样 model_router 可以基于 task_type 分模型。

V1.5 时升级:
- structured_writing → JSON Schema 提示词 + 结构化解析
- summarization → 分段摘要 / 抽取式 / 生成式
- analysis → 把上游 reference 拆成知识点
- translation → 加术语表 + 双向方向
- polish → 风格化语料微调
"""

from __future__ import annotations

import time
from uuid import uuid4

from agents._common import llm
from agents._common.oss_writer import put_text
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

SYSTEM_BY_TYPE: dict[str, str] = {
    "structured_writing": "你是结构化写作师。请按 JSON 输出,字段名用 snake_case。",
    "summarization": "你是摘要师。先列 3-5 个要点,再给一段不超 200 字的总结。",
    "analysis": "你是分析师。从给定材料中提炼论点 / 论据 / 结论。直接列点。",
    "translation": "你是翻译师。中英互译,保持术语一致性。",
    "polish": "你是润色师。改通顺、改简洁,保留原意,不加新内容。",
}


def _make_handler(task_type: str):
    system = SYSTEM_BY_TYPE[task_type]

    async def _handler(task: AgentTask) -> AgentResult:
        t0 = time.monotonic()
        prompt = task.inputs.get("_prompt") or task.inputs.get("prompt", "")
        resp = await llm.complete(
            task_type=task_type,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            routing_hints=task.routing_hints,
            max_tokens=task.parameters.get("max_tokens", 800),
        )
        oss_ref = await put_text(
            key=f"artifacts/{task.task_id}/{task.step_id}.txt",
            content=resp.content,
        )
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="completed",
            output=ArtifactRef(
                artifact_id=uuid4(),
                type="text",
                reference=oss_ref,
                extra_metadata={"model": resp.model, "task_type": task_type},
            ),
            cost_usd=resp.cost_usd,
            duration_ms=int((time.monotonic() - t0) * 1000),
            model_used=resp.model,
        )

    _handler.__name__ = f"{task_type}_handler"
    return _handler


structured_writing_handler = _make_handler("structured_writing")
summarization_handler = _make_handler("summarization")
analysis_handler = _make_handler("analysis")
translation_handler = _make_handler("translation")
polish_handler = _make_handler("polish")
