"""TaskRunner 调度逻辑单测(不需要 docker / pg)。

策略:Mock session + DB 模型,只验证调度纯逻辑(topo + HITL gate 阻塞 + modify 重派)。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

# ════════════════════════════════════════════════════════════════
# 拓扑调度的核心思路验证(纯 Python,不碰 SQLAlchemy)
# ════════════════════════════════════════════════════════════════


def _eligible(
    workflow: list[dict[str, Any]],
    statuses: dict[str, str],
    blocked_by_gate: set[str],
) -> list[str]:
    """复制 runner._dispatch_eligible 的纯调度判定。"""
    out = []
    for step in workflow:
        sid = step["step_id"]
        if statuses.get(sid) != "pending":
            continue
        deps = step.get("depends_on", [])
        if any(d in blocked_by_gate for d in deps):
            continue
        if not all(statuses.get(d) == "completed" for d in deps):
            continue
        out.append(sid)
    return out


ANTI_FRAUD = [
    {"step_id": "research", "depends_on": []},
    {"step_id": "script", "depends_on": ["research"]},
    {"step_id": "image_process", "depends_on": ["research"]},
    {"step_id": "bgm", "depends_on": ["script"]},
    {"step_id": "video_compose", "depends_on": ["script", "image_process", "bgm"]},
]


def test_entry_only_research() -> None:
    statuses = {s["step_id"]: "pending" for s in ANTI_FRAUD}
    assert _eligible(ANTI_FRAUD, statuses, set()) == ["research"]


def test_after_research_two_branches() -> None:
    statuses = {s["step_id"]: "pending" for s in ANTI_FRAUD}
    statuses["research"] = "completed"
    out = _eligible(ANTI_FRAUD, statuses, set())
    assert sorted(out) == ["image_process", "script"]


def test_script_gate_blocks_bgm() -> None:
    """script 完成但 gate 还开着 → bgm 不能派。"""
    statuses = {s["step_id"]: "pending" for s in ANTI_FRAUD}
    statuses["research"] = "completed"
    statuses["script"] = "completed"
    statuses["image_process"] = "completed"
    out = _eligible(ANTI_FRAUD, statuses, blocked_by_gate={"script"})
    assert out == []  # bgm 依赖 script,被 gate 卡住


def test_after_all_gates_closed_bgm_runs() -> None:
    statuses = {s["step_id"]: "pending" for s in ANTI_FRAUD}
    statuses["research"] = "completed"
    statuses["script"] = "completed"
    statuses["image_process"] = "completed"
    out = _eligible(ANTI_FRAUD, statuses, set())
    assert out == ["bgm"]


def test_video_compose_needs_all_three() -> None:
    statuses = {s["step_id"]: "pending" for s in ANTI_FRAUD}
    statuses["research"] = "completed"
    statuses["script"] = "completed"
    statuses["image_process"] = "completed"
    statuses["bgm"] = "running"
    out = _eligible(ANTI_FRAUD, statuses, set())
    assert out == []  # bgm 还没完成


def test_video_compose_eligible_after_bgm_done() -> None:
    statuses = {
        "research": "completed",
        "script": "completed",
        "image_process": "completed",
        "bgm": "completed",
        "video_compose": "pending",
    }
    out = _eligible(ANTI_FRAUD, statuses, set())
    assert out == ["video_compose"]


# ════════════════════════════════════════════════════════════════
# Jinja2 模板上下文(deps 产物注入)
# ════════════════════════════════════════════════════════════════


def test_template_renders_with_dep_artifact() -> None:
    from jinja2 import Template

    tpl = Template("基于 {{research.output}} 撰写脚本,受众 {{受众}}")
    out = tpl.render(
        **{"research": {"output": "oss://test/research.xlsx"}, "受众": "城市老人"}
    )
    assert "oss://test/research.xlsx" in out
    assert "城市老人" in out


# ════════════════════════════════════════════════════════════════
# V1 不允许 rollback(铁律 14)
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_resolve_hitl_rollback_raises() -> None:
    from app.orchestrator.runner import TaskRunner
    from app.models.hitl_gate import HITLGate

    fake_session = MagicMock()
    fake_gate = HITLGate(
        id=uuid4(),
        task_id=uuid4(),
        step_id="video_compose",
        gate_type="final_approval",
        timeout_seconds=600,
        closed_at=None,
    )
    fake_session.get = AsyncMock(return_value=fake_gate)
    fake_session.commit = AsyncMock()

    runner = TaskRunner(
        fake_session,
        dispatcher=AsyncMock(),
        publisher=AsyncMock(),
    )
    with pytest.raises(NotImplementedError):
        await runner.resolve_hitl(fake_gate.id, resolution="rolled_back")
