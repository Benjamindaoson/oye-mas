"""Agent 3 扩展 handlers — V1.5 范围。

走 mcp-image-tools 的 bg_remove / enhance / quality_check;
image_generate / image_edit / image_describe 走 LiteLLM 多模态(铁律 7/13)。
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from agents._common import llm
from agents._common.mcp_client import mcp_client
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef


def _make_mcp_handler(tool_name: str, *, artifact_type: str = "image"):
    async def _handler(task: AgentTask) -> AgentResult:
        t0 = time.monotonic()
        args: dict[str, Any] = {**(task.parameters or {}), **(task.inputs or {})}
        args.pop("_prompt", None)
        out = await mcp_client.call_tool(
            server="image_tools", tool=tool_name, arguments=args
        )
        if out.get("_failed"):
            return AgentResult(
                task_id=task.task_id,
                step_id=task.step_id,
                status="failed",
                error_detail={"tool": tool_name, "error": out.get("error", "unknown")},
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
        ref = out.get("oss_ref") or f"oss://artifacts/{task.task_id}/{task.step_id}.png"
        meta = {k: v for k, v in out.items() if k != "oss_ref"}
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="completed",
            output=ArtifactRef(
                artifact_id=uuid4(),
                type=artifact_type,
                reference=ref,
                extra_metadata=meta,
            ),
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    _handler.__name__ = f"{tool_name}_handler"
    return _handler


bg_remove_handler = _make_mcp_handler("bg_remove")
enhance_handler = _make_mcp_handler("enhance")


async def image_generate_handler(task: AgentTask) -> AgentResult:
    """文生图(走 LiteLLM 路由的图像生成模型,e.g. seedream-4 / gpt-image-2)。"""
    t0 = time.monotonic()
    prompt = task.inputs.get("_prompt") or task.inputs.get("prompt", "")
    resp = await llm.complete(
        task_type="image_generate",
        messages=[{"role": "user", "content": prompt}],
        routing_hints=task.routing_hints,
    )
    # 真接入时 resp.content 是 url/oss_ref;占位先用 mock ref
    ref = (
        resp.content
        if isinstance(resp.content, str) and resp.content.startswith("oss://")
        else f"oss://artifacts/{task.task_id}/{task.step_id}.png"
    )
    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(),
            type="image",
            reference=ref,
            extra_metadata={"model": resp.model, "prompt": prompt[:200]},
        ),
        cost_usd=resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=resp.model,
    )


async def image_edit_handler(task: AgentTask) -> AgentResult:
    """图生图(局部重绘 / 扩图)— V1.5 接 SDXL Inpaint。V1 走与 generate 同模型。"""
    return await image_generate_handler(task)


async def image_describe_handler(task: AgentTask) -> AgentResult:
    """图理解 — 走 LiteLLM 多模态。返回文本到 OSS。"""
    t0 = time.monotonic()
    image_ref = (
        task.inputs.get("image_ref")
        or task.inputs.get("ref")
        or task.parameters.get("image_ref")
    )
    user_msg = task.inputs.get("_prompt") or "请描述这张图的核心元素。"
    resp = await llm.complete(
        task_type="image_describe",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": str(user_msg)},
                    {"type": "image_url", "image_url": {"url": str(image_ref)}},
                ]
                if image_ref
                else str(user_msg),
            }
        ],
        routing_hints=task.routing_hints,
    )
    from agents._common.oss_writer import put_text

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
            extra_metadata={"model": resp.model, "image_ref": image_ref},
        ),
        cost_usd=resp.cost_usd,
        duration_ms=int((time.monotonic() - t0) * 1000),
        model_used=resp.model,
    )
