"""LangGraph 节点等 Agent 回执的 utility。

每个 step 节点 await `wait_for_step_result(task_id, step_id, timeout_s)` →
读 `agent_results:<task_id>` Redis Stream,过滤匹配 step_id 的回执。
"""

from __future__ import annotations

import asyncio
import json

import structlog

from app.redis_client import get_redis
from app.schemas.agent import AgentResult

log = structlog.get_logger(__name__)

# 每个 task 有自己的 stream cursor(进程内,与 LangGraph state 解耦)
_cursors: dict[str, str] = {}


async def wait_for_step_result(
    task_id: str, step_id: str, timeout_s: int
) -> AgentResult | None:
    """阻塞等指定 step 的 AgentResult。

    其它 step 的回执 不会丢,会留在 stream 给别的节点消费(下一次 read 时拿到)。
    """
    redis = await get_redis()
    stream = f"agent_results:{task_id}"
    deadline = asyncio.get_event_loop().time() + max(5, timeout_s)
    cursor_key = f"{task_id}:{step_id}"
    last_id = _cursors.get(cursor_key, "0")

    while asyncio.get_event_loop().time() < deadline:
        try:
            resp = await redis.xread({stream: last_id}, block=2000, count=10)
        except Exception as e:
            log.warning("lg.waiter.read_failed", err=str(e))
            await asyncio.sleep(1)
            continue
        if not resp:
            continue
        for _stream, messages in resp:
            for msg_id, fields in messages:
                last_id = msg_id
                _cursors[cursor_key] = last_id
                try:
                    payload = json.loads(fields["data"])
                    result = AgentResult.model_validate(payload)
                except Exception as e:
                    log.warning("lg.waiter.parse_failed", err=str(e))
                    continue
                if result.step_id == step_id:
                    return result
                # 不是本 step 的回执 — cursor 已前进,下次别的节点 read 时会从这里继续
    return None


def reset_cursor(task_id: str, step_id: str) -> None:
    """time-travel 回滚后,重置某 step 的 cursor 让它能重新等回执。"""
    _cursors.pop(f"{task_id}:{step_id}", None)
