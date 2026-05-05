"""Agent 通信契约(与 backend.app.schemas.agent 对齐)。"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AgentId = Literal["agent_1", "agent_2", "agent_3", "agent_4"]
AgentStatus = Literal["pending", "running", "completed", "failed", "pending_external"]

QUEUE_MAP: dict[AgentId, str] = {
    "agent_1": "agent_tasks:text",
    "agent_2": "agent_tasks:document",
    "agent_3": "agent_tasks:image",
    "agent_4": "agent_tasks:av",
}


class ArtifactRef(BaseModel):
    artifact_id: UUID
    type: str
    reference: str
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    task_id: UUID
    step_id: str
    agent_id: AgentId
    task_type: str
    user_id: UUID
    conversation_id: UUID
    inputs: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    routing_hints: dict[str, Any] = Field(default_factory=dict)
    skill_id: str | None = None
    skill_version: str | None = None
    timeout_seconds: int = 60


class AgentResult(BaseModel):
    task_id: UUID
    step_id: str
    status: AgentStatus
    output: ArtifactRef | None = None
    extra_artifacts: list[ArtifactRef] = Field(default_factory=list)
    cost_usd: float | None = None
    duration_ms: int | None = None
    model_used: str | None = None
    error_detail: dict[str, Any] | None = None
    external_workflow_id: str | None = None
