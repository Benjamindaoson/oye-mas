"""子模块 9:Agent 互动编排器(v3.0 ADR-015)。

派活时编排"前 Agent → 后 Agent"的交接对话(handoff message)。
V1 克制 — 不每步演戏。

严肃场景(金融/医疗/政务)关闭表情(铁律 19)。
"""

from __future__ import annotations

import structlog

from app.config.prompts import AGENT_HANDOFF_PROMPT
from app.router import complete

log = structlog.get_logger(__name__)

AGENT_DISPLAY = {
    "agent_1": "研究员",
    "agent_2": "文档专员",
    "agent_3": "设计师",
    "agent_4": "影音师",
}

SOLEMN_SCENARIOS = {"finance", "medical", "government"}


async def emit_handoff(
    *,
    from_agent: str,
    to_agent: str,
    summary: str,
    scenario: str | None = None,
) -> str:
    """生成一句 Agent 间交接的群聊语;严肃场景返回空串(关闭演戏)。"""
    if scenario in SOLEMN_SCENARIOS:
        return ""

    resp = await complete(
        task_type="intent_understanding",  # 复用 L1 路由
        messages=[
            {
                "role": "system",
                "content": AGENT_HANDOFF_PROMPT.format(
                    from_agent=AGENT_DISPLAY.get(from_agent, from_agent),
                    to_agent=AGENT_DISPLAY.get(to_agent, to_agent),
                    summary=summary[:200],
                ),
            }
        ],
        temperature=0.5,
        max_tokens=80,
    )
    return resp.content.strip()
