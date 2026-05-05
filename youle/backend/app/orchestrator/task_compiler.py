"""子模块 5:任务编排器(纯程序)。

把 Skill YAML + collected_fields → LangGraph StateGraph(可执行)。
本文件提供 stub:加载 YAML、Jinja2 渲染 prompt_template、组装 AgentTask 列表。
完整 LangGraph 接入在 Sprint 4。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from jinja2 import Template
from pydantic import BaseModel

from app.schemas.agent import AgentTask


class CompiledStep(BaseModel):
    step_id: str
    agent_id: str
    task_type: str
    inputs: dict[str, Any]
    parameters: dict[str, Any]
    timeout_seconds: int
    depends_on: list[str]
    hitl_gate: dict[str, Any] | None = None


def compile_task(
    *,
    skill_yaml: dict[str, Any],
    collected_fields: dict[str, Any],
    user_id: UUID,
    conversation_id: UUID,
    task_id: UUID | None = None,
) -> tuple[UUID, list[CompiledStep], list[AgentTask]]:
    task_id = task_id or uuid4()
    workflow = skill_yaml.get("workflow", [])
    compiled: list[CompiledStep] = []
    agent_tasks: list[AgentTask] = []

    for step in workflow:
        prompt_tpl = step.get("prompt_template", "")
        rendered_prompt = Template(prompt_tpl).render(**collected_fields) if prompt_tpl else ""
        compiled_step = CompiledStep(
            step_id=step["step_id"],
            agent_id=step["agent"],
            task_type=step["task_type"],
            inputs={**step.get("inputs", {}), "_prompt": rendered_prompt} if rendered_prompt else step.get("inputs", {}),
            parameters=step.get("parameters", {}),
            timeout_seconds=step.get("timeout", 60),
            depends_on=step.get("depends_on", []),
            hitl_gate=step.get("hitl_gate"),
        )
        compiled.append(compiled_step)
        agent_tasks.append(
            AgentTask(
                task_id=task_id,
                step_id=compiled_step.step_id,
                agent_id=compiled_step.agent_id,  # type: ignore[arg-type]
                task_type=compiled_step.task_type,
                user_id=user_id,
                conversation_id=conversation_id,
                inputs=compiled_step.inputs,
                parameters=compiled_step.parameters,
                routing_hints=step.get("routing_hints", {}),
                skill_id=skill_yaml.get("skill_id"),
                skill_version=skill_yaml.get("version"),
                timeout_seconds=compiled_step.timeout_seconds,
            )
        )
    return task_id, compiled, agent_tasks
