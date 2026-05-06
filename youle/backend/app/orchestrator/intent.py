"""子模块 1:意图理解器。

输入:user_message + 最近对话历史 + 会话上下文
输出:Intent JSON {intent_type, domain, scenario, entities, confidence}
模型:deepseek-v4-flash(L1)

详见 docs/2_工程实现/主编排 Agent 实现指南.md §1
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal

import structlog
from pydantic import BaseModel, Field

from app.config.prompts import ORCHESTRATOR_INTENT_PROMPT
from app.router import complete
from app.services.metrics import record_intent_latency

log = structlog.get_logger(__name__)

IntentType = Literal[
    "task_request",
    "chitchat",
    "clarification_answer",
    "interrupt",
    "mode_switch",
    "team_management",
    "quota_query",
]


class Intent(BaseModel):
    intent_type: IntentType
    domain: Literal["text", "image", "video", "document", "mixed", "none"] = "none"
    scenario: str | None = None
    entities: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0


async def understand_intent(
    *,
    user_message: str,
    recent_history: list[dict[str, str]] | None = None,
    conversation_context: dict[str, Any] | None = None,
) -> Intent:
    history = recent_history or []
    context_blob = conversation_context or {}

    messages = [
        {"role": "system", "content": ORCHESTRATOR_INTENT_PROMPT},
        *history,
        {
            "role": "user",
            "content": json.dumps(
                {"message": user_message, "context": context_blob}, ensure_ascii=False
            ),
        },
    ]
    t0 = time.monotonic()
    resp = await complete(
        task_type="intent_understanding",
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    record_intent_latency(time.monotonic() - t0)
    try:
        data = json.loads(resp.content)
    except json.JSONDecodeError:
        log.warning("intent.parse_failed", content=resp.content[:200])
        data = {"intent_type": "chitchat", "confidence": 0.0}
    return Intent.model_validate(data)
