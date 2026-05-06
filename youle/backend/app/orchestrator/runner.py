"""TaskRunner — 主编排核心调度引擎(LangGraph-shaped)。

职责:
- 接收 start_task 信号 → 把 Skill YAML 编排成 task_steps 行 → 派发入口 step
- 接收 Agent 回执 → 写 artifact + 更新 task_step → 检查 HITL → 推进下游
- 接收 HITL 决议 → 推进或重派

设计原则(为日后迁移到完整 LangGraph 留口):
- 所有状态都在 DB 里(tasks / task_steps / artifacts / hitl_gates),无内存状态
- 派发(dispatch)与 WS 推送(publish)注入,便于测试
- 一个事件触发一次"找出可派发 step 的 sweep",纯无状态函数
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import structlog
from jinja2 import Template
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact import Artifact
from app.models.hitl_gate import HITLGate
from app.models.skill import Skill
from app.models.task import Task, TaskStep
from app.orchestrator.task_compiler import DAGCompileError, compile_to_dag
from app.schemas.agent import AgentResult, AgentTask, ArtifactRef
from app.schemas.ws import WSEventType
from app.services.agent_status import set_status as set_agent_status
from app.services.dispatcher import dispatch_task as default_dispatch
from app.services.flywheel import flywheel
from app.services.skill_loader import load_skill_by_id
from app.ws.manager import ws_manager

log = structlog.get_logger(__name__)

DispatcherFn = Callable[[AgentTask], Awaitable[Any]]
PublisherFn = Callable[[str, dict[str, Any]], Awaitable[None]]


# ── 默认 publisher = ws_manager.publish ──
async def _default_publish(user_id: str, payload: dict[str, Any]) -> None:
    await ws_manager.publish(user_id, payload)


class TaskRunner:
    """单个 FastAPI 请求或后台 reaper 周期共享一个实例。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        dispatcher: DispatcherFn | None = None,
        publisher: PublisherFn | None = None,
    ) -> None:
        self.session = session
        self.dispatch: DispatcherFn = dispatcher or default_dispatch
        self.publish: PublisherFn = publisher or _default_publish

    # ════════════════════════════════════════════════════════════════
    # 公开 API:start / handle_result / resolve_hitl
    # ════════════════════════════════════════════════════════════════

    async def start(self, task_id: UUID) -> list[str]:
        """初始化 task_steps 并派发入口 step。返回派发的 step_id 列表。"""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"task {task_id} not found")
        skill_yaml = await self._load_skill_yaml(task)

        # 启动前静态校验 DAG(环 / 缺失 dep / 重复 step_id 等 → 立即失败)
        try:
            compile_to_dag(skill_yaml)
        except DAGCompileError as e:
            await self._fail_task(task, reason={"phase": "compile", "error": str(e)})
            raise

        # 持久化所有 step(pending),便于 UI 一次性看到全貌
        existing_rows = await self.session.execute(
            select(TaskStep).where(TaskStep.task_id == task_id)
        )
        existing = {r.step_id for r in existing_rows.scalars().all()}

        for step_def in skill_yaml.get("workflow", []):
            sid = step_def["step_id"]
            if sid in existing:
                continue
            self.session.add(
                TaskStep(
                    id=uuid4(),
                    task_id=task_id,
                    step_id=sid,
                    agent_id=step_def.get("agent"),
                    task_type=step_def.get("task_type"),
                    status="pending",
                )
            )
        task.status = "executing"
        if task.started_at is None:
            task.started_at = datetime.now(UTC)
        await self.session.commit()

        return await self._dispatch_eligible(task_id)

    async def handle_result(self, result: AgentResult) -> list[str]:
        """Agent 完成 step 时调用。返回新派发的下游 step_id。"""
        # 1. 写 artifact(若有)
        artifact_db_id: UUID | None = None
        if result.output is not None:
            artifact = await self._persist_artifact(result, result.output)
            artifact_db_id = artifact.id

        # 2. 更新 task_step 行
        await self.session.execute(
            update(TaskStep)
            .where(
                TaskStep.task_id == result.task_id,
                TaskStep.step_id == result.step_id,
            )
            .values(
                status=result.status,
                completed_at=datetime.now(UTC) if result.status in ("completed", "failed") else None,
                duration_ms=result.duration_ms,
                cost_usd=Decimal(str(result.cost_usd)) if result.cost_usd is not None else None,
                model_used=result.model_used,
                output_artifact_id=artifact_db_id,
                error_detail=result.error_detail,
            )
        )
        await self.session.commit()

        # 3. WS 推送 step_completed / step_failed
        task = await self.session.get(Task, result.task_id)
        if task is None:
            log.warning("runner.task_missing", task_id=str(result.task_id))
            return []
        await self.publish(
            str(task.user_id),
            {
                "type": (
                    WSEventType.STEP_COMPLETED
                    if result.status == "completed"
                    else WSEventType.TASK_FAILED
                ),
                "task_id": str(task.id),
                "step_id": result.step_id,
                "artifact": (
                    {
                        "type": result.output.type,
                        "reference": result.output.reference,
                        "metadata": result.output.extra_metadata,
                    }
                    if result.output
                    else None
                ),
            },
        )

        # Agent 完成本步 → 切回 idle(铁律 19 拟人化:UI 实时反馈)
        try:
            row = (
                await self.session.execute(
                    select(TaskStep).where(
                        TaskStep.task_id == result.task_id, TaskStep.step_id == result.step_id
                    )
                )
            ).scalar_one_or_none()
            if row and row.agent_id:
                await set_agent_status(
                    self.session,
                    user_id=task.user_id,
                    agent_id=row.agent_id,
                    status="idle",
                    conversation_id=task.conversation_id,
                )
        except Exception as e:
            log.warning("runner.set_status_idle_failed", err=str(e))

        if result.status == "failed":
            await self._fail_task(task, reason=result.error_detail or {"step": result.step_id})
            return []

        if result.status == "pending_external":
            # video_compose 等 Celery 任务 — 不推进,等待回调
            log.info("runner.pending_external", task_id=str(task.id), step_id=result.step_id)
            return []

        # 4. 检查该 step 是否有 hitl_gate(开了就不推进,等用户)
        skill_yaml = await self._load_skill_yaml(task)
        step_def = self._find_step(skill_yaml, result.step_id)
        if step_def and step_def.get("hitl_gate") and result.status == "completed":
            await self._open_hitl(
                task=task,
                step_id=result.step_id,
                gate_config=step_def["hitl_gate"],
                preview_artifact_id=artifact_db_id,
            )
            return []

        # 5. 推进
        return await self._dispatch_eligible(result.task_id)

    async def resolve_hitl(
        self,
        gate_id: UUID,
        *,
        resolution: str,
        user_choice: dict[str, Any] | None = None,
    ) -> list[str]:
        """用户在 HITL gate 上做了决定 — 推进 / 重派 / 取消。

        - approved:推进下游
        - modified:重派被审 step(target_step 或当前 step)
        - rolled_back:V1 不支持,抛 NotImplementedError(铁律 14)
        """
        gate = await self.session.get(HITLGate, gate_id)
        if gate is None:
            raise ValueError(f"hitl gate {gate_id} not found")
        if gate.closed_at is not None:
            log.warning("runner.gate_already_closed", gate_id=str(gate_id))
            return []

        if resolution == "rolled_back":
            raise NotImplementedError("V1 不支持回滚到第 N 步(中断 C);V2 范围。")

        gate.resolution = resolution
        gate.user_choice = user_choice
        gate.closed_at = datetime.now(UTC)
        await self.session.commit()

        task = await self.session.get(Task, gate.task_id)
        if task is not None:
            await self.publish(
                str(task.user_id),
                {
                    "type": WSEventType.HITL_GATE_CLOSED,
                    "task_id": str(gate.task_id),
                    "resolution": resolution,
                },
            )

        if resolution == "modified":
            # 找 target_step 或当前 step,把它 reset 为 pending,重新派发
            target = (user_choice or {}).get("target_step", gate.step_id)
            await self._reset_steps_from(gate.task_id, target)
            return await self._dispatch_eligible(gate.task_id)

        # approved / cancelled → 推进
        if resolution == "cancelled":
            task = await self.session.get(Task, gate.task_id)
            if task is not None:
                task.status = "cancelled"
                task.cancelled_at = datetime.now(UTC)
                await self.session.commit()
            return []

        return await self._dispatch_eligible(gate.task_id)

    # ════════════════════════════════════════════════════════════════
    # 内部:调度循环
    # ════════════════════════════════════════════════════════════════

    async def _dispatch_eligible(self, task_id: UUID) -> list[str]:
        """找所有 status=pending 且 depends_on 全 completed 的 step,派发它们。"""
        task = await self.session.get(Task, task_id)
        if task is None:
            return []
        skill_yaml = await self._load_skill_yaml(task)
        all_steps = skill_yaml.get("workflow", [])

        rows = await self.session.execute(
            select(TaskStep).where(TaskStep.task_id == task_id)
        )
        step_status: dict[str, str] = {}
        completed_artifacts: dict[str, Artifact] = {}
        for r in rows.scalars().all():
            step_status[r.step_id] = r.status
            if r.status == "completed" and r.output_artifact_id:
                art = await self.session.get(Artifact, r.output_artifact_id)
                if art is not None:
                    completed_artifacts[r.step_id] = art

        # 是否有 step 因为 HITL gate 开着而被卡(此 step 已 completed,但 gate 未 close)
        # 在这种情况下,这个 step 的下游不能派发
        blocked_by_open_gate: set[str] = set()
        open_gates = await self.session.execute(
            select(HITLGate).where(HITLGate.task_id == task_id, HITLGate.closed_at.is_(None))
        )
        for g in open_gates.scalars().all():
            blocked_by_open_gate.add(g.step_id)

        dispatched: list[str] = []
        for step_def in all_steps:
            sid = step_def["step_id"]
            if step_status.get(sid) != "pending":
                continue
            depends = step_def.get("depends_on", [])
            if any(d in blocked_by_open_gate for d in depends):
                continue
            if not all(step_status.get(d) == "completed" for d in depends):
                continue

            agent_task = self._build_agent_task(
                task=task,
                skill_yaml=skill_yaml,
                step_def=step_def,
                completed_artifacts=completed_artifacts,
            )
            await self.dispatch(agent_task)
            await self.session.execute(
                update(TaskStep)
                .where(TaskStep.task_id == task_id, TaskStep.step_id == sid)
                .values(status="running", started_at=datetime.now(UTC))
            )
            # 快路径:Agent 进入 working 状态 + WS 推送(铁律 19 拟人化)
            try:
                await set_agent_status(
                    self.session,
                    user_id=task.user_id,
                    agent_id=step_def["agent"],
                    status="working",
                    conversation_id=task.conversation_id,
                )
            except Exception as e:
                log.warning("runner.set_status_failed", err=str(e))
            await self.publish(
                str(task.user_id),
                {
                    "type": WSEventType.STEP_STARTED,
                    "task_id": str(task_id),
                    "step_id": sid,
                    "agent_id": step_def["agent"],
                },
            )
            dispatched.append(sid)
            log.info("runner.dispatched", task_id=str(task_id), step_id=sid)

        await self.session.commit()

        # 是否全部完成
        if not dispatched:
            await self._maybe_complete_task(task_id, all_steps, step_status)

        return dispatched

    async def _maybe_complete_task(
        self,
        task_id: UUID,
        all_steps: list[dict[str, Any]],
        step_status: dict[str, str],
    ) -> None:
        if not all(step_status.get(s["step_id"]) == "completed" for s in all_steps):
            return
        task = await self.session.get(Task, task_id)
        if task is None or task.status == "completed":
            return
        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        # 找 primary_artifact
        skill_yaml = await self._load_skill_yaml(task)
        primary_step = (skill_yaml.get("delivery") or {}).get("primary_artifact")
        primary_artifact_id = None
        if primary_step:
            row = await self.session.execute(
                select(TaskStep).where(
                    TaskStep.task_id == task_id, TaskStep.step_id == primary_step
                )
            )
            ts = row.scalar_one_or_none()
            if ts and ts.output_artifact_id:
                primary_artifact_id = ts.output_artifact_id
        await self.session.commit()
        # 飞轮信号 1:工作流轨迹(成功) — Reflexion 不会触发(failure_reason 为空)
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
                cost_usd=None,  # 累计 cost 由 ingestion runner 汇总(不阻塞主流程)
                full_trace=await self._collect_trace_summary(task.id),
            )
        except Exception as e:
            log.warning("runner.flywheel_emit_failed", task_id=str(task_id), err=str(e))
        await self.publish(
            str(task.user_id),
            {
                "type": WSEventType.TASK_COMPLETED,
                "task_id": str(task_id),
                "primary_artifact": (
                    {"artifact_id": str(primary_artifact_id)} if primary_artifact_id else None
                ),
            },
        )
        log.info("runner.task_completed", task_id=str(task_id))

    async def _collect_trace_summary(self, task_id: UUID) -> dict[str, Any]:
        """采集任务 step 摘要,作为 trace_excerpt(供 Reflexion / Skill 草稿)。"""
        rows = await self.session.execute(
            select(TaskStep).where(TaskStep.task_id == task_id)
        )
        return {
            "steps": [
                {
                    "step_id": r.step_id,
                    "agent_id": r.agent_id,
                    "task_type": r.task_type,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    "error": r.error_detail,
                }
                for r in rows.scalars().all()
            ]
        }

    async def _fail_task(self, task: Task, *, reason: dict[str, Any]) -> None:
        task.status = "failed"
        task.completed_at = datetime.now(UTC)
        task.error_detail = reason
        await self.session.commit()
        # 飞轮信号 1+3:失败 trace 触发 Reflexion(由 emit_trace 在 failure_reason 非空时自动 emit)
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
                failure_reason=str(reason)[:500],
                full_trace=await self._collect_trace_summary(task.id),
            )
        except Exception as e:
            log.warning("runner.flywheel_emit_failed", task_id=str(task.id), err=str(e))
        await self.publish(
            str(task.user_id),
            {
                "type": WSEventType.TASK_FAILED,
                "task_id": str(task.id),
                "error": reason,
            },
        )

    # ════════════════════════════════════════════════════════════════
    # 内部:HITL
    # ════════════════════════════════════════════════════════════════

    async def _open_hitl(
        self,
        *,
        task: Task,
        step_id: str,
        gate_config: dict[str, Any],
        preview_artifact_id: UUID | None,
    ) -> HITLGate:
        gate = HITLGate(
            id=uuid4(),
            task_id=task.id,
            step_id=step_id,
            gate_type=gate_config.get("type", "version_select"),
            timeout_seconds=int(gate_config.get("timeout_seconds", 600)),
            preview_artifact_id=preview_artifact_id,
            extra_metadata={"actions": gate_config.get("actions")},
        )
        self.session.add(gate)
        await self.session.commit()
        await self.session.refresh(gate)

        await self.publish(
            str(task.user_id),
            {
                "type": WSEventType.HITL_GATE_OPENED,
                "task_id": str(task.id),
                "gate": {
                    "id": str(gate.id),
                    "step_id": step_id,
                    "gate_type": gate.gate_type,
                    "timeout_seconds": gate.timeout_seconds,
                    "actions": gate_config.get("actions"),
                },
                "preview_artifact": (
                    {"artifact_id": str(preview_artifact_id)} if preview_artifact_id else None
                ),
            },
        )
        log.info(
            "runner.hitl_opened",
            task_id=str(task.id),
            step_id=step_id,
            gate_type=gate.gate_type,
        )
        return gate

    async def _reset_steps_from(self, task_id: UUID, target_step: str) -> None:
        """把 target_step 重置为 pending(modified 重派)。简化版:只 reset 单个 step。"""
        await self.session.execute(
            update(TaskStep)
            .where(TaskStep.task_id == task_id, TaskStep.step_id == target_step)
            .values(
                status="pending",
                started_at=None,
                completed_at=None,
                output_artifact_id=None,
                error_detail=None,
            )
        )
        await self.session.commit()

    # ════════════════════════════════════════════════════════════════
    # 内部:Skill / 模板渲染 / AgentTask 构造
    # ════════════════════════════════════════════════════════════════

    async def _load_skill_yaml(self, task: Task) -> dict[str, Any]:
        if task.skill_id is None:
            raise ValueError(f"task {task.id} has no skill_id")
        skill = await self.session.get(Skill, task.skill_id)
        if skill is None:
            raise ValueError(f"skill {task.skill_id} not found in DB")
        try:
            return load_skill_by_id(skill.skill_id)
        except KeyError:
            import yaml as _yaml

            return _yaml.safe_load(skill.yaml_content)  # type: ignore[no-any-return]

    @staticmethod
    def _find_step(skill_yaml: dict[str, Any], step_id: str) -> dict[str, Any] | None:
        for s in skill_yaml.get("workflow", []):
            if s["step_id"] == step_id:
                return s  # type: ignore[no-any-return]
        return None

    def _build_agent_task(
        self,
        *,
        task: Task,
        skill_yaml: dict[str, Any],
        step_def: dict[str, Any],
        completed_artifacts: dict[str, Artifact],
    ) -> AgentTask:
        """渲染 prompt_template + 把 deps 产物注入 inputs(关键的依赖图传递)。"""
        # 模板上下文:用户填写字段 + 上游 step 的 output(reference / metadata)
        context: dict[str, Any] = dict(task.collected_fields or {})
        for dep_id in step_def.get("depends_on", []):
            artifact = completed_artifacts.get(dep_id)
            if artifact is None:
                continue
            context[dep_id] = {
                "output": artifact.reference,
                "artifact_id": str(artifact.id),
                "metadata": artifact.extra_metadata or {},
            }

        prompt_tpl = step_def.get("prompt_template", "")
        rendered = Template(prompt_tpl).render(**context) if prompt_tpl else ""

        # inputs 包含:原始 inputs / _prompt / 每个 dep 的 reference
        inputs: dict[str, Any] = dict(step_def.get("inputs", {}))
        if rendered:
            inputs["_prompt"] = rendered
        for dep_id in step_def.get("depends_on", []):
            artifact = completed_artifacts.get(dep_id)
            if artifact is None:
                continue
            inputs[dep_id] = {
                "reference": artifact.reference,
                "metadata": artifact.extra_metadata or {},
            }

        return AgentTask(
            task_id=task.id,
            step_id=step_def["step_id"],
            agent_id=step_def["agent"],  # type: ignore[arg-type]
            task_type=step_def["task_type"],
            user_id=task.user_id,
            conversation_id=task.conversation_id,
            inputs=inputs,
            parameters=step_def.get("parameters", {}),
            routing_hints=step_def.get("routing_hints", {}),
            skill_id=skill_yaml.get("skill_id"),
            skill_version=str(skill_yaml.get("version", "1.0")),
            timeout_seconds=int(step_def.get("timeout", 60)),
        )

    async def _persist_artifact(self, result: AgentResult, output: ArtifactRef) -> Artifact:
        # 找 source conversation
        task = await self.session.get(Task, result.task_id)
        if task is None:
            raise ValueError(f"task {result.task_id} missing")
        # is_final = 该 step 是否是 delivery.primary_artifact
        is_final = False
        try:
            skill_yaml = await self._load_skill_yaml(task)
            primary = (skill_yaml.get("delivery") or {}).get("primary_artifact")
            is_final = primary == result.step_id
        except Exception as e:
            log.warning("runner.is_final_check_failed", task_id=str(task.id), err=str(e))

        artifact = Artifact(
            id=output.artifact_id,
            user_id=task.user_id,
            source_conversation_id=task.conversation_id,
            source_task_id=task.id,
            source_step_id=result.step_id,
            type=output.type,
            is_final=is_final,
            reference=output.reference,
            extra_metadata=output.extra_metadata or {},
        )
        self.session.add(artifact)
        await self.session.commit()
        await self.session.refresh(artifact)
        return artifact
