"""Agent 3 image_download — 反诈视频:从研究 xlsx 的图片 URL 下载,质检。"""

from __future__ import annotations

import time
from uuid import uuid4

import structlog

from agents._common.mcp_client import mcp_client
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

log = structlog.get_logger(__name__)


async def image_download_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    urls = task.inputs.get("urls", []) or task.parameters.get("urls", [])
    check_quality = bool(task.parameters.get("check_quality", True))
    min_resolution = task.parameters.get("min_resolution", "1080p")

    out = await mcp_client.call_tool(
        server="image_tools",
        tool="download_batch",
        arguments={
            "urls": urls,
            "check_quality": check_quality,
            "min_resolution": min_resolution,
        },
    )
    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=ArtifactRef(
            artifact_id=uuid4(),
            type="image_collection",
            reference=out.get(
                "oss_ref", f"oss://artifacts/{task.task_id}/{task.step_id}/"
            ),
            extra_metadata={
                "count": out.get("downloaded_count", 0),
                "rejected": out.get("rejected_count", 0),
            },
        ),
        duration_ms=int((time.monotonic() - t0) * 1000),
    )
