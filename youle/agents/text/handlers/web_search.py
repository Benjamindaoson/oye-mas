"""Agent 1 web_search handler — 真实走 mcp-search 工具,产物落 OSS。"""

from __future__ import annotations

import time
from uuid import uuid4

import structlog

from agents._common.flywheel_emitter import emit
from agents._common.mcp_client import mcp_client
from agents._common.oss_writer import put_json
from agents._common.protocol import AgentResult, AgentTask, ArtifactRef

log = structlog.get_logger(__name__)


async def web_search_handler(task: AgentTask) -> AgentResult:
    t0 = time.monotonic()
    query = (
        task.inputs.get("query")
        or task.parameters.get("query")
        or task.inputs.get("_prompt", "")
    )[:300]
    max_results = int(task.parameters.get("max_results", 10))

    try:
        out = await mcp_client.call_tool(
            server="search",
            tool="web_search",
            arguments={"query": query, "max_results": max_results},
        )
    except Exception as e:
        log.warning("web_search.mcp_failed", err=str(e))
        return AgentResult(
            task_id=task.task_id,
            step_id=task.step_id,
            status="failed",
            error_detail={"reason": "mcp_search_failed", "msg": str(e)},
        )

    results = out.get("results", [])
    artifact_id = uuid4()
    oss_ref = await put_json(
        key=f"artifacts/{task.task_id}/{task.step_id}.json",
        payload={"query": query, "results": results},
    )

    artifact = ArtifactRef(
        artifact_id=artifact_id,
        type="structured",
        reference=oss_ref,
        extra_metadata={"query": query, "result_count": len(results)},
    )

    # 飞轮信号 1:工作流轨迹(任务级在主编排 emit;此处 emit step 完成事件)
    await emit(
        signal_type="trace",
        payload={
            "task_id": str(task.task_id),
            "step_id": task.step_id,
            "agent_id": "agent_1",
            "task_type": "web_search",
            "result_count": len(results),
        },
    )

    return AgentResult(
        task_id=task.task_id,
        step_id=task.step_id,
        status="completed",
        output=artifact,
        duration_ms=int((time.monotonic() - t0) * 1000),
    )
