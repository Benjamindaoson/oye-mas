"""LangGraphTaskRunner — 与现有 TaskRunner 等价的 LangGraph 实现。

对外 API 兼容:
  - start(task_id) → invoke graph,返回 派发的 step 列表(对齐 TaskRunner.start)
  - resume(task_id, step_id, decision) → Command(resume=...) 唤醒 interrupt
  - resolve_hitl(...) → 同 resume
  - rollback_to_step(task_id, target_step) → time-travel(V2 中断 C/D 真实现)
  - get_state(task_id) → graph.aget_state
  - get_history(task_id) → graph.aget_state_history(用于 UI 时间线 + V2 回滚选 N)

对外仍走 ws_manager.publish(铁律不变)。LangGraph 的 astream_events 用作内部事件源
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact
from app.models.hitl_gate import HITLGate
from app.models.skill import Skill
from app.models.task import Task, TaskStep
from app.orchestrator.langgraph_runner.compiler import build_state_graph
from app.orchestrator.langgraph_runner.result_waiter import (
    reset_cursor,
    wait_for_step_result,
)
from app.orchestrator.langgraph_runner.state import make_initial_state
from app.schemas.ws import WSEventType
from app.services.agent_status import set_status as set_agent_status
from app.services.dispatcher import dispatch_task as default_dispatch
from app.services.flywheel import flywheel
from app.services.skill_loader import load_skill_by_id
from app.ws.manager import ws_manager

log = structlog.get_logger(__name__)

# ── 全局单例 checkpointer(进程级)──
# - 单 worker 时 InMemorySaver 够;
# - 多 worker / 跨重启用 PostgresSaver(见 checkpointer.py)。
_CHECKPOINTER = None  # 由 init_checkpointer() 注入


def init_checkpointer(saver) -> None:
    """app 启动时调一次。"""
    global _CHECKPOINTER
    _CHECKPOINTER = saver


def get_checkpointer():
    global _CHECKPOINTER
    if _CHECKPOINTER is None:
        _CHECKPOINTER = InMemorySaver()
        log.info("lg.checkpointer.in_memory_default")
    return _CHECKPOINTER


# ── 把 LangGraph 状态镜射回 DB(铁律 4 + 现有 UI 兼容)──
async def _mirror_step_to_db(
    session: AsyncSession,
    *,
    task_id: UUID,
    step_id: str,
    step_result: dict[str, Any],
) -> UUID | None:
    """把 LangGraph state.step_results 的一条镜射回 task_steps 表 + artifacts 表。"""
    artifact_db_id: UUID | None = None
    artifact_ref = step_result.get("artifact_ref")
    if artifact_ref:
        # 写 artifacts(若新)
        task = await session.get(Task, task_id)
        if task is not None:
            artifact = Artifact(
                id=uuid4(),
                user_id=task.user_id,
                source_conversation_id=task.conversation_id,
                source_task_id=task.id,
                type=step_result.get("artifact_type") or "text",
                reference=artifact_ref,
                extra_metadata=step_result.get("artifact_metadata") or {},
            )
            session.add(artifact)
            await session.flush()
            artifact_db_id = artifact.id

    # upsert task_step
    row = (
        await session.execute(
            select(TaskStep).where(
                TaskStep.task_id == task_id, TaskStep.step_id == step_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = TaskStep(
            id=uuid4(),
            task_id=task_id,
            step_id=step_id,
            agent_id=step_result.get("agent_id"),
            task_type=step_result.get("task_type"),
            status=step_result.get("status") or "pending",
        )
        session.add(row)
    else:
        row.agent_id = step_result.get("agent_id") or row.agent_id
        row.task_type = step_result.get("task_type") or row.task_type
        row.status = step_result.get("status") or row.status
    if step_result.get("started_at"):
        with contextlib.suppress(Exception):
            row.started_at = datetime.fromisoformat(step_result["started_at"])
    if step_result.get("completed_at"):
        with contextlib.suppress(Exception):
            row.completed_at = datetime.fromisoformat(step_result["completed_at"])
    if step_result.get("duration_ms") is not None:
        row.duration_ms = int(step_result["duration_ms"])
    if step_result.get("cost_usd") is not None:
        row.cost_usd = Decimal(str(step_result["cost_usd"]))
    if step_result.get("model_used"):
        row.model_used = step_result["model_used"]
    if artifact_db_id is not None:
        row.output_artifact_id = artifact_db_id
    if step_result.get("error_detail"):
        row.error_detail = step_result["error_detail"]
    await session.commit()
    return artifact_db_id


# ─────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────
class LangGraphTaskRunner:
    """与 TaskRunner 接口兼容的 LangGraph 版编排器。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        dispatcher=None,
        publisher=None,
    ) -> None:
        self.session = session
        self.dispatch = dispatcher or default_dispatch
        self.publish = publisher or ws_manager.publish

    # ── 加载 Skill YAML(同 TaskRunner)──
    async def _load_skill_yaml(self, task: Task) -> dict[str, Any]:
        if task.skill_id is None:
            raise ValueError(f"task {task.id} has no skill_id")
        skill = await self.session.get(Skill, task.skill_id)
        if skill is None or skill.yaml_definition is None:
            yml = await load_skill_by_id(task.skill_id)
            return yml
        return skill.yaml_definition

    # ── thread_id 约定:LangGraph checkpoint 的 key ──
    @staticmethod
    def _thread_id(task_id: UUID) -> str:
        return f"task:{task_id}"

    async def _build_compiled(self, skill_yaml: dict[str, Any]):
        """编译 + 注入 checkpointer。"""

        async def _wait(tid: str, sid: str, timeout: int):
            return await wait_for_step_result(tid, sid, timeout)

        builder = build_state_graph(
            skill_yaml,
            dispatcher=self.dispatch,
            result_waiter=_wait,
        )
        return builder.compile(checkpointer=get_checkpointer())

    # ── start:首次跑 ──
    async def start(self, task_id: UUID) -> dict[str, Any]:
        """启动 LangGraph 图。返回 final state(可能含 interrupt 标记)。"""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        skill_yaml = await self._load_skill_yaml(task)

        graph = await self._build_compiled(skill_yaml)
        config = {"configurable": {"thread_id": self._thread_id(task_id)}}

        initial = make_initial_state(
            task_id=task_id,
            user_id=task.user_id,
            conversation_id=task.conversation_id,
            skill_id=task.skill_id,
            skill_version=task.skill_version,
            skill_yaml=skill_yaml,
            collected_fields=task.collected_fields or {},
        )

        # 标记 task 进入执行
        task.status = "executing"
        task.started_at = task.started_at or datetime.now(UTC)
        await self.session.commit()

        # 跑 graph 直到结束 / interrupt(用 stream + handlers)
        final_state = await self._run_until_pause(graph, initial, config, task_id, task.user_id)
        return {"state": final_state, "config": config}

    # ── resume:HITL 决议后 / 中断后续 ──
    async def resume(
        self,
        task_id: UUID,
        *,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """HITL gate 用户决议后调:graph 用 Command(resume=decision) 继续跑。"""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        skill_yaml = await self._load_skill_yaml(task)
        graph = await self._build_compiled(skill_yaml)
        config = {"configurable": {"thread_id": self._thread_id(task_id)}}

        final_state = await self._run_until_pause(
            graph,
            Command(resume=decision),
            config,
            task_id,
            task.user_id,
        )
        return {"state": final_state, "config": config}

    # ── 兼容老 API:resolve_hitl(gate_id, resolution, user_choice) → 内部转 resume ──
    async def resolve_hitl(
        self,
        gate_id: UUID,
        *,
        resolution: str,
        user_choice: dict[str, Any] | None = None,
    ) -> list[str]:
        """V1 hitl.py 调用入口。把 gate_id → task_id,组装 decision payload 转给 resume。

        decision 语义:
        - resolution="approved"   → graph 继续跑下游
        - resolution="modified"   → graph 走 modify(V1.5 用 rollback_to_step 实现)
        - resolution="cancelled"  → 标 final_status=failed
        - resolution="rejected"   → 同 cancelled
        """
        gate = await self.session.get(HITLGate, gate_id)
        if gate is None:
            raise ValueError(f"hitl gate {gate_id} not found")
        # 关 gate(UI 兼容)
        gate.resolution = resolution
        gate.user_choice = user_choice or {}
        gate.closed_at = datetime.now(UTC)
        await self.session.commit()
        # LangGraph resume:resolution=approved 继续;cancelled/rejected 终止;modified 暂作 approved + 标记
        if resolution in ("cancelled", "rejected"):
            decision = {"resolution": "rejected", "feedback": (user_choice or {}).get("reason", "user_cancelled")}
        elif resolution == "modified":
            # V1.5 真实现:这里应当调 rollback_to_step;V1 暂作 approved 处理
            decision = {"resolution": "approved", "modify_request": user_choice or {}}
        else:
            decision = {"resolution": "approved", "user_choice": user_choice or {}}
        out = await self.resume(gate.task_id, decision=decision)
        # 返回新派发的 step_id 列表(API 契约兼容)— 简化:从最终 state 提 next
        return list((out.get("state") or {}).get("step_results", {}).keys())

    # ── 时间旅行:V2 中断 C/D — 回滚到 step N 重做 ──
    async def rollback_to_step(
        self,
        task_id: UUID,
        *,
        target_step_id: str,
        instruction: str | None = None,
    ) -> dict[str, Any]:
        """回滚到指定 step 的 checkpoint,并清掉它和下游的状态后再跑。

        这是 V2 中断 C/D 的核心实现。LangGraph 原生支持:
          1. aget_state_history 找到 target_step 完成前的 checkpoint
          2. update_state 改写 collected_fields(承载 user instruction)+ 清下游 step
          3. 用 None invoke 让 graph 从该 checkpoint 继续
        """
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        skill_yaml = await self._load_skill_yaml(task)
        graph = await self._build_compiled(skill_yaml)
        config = {"configurable": {"thread_id": self._thread_id(task_id)}}

        # 找回滚点 — history 是 reverse-chronological,跳过 target_step 已完成的 snapshot,
        # 找到第一个 target_step 尚未完成的(= target_step 刚好待跑或下游中)
        target_checkpoint_id = None
        async for snapshot in graph.aget_state_history(config):
            results = (snapshot.values or {}).get("step_results") or {}
            target_done = (
                target_step_id in results
                and results[target_step_id].get("status") == "completed"
            )
            if not target_done:
                target_checkpoint_id = snapshot.config["configurable"].get("checkpoint_id")
                break
        if target_checkpoint_id is None:
            raise ValueError(f"无法找到 step {target_step_id!r} 的回滚点")

        anchor_config = {
            "configurable": {
                "thread_id": self._thread_id(task_id),
                "checkpoint_ns": "",
                "checkpoint_id": target_checkpoint_id,
            }
        }

        # 改写 state — 清掉 target_step 及下游的 step_results
        snap = await graph.aget_state(anchor_config)
        results = dict((snap.values or {}).get("step_results") or {})
        # 找 target_step 的下游(BFS)
        workflow = skill_yaml.get("workflow") or []
        children_map: dict[str, list[str]] = {}
        for s in workflow:
            for d in s.get("depends_on") or []:
                children_map.setdefault(d, []).append(s["step_id"])
        to_clear = {target_step_id}
        frontier = [target_step_id]
        while frontier:
            n = frontier.pop()
            for c in children_map.get(n, []):
                if c not in to_clear:
                    to_clear.add(c)
                    frontier.append(c)
        for sid in to_clear:
            results.pop(sid, None)
            reset_cursor(str(task_id), sid)
        new_collected = dict((snap.values or {}).get("collected_fields") or {})
        if instruction:
            new_collected["_user_instruction"] = instruction

        await graph.aupdate_state(
            anchor_config,
            {
                "step_results": results,  # 注意:这是完全替换(因为我们没让 reducer 处理"删除")
                "collected_fields": new_collected,
                "rollback_count": (snap.values or {}).get("rollback_count", 0) + 1,
                "final_status": None,
                "failure_reason": None,
            },
        )

        log.info(
            "lg.rollback",
            task_id=str(task_id),
            target=target_step_id,
            cleared=list(to_clear),
        )

        # 镜回 DB:把清掉的 step 标 rolled_back
        for sid in to_clear:
            await self.session.execute(
                # 注意 raw update — 简单起见
                __import__("sqlalchemy").update(TaskStep)
                .where(TaskStep.task_id == task_id, TaskStep.step_id == sid)
                .values(status="rolled_back", error_detail={"reason": "user_rollback"})
            )
        await self.session.commit()

        # 从 anchor 继续跑(invoke None 触发 graph 从该 checkpoint resume)
        final_state = await self._run_until_pause(
            graph,
            None,
            {"configurable": {"thread_id": self._thread_id(task_id)}},
            task_id,
            task.user_id,
        )
        await self.publish(
            str(task.user_id),
            {
                "type": "task_rolled_back",
                "task_id": str(task_id),
                "target_step_id": target_step_id,
                "cleared_steps": sorted(to_clear),
                "rollback_count": (final_state or {}).get("rollback_count"),
            },
        )
        return {"state": final_state, "cleared_steps": sorted(to_clear)}

    # ── 取 state / 历史(给 UI / 调试)──
    async def get_state(self, task_id: UUID) -> dict[str, Any]:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        skill_yaml = await self._load_skill_yaml(task)
        graph = await self._build_compiled(skill_yaml)
        config = {"configurable": {"thread_id": self._thread_id(task_id)}}
        snap = await graph.aget_state(config)
        return {"values": snap.values, "next": list(snap.next), "tasks": [t._asdict() if hasattr(t, "_asdict") else str(t) for t in (snap.tasks or [])]}

    async def get_history(self, task_id: UUID) -> AsyncIterator[dict[str, Any]]:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        skill_yaml = await self._load_skill_yaml(task)
        graph = await self._build_compiled(skill_yaml)
        config = {"configurable": {"thread_id": self._thread_id(task_id)}}
        async for snap in graph.aget_state_history(config):
            yield {
                "checkpoint_id": snap.config["configurable"].get("checkpoint_id"),
                "next": list(snap.next),
                "values_summary": {
                    "step_count": len((snap.values or {}).get("step_results") or {}),
                    "rollback_count": (snap.values or {}).get("rollback_count", 0),
                    "final_status": (snap.values or {}).get("final_status"),
                },
            }

    # ── 内部:跑到下一次 interrupt 或 END,边跑边把状态镜回 DB + WS 推送 ──
    async def _run_until_pause(
        self,
        graph,
        input_or_command,
        config: dict[str, Any],
        task_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        """用 astream_events 边跑边推 WS,完成后镜射 state 到 DB。"""
        last_state: dict[str, Any] = {}
        # 用 astream_events v2 拿节点开始/结束 + state 更新
        async for event in graph.astream_events(input_or_command, config, version="v2"):
            ev = event.get("event")
            name = event.get("name", "")
            data = event.get("data", {})
            if ev == "on_chain_start" and name.startswith("step_"):
                step_id = name[len("step_") :]
                await self.publish(
                    str(user_id),
                    {
                        "type": WSEventType.STEP_STARTED,
                        "task_id": str(task_id),
                        "step_id": step_id,
                    },
                )
                # Agent 状态 → working
                # (从 skill_yaml 查 agent_id 太重,运行时从节点入参 state 拿)
            elif ev == "on_chain_end" and name.startswith("step_"):
                step_id = name[len("step_") :]
                output = data.get("output") or {}
                step_results_delta = output.get("step_results") or {}
                if step_id in step_results_delta:
                    step_result = step_results_delta[step_id]
                    artifact_id = await _mirror_step_to_db(
                        self.session, task_id=task_id, step_id=step_id, step_result=step_result
                    )
                    await self.publish(
                        str(user_id),
                        {
                            "type": (
                                WSEventType.STEP_COMPLETED
                                if step_result.get("status") == "completed"
                                else WSEventType.TASK_FAILED
                            ),
                            "task_id": str(task_id),
                            "step_id": step_id,
                            "artifact": (
                                {
                                    "artifact_id": str(artifact_id) if artifact_id else None,
                                    "type": step_result.get("artifact_type"),
                                    "reference": step_result.get("artifact_ref"),
                                    "metadata": step_result.get("artifact_metadata"),
                                }
                                if step_result.get("artifact_ref")
                                else None
                            ),
                        },
                    )
                    # Agent → idle
                    if step_result.get("agent_id"):
                        try:
                            await set_agent_status(
                                self.session,
                                user_id=user_id,
                                agent_id=step_result["agent_id"],
                                status="idle",
                            )
                        except Exception as e:  # noqa: BLE001
                            log.warning("lg.set_status_failed", err=str(e))

        # 取最终 state
        snap = await graph.aget_state(config)
        last_state = snap.values or {}

        # 是否被 interrupt 暂停?
        paused = bool(snap.next)
        if paused:
            # 找最近一个 interrupt → open HITLGate row(给现有 UI 兼容)
            await self._open_hitl_for_interrupt(snap, task_id=task_id, user_id=user_id)
        else:
            # 没暂停 → 任务完成(成功/失败)
            await self._finalize_task_db(task_id, last_state)
        return last_state

    async def _open_hitl_for_interrupt(self, snap, *, task_id: UUID, user_id: UUID) -> None:
        """把 LangGraph 的 __interrupt__ 反射成 hitl_gates 行(WS UI 现成)。"""
        ints = []
        for t in snap.tasks or []:
            ints.extend(getattr(t, "interrupts", []) or [])
        if not ints:
            return
        intr = ints[0]
        payload = getattr(intr, "value", None) or {}
        step_id = payload.get("step_id") if isinstance(payload, dict) else None
        if not step_id:
            return
        existing = (
            await self.session.execute(
                select(HITLGate).where(
                    HITLGate.task_id == task_id,
                    HITLGate.step_id == step_id,
                    HITLGate.closed_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            gate = HITLGate(
                id=uuid4(),
                task_id=task_id,
                user_id=user_id,
                step_id=step_id,
                gate_type=payload.get("gate_type", "quality_review"),
                preview_artifact_id=None,
                preview_metadata=payload,
            )
            self.session.add(gate)
            await self.session.commit()
        await self.publish(
            str(user_id),
            {
                "type": WSEventType.HITL_GATE_OPENED,
                "task_id": str(task_id),
                "step_id": step_id,
                "preview": payload,
            },
        )

    async def _finalize_task_db(self, task_id: UUID, state: dict[str, Any]) -> None:
        task = await self.session.get(Task, task_id)
        if task is None:
            return
        final_status = state.get("final_status") or "completed"
        task.status = final_status
        task.completed_at = datetime.now(UTC)
        if state.get("failure_reason"):
            task.error_detail = {"failure_reason": state["failure_reason"]}
        await self.session.commit()

        # 飞轮:emit_trace
        try:
            duration_ms = (
                int((task.completed_at - task.started_at).total_seconds() * 1000)
                if task.started_at
                else None
            )
            await flywheel.emit_trace(
                self.session,
                task_id=task.id,
                user_id=task.user_id,
                skill_id=task.skill_id,
                skill_version=task.skill_version,
                duration_ms=duration_ms,
                cost_usd=None,
                failure_reason=state.get("failure_reason"),
                full_trace={"step_results": state.get("step_results") or {}},
            )
        except Exception as e:  # noqa: BLE001
            log.warning("lg.flywheel_emit_failed", err=str(e))

        await self.publish(
            str(task.user_id),
            {
                "type": (
                    WSEventType.TASK_COMPLETED
                    if final_status == "completed"
                    else WSEventType.TASK_FAILED
                ),
                "task_id": str(task_id),
                "primary_artifact": (
                    {"reference": state.get("primary_artifact_ref")}
                    if state.get("primary_artifact_ref")
                    else None
                ),
            },
        )
