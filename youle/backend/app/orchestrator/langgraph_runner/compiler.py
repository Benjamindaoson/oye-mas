"""Skill YAML → LangGraph StateGraph 编译器。

每个 Skill workflow step 对应一个 LangGraph 节点,它做的事是:
  1. 从 state.collected_fields 渲染 prompt_template
  2. 通过 Redis Streams 派发 AgentTask 到对应 Agent worker
  3. 阻塞等待 agent_results:<task_id> stream 上该 step 的回执
  4. 写回 state.step_results[step_id]
  5. 若 step 配 hitl_gate → 调 interrupt() 暂停,等用户决议

并行 fan-out 策略:
  - 用 conditional_edges 从入口节点 yield Send("step_X", state) 列表
    给所有 deps 已满足的 step,LangGraph 自己跑同层并行
  - 每个 step 完成后再 dispatch 下一层

铁律 13 守住:Agent 派发依然走 Redis Streams,LangGraph 不直接调 Agent 函数。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import structlog
from jinja2 import Template
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send, interrupt

from app.orchestrator.langgraph_runner.state import TaskState
from app.orchestrator.task_compiler import compile_to_dag
from app.schemas.agent import AgentTask

log = structlog.get_logger(__name__)

DispatchFn = Callable[[AgentTask], Any]  # async


# ─────────────────────────────────────────────────────────────────
# 节点工厂
# ─────────────────────────────────────────────────────────────────
def _make_step_node(
    step_def: dict[str, Any],
    *,
    dispatcher: DispatchFn,
    result_waiter: Callable[[str, str, int], Any],
):
    """生成单个 step 的 LangGraph 节点函数。

    节点行为:
      派发 → 阻塞等回执 → 写 step_results → (若 gate)interrupt
    """

    sid: str = step_def["step_id"]
    agent_id: str = step_def["agent"]
    task_type: str = step_def["task_type"]
    timeout_s: int = int(step_def.get("timeout") or 120)
    has_gate = bool(step_def.get("hitl_gate"))
    gate_cfg = step_def.get("hitl_gate") or {}
    prompt_template: str = step_def.get("prompt_template", "")
    static_inputs: dict[str, Any] = step_def.get("inputs") or {}
    parameters: dict[str, Any] = step_def.get("parameters") or {}
    routing_hints: dict[str, Any] = step_def.get("routing_hints") or {}

    async def _node(state: TaskState) -> dict[str, Any]:
        # 已完成:防 time-travel 后重跑
        prev = (state.get("step_results") or {}).get(sid)
        if prev and prev.get("status") == "completed":
            log.info("lg.node.skip_completed", step_id=sid)
            return {}

        started = datetime.now(UTC).isoformat()

        # 渲染 prompt
        inputs = dict(static_inputs)
        if prompt_template:
            try:
                inputs["_prompt"] = Template(prompt_template).render(
                    **(state.get("collected_fields") or {}),
                    step_results=state.get("step_results") or {},
                )
            except Exception as e:
                log.warning("lg.template_render_failed", step_id=sid, err=str(e))

        # 上游产物注入(让 step 之间能传递 ref)
        upstream_refs = {
            up_sid: r.get("artifact_ref")
            for up_sid, r in (state.get("step_results") or {}).items()
            if r.get("artifact_ref")
        }
        if upstream_refs:
            inputs["_upstream"] = upstream_refs

        agent_task = AgentTask(
            task_id=state["task_id"],  # type: ignore[arg-type]
            step_id=sid,
            agent_id=agent_id,  # type: ignore[arg-type]
            task_type=task_type,
            user_id=state["user_id"],  # type: ignore[arg-type]
            conversation_id=state["conversation_id"],  # type: ignore[arg-type]
            inputs=inputs,
            parameters=parameters,
            routing_hints=routing_hints,
            skill_id=state.get("skill_id"),
            skill_version=state.get("skill_version"),
            timeout_seconds=timeout_s,
        )

        # 派发到 Redis Streams
        await dispatcher(agent_task)
        log.info("lg.dispatched", step_id=sid, agent=agent_id)

        # 阻塞等结果(由 result_waiter 消费 agent_results:<task_id>)
        result = await result_waiter(state["task_id"], sid, timeout_s)
        completed = datetime.now(UTC).isoformat()

        if result is None:
            log.error("lg.timeout", step_id=sid, timeout=timeout_s)
            return {
                "step_results": {
                    sid: {
                        "step_id": sid,
                        "agent_id": agent_id,
                        "task_type": task_type,
                        "status": "failed",
                        "error_detail": {"reason": "timeout", "timeout_s": timeout_s},
                        "started_at": started,
                        "completed_at": completed,
                    }
                },
                "final_status": "failed",
                "failure_reason": f"step {sid!r} timeout",
            }

        step_result = {
            "step_id": sid,
            "agent_id": agent_id,
            "task_type": task_type,
            "status": result.status,
            "artifact_ref": result.output.reference if result.output else None,
            "artifact_type": result.output.type if result.output else None,
            "artifact_metadata": (result.output.extra_metadata if result.output else {}) or {},
            "duration_ms": result.duration_ms,
            "cost_usd": float(result.cost_usd) if result.cost_usd is not None else None,
            "model_used": result.model_used,
            "error_detail": result.error_detail,
            "started_at": started,
            "completed_at": completed,
        }

        if result.status == "failed":
            return {
                "step_results": {sid: step_result},
                "final_status": "failed",
                "failure_reason": (result.error_detail or {}).get("reason")
                or f"step {sid} failed",
            }

        update: dict[str, Any] = {"step_results": {sid: step_result}}

        # ─── HITL gate:中断,等用户决议 ───
        if has_gate and result.status == "completed":
            decision = interrupt(
                {
                    "kind": "hitl_gate",
                    "step_id": sid,
                    "gate_type": gate_cfg.get("gate_type", "quality_review"),
                    "preview_artifact_ref": step_result["artifact_ref"],
                    "preview_artifact_metadata": step_result["artifact_metadata"],
                    "task_id": state["task_id"],
                    "agent_id": agent_id,
                }
            )
            # 用户回复:{"resolution": "approved" | "modify_request" | "rejected", "feedback": "..."}
            update["hitl_decisions"] = {sid: decision}
            if decision.get("resolution") == "rejected":
                update["final_status"] = "failed"
                update["failure_reason"] = f"HITL {sid} rejected: {decision.get('feedback', '')[:200]}"

        return update

    _node.__name__ = f"step_{sid}"
    return _node


# ─────────────────────────────────────────────────────────────────
# Send 路由(动态 fan-out)
# ─────────────────────────────────────────────────────────────────
def _make_router(workflow: list[dict[str, Any]], primary_step: str | None):
    """从入口"plan" 节点路由出去 — 把所有 deps 满足且未完成的 step 用 Send 派出。"""

    deps_by_step: dict[str, list[str]] = {
        s["step_id"]: list(s.get("depends_on") or []) for s in workflow
    }

    def _eligible(state: TaskState) -> list[str]:
        results = state.get("step_results") or {}
        out: list[str] = []
        for sid, deps in deps_by_step.items():
            if sid in results and results[sid].get("status") in ("completed", "rolled_back"):
                continue
            if sid in results and results[sid].get("status") == "running":
                continue  # 防止 fan-in 时重复派
            if all(
                d in results and results[d].get("status") == "completed" for d in deps
            ):
                out.append(sid)
        return out

    def _route(state: TaskState):
        # 任务已失败 → 直接结束
        if state.get("final_status") == "failed":
            return END
        # 还有待执行 step → fan-out
        eligible = _eligible(state)
        if eligible:
            return [Send(f"step_{sid}", state) for sid in eligible]
        # 所有 step 完成 → 终结
        results = state.get("step_results") or {}
        if all(
            results.get(s["step_id"], {}).get("status") in ("completed", "rolled_back")
            for s in workflow
        ):
            return "finalize"
        return END  # 死锁兜底

    return _route


# ─────────────────────────────────────────────────────────────────
# finalize / planner 节点
# ─────────────────────────────────────────────────────────────────
def _make_planner(workflow: list[dict[str, Any]]):
    """planner 是 START 之后的"门",只做日志 + state init。真正的 fan-out 靠后面的 router。"""

    async def _planner(state: TaskState) -> dict[str, Any]:
        log.info("lg.planner", task_id=state.get("task_id"), steps=len(workflow))
        return {}

    return _planner


def _make_finalize(primary_step: str | None):
    async def _finalize(state: TaskState) -> dict[str, Any]:
        results = state.get("step_results") or {}
        primary_ref = None
        if primary_step and primary_step in results:
            primary_ref = results[primary_step].get("artifact_ref")
        return {
            "final_status": state.get("final_status") or "completed",
            "primary_artifact_ref": primary_ref,
        }

    return _finalize


# ─────────────────────────────────────────────────────────────────
# 顶层:build_state_graph
# ─────────────────────────────────────────────────────────────────
def build_state_graph(
    skill_yaml: dict[str, Any],
    *,
    dispatcher: DispatchFn,
    result_waiter: Callable[[str, str, int], Any],
):
    """编译 Skill YAML 为 LangGraph 图(未编译,等 runner 加 checkpointer)。"""
    # 复用现有 DAG 校验(环检测 / 缺失 dep / 重复 step_id)
    compile_to_dag(skill_yaml)

    workflow: list[dict[str, Any]] = skill_yaml.get("workflow") or []
    primary_step: str | None = (skill_yaml.get("delivery") or {}).get("primary_artifact")

    builder = StateGraph(TaskState)
    builder.add_node("planner", _make_planner(workflow))
    builder.add_node("finalize", _make_finalize(primary_step))

    for step_def in workflow:
        builder.add_node(
            f"step_{step_def['step_id']}",
            _make_step_node(step_def, dispatcher=dispatcher, result_waiter=result_waiter),
        )

    builder.add_edge(START, "planner")
    # planner 后用 router 把可执行 step 一次性 Send 出去
    builder.add_conditional_edges(
        "planner", _make_router(workflow, primary_step), [f"step_{s['step_id']}" for s in workflow] + ["finalize", END],
    )
    # 每个 step 跑完后 → 回 planner(让 router 再判断下一层)
    for step_def in workflow:
        builder.add_edge(f"step_{step_def['step_id']}", "planner")

    builder.add_edge("finalize", END)
    return builder
