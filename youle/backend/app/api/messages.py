"""主编排消息入口 — 端到端胶水(铁律 1:单一调度者)。

POST /api/conversations/:id/messages
  → 写 messages
  → 9 子模块:意图 → 模式切换检测 → 配额规则 → Skill 匹配 → 输入校验 → 澄清 OR 编排
  → Task 持久化后交给 TaskRunner.start(task_id),由 runner 推进整图
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.conversation import Conversation
from app.models.task import Task
from app.orchestrator.clarification import generate_clarification
from app.orchestrator.input_validator import validate_inputs
from app.orchestrator.intent import understand_intent
from app.orchestrator.mode_manager import consumes_task_quota, detect_mode_switch
from app.orchestrator.runner import TaskRunner
from app.orchestrator.skill_match import match_skill
from app.schemas.ws import WSEventType
from app.services.conversation import append_message
from app.services.skill_loader import load_skill_by_id
from app.ws.manager import ws_manager

router = APIRouter()
log = structlog.get_logger(__name__)


class SendMessageRequest(BaseModel):
    content: str
    role: str = "user"


class SendMessageResponse(BaseModel):
    message_id: UUID
    decision: str  # task_started / clarification_required / chitchat / mode_switched
    payload: dict[str, Any]


@router.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: UUID,
    body: SendMessageRequest,
    session: AsyncSession = Depends(get_session),
) -> SendMessageResponse:
    conv = await session.get(Conversation, conversation_id)
    if conv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")

    user_msg = await append_message(
        session, conversation_id=conv.id, role=body.role, content=body.content
    )

    # 中断 I:模式切换检测
    if conv.mode == "group" and conv.work_mode is not None:
        sig = await detect_mode_switch(
            current_mode=conv.work_mode,  # type: ignore[arg-type]
            conversation_name=conv.name,
            message=body.content,
        )
        if sig.switch_to and sig.switch_to != conv.work_mode and sig.confidence >= 0.7:
            old_mode = conv.work_mode
            conv.work_mode = sig.switch_to
            await session.commit()
            await ws_manager.publish(
                str(conv.user_id),
                {
                    "type": WSEventType.WORK_MODE_CHANGED,
                    "conversation_id": str(conv.id),
                    "from": old_mode,
                    "to": sig.switch_to,
                },
            )
            return SendMessageResponse(
                message_id=user_msg.id,
                decision="mode_switched",
                payload={"from": old_mode, "to": sig.switch_to},
            )

    # 意图理解
    intent = await understand_intent(user_message=body.content)
    if intent.intent_type != "task_request":
        return SendMessageResponse(
            message_id=user_msg.id,
            decision="chitchat",
            payload={"intent": intent.model_dump()},
        )

    # 铁律 20:Plan/Ask 不消耗任务配额
    if not consumes_task_quota(conv.work_mode):  # type: ignore[arg-type]
        return SendMessageResponse(
            message_id=user_msg.id,
            decision="chitchat",
            payload={
                "intent": intent.model_dump(),
                "note": "Plan/Ask 模式仅讨论,不派活;切到 Auto 才执行",
            },
        )

    # Skill 匹配
    skill = await match_skill(
        session=session, user_message=body.content, intent=intent.model_dump()
    )
    if skill is None:
        return SendMessageResponse(
            message_id=user_msg.id,
            decision="chitchat",
            payload={"reason": "no_skill_matched", "intent": intent.model_dump()},
        )

    # 加载 YAML
    try:
        skill_yaml = load_skill_by_id(skill.skill_id)
    except KeyError:
        import yaml as _yaml

        skill_yaml = _yaml.safe_load(skill.yaml_content)

    # 输入校验
    validation = validate_inputs(
        inputs_schema=skill_yaml.get("inputs_schema", []),
        collected_fields=intent.entities,
    )
    if not validation.is_complete:
        clar = generate_clarification(validation.missing_fields)
        return SendMessageResponse(
            message_id=user_msg.id,
            decision="clarification_required",
            payload={
                "skill_id": skill.skill_id,
                "clarification": clar.model_dump() if clar else None,
            },
        )

    # 创建 Task,交给 TaskRunner.start
    task = Task(
        id=uuid4(),
        user_id=conv.user_id,
        conversation_id=conv.id,
        skill_id=skill.id,
        skill_version=str(skill_yaml.get("version", "1.0")),
        status="pending",
        collected_fields=validation.filled_fields,
        progress={"current": 0, "total": len(skill_yaml.get("workflow", []))},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    runner = TaskRunner(session)
    dispatched = await runner.start(task.id)

    log.info(
        "messages.task_started",
        task_id=str(task.id),
        skill=skill.skill_id,
        dispatched=dispatched,
    )
    return SendMessageResponse(
        message_id=user_msg.id,
        decision="task_started",
        payload={
            "task_id": str(task.id),
            "skill_id": skill.skill_id,
            "step_count": len(skill_yaml.get("workflow", [])),
            "dispatched": dispatched,
        },
    )
