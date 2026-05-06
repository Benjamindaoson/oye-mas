"""Agent 2 扩展 handlers — V1.5 范围,V1 接口预留(铁律 11)。

每个 handler 走 mcp-document-tools(铁律 13:工具走 MCP)。
传入参数从 inputs / parameters 中读;输出为 OSS 引用 + metadata。
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

from agents._common.mcp_client import mcp_client
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

ARTIFACT_TYPE_BY_TOOL = {
    "pptx_assemble": "document",
    "xlsx_assemble": "document",
    "docx_assemble": "document",
    "pdf_extract": "text",
    "pdf_ocr": "text",
}


def _make_handler(tool_name: str):
    async def _handler(task: AgentTask) -> AgentResult:
        t0 = time.monotonic()
        # 把 inputs / parameters 合并传给 MCP tool(剔除 _prompt)
        args: dict[str, Any] = {**(task.parameters or {}), **(task.inputs or {})}
        args.pop("_prompt", None)
        out = await mcp_client.call_tool(
            server="document_tools",
            tool=tool_name,
            arguments=args,
        )
        if out.get("_failed"):
            return AgentResult(
                task_id=task.task_id,
                step_id=task.step_id,
                status="failed",
                error_detail={"tool": tool_name, "error": out.get("error", "unknown")},
                duration_ms=int((time.monotonic() - t0) * 1000),
            )

        ref = out.get("oss_ref")
        artifact_type = ARTIFACT_TYPE_BY_TOOL.get(tool_name, "document")

        # pdf_extract / pdf_ocr 是文本输出 — 没有 oss_ref 时,落 OSS 文本
        if not ref and tool_name in ("pdf_extract", "pdf_ocr"):
            from agents._common.oss_writer import put_text

            ref = await put_text(
                key=f"artifacts/{task.task_id}/{task.step_id}.txt",
                content=out.get("text", ""),
            )

        meta = {k: v for k, v in out.items() if k not in ("oss_ref", "text")}
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="completed",
            output=ArtifactRef(
                artifact_id=uuid4(),
                type=artifact_type,
                reference=ref or f"oss://artifacts/{task.task_id}/{task.step_id}",
                extra_metadata=meta,
            ),
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

    _handler.__name__ = f"{tool_name}_handler"
    return _handler


pptx_assemble_handler = _make_handler("pptx_assemble")
xlsx_assemble_handler = _make_handler("xlsx_assemble")
docx_assemble_handler = _make_handler("docx_assemble")
pdf_extract_handler = _make_handler("pdf_extract")
pdf_ocr_handler = _make_handler("pdf_ocr")
