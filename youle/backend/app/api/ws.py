"""WebSocket 端点 + 心跳。"""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.ws.manager import ws_manager

router = APIRouter()
log = structlog.get_logger(__name__)


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str | None = None) -> None:
    """token=xxx 鉴权;dev 阶段允许匿名。"""
    user_id = await _resolve_user(token)
    await websocket.accept()
    await ws_manager.register(user_id, websocket)
    log.info("ws.connect", user_id=user_id)

    try:
        while True:
            recv = asyncio.create_task(websocket.receive_text())
            done, pending = await asyncio.wait(
                {recv}, timeout=settings.WS_HEARTBEAT_SECONDS
            )
            if recv in done:
                msg = recv.result()
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            else:
                recv.cancel()
                await websocket.send_json({"type": "pong"})  # 心跳
    except WebSocketDisconnect:
        log.info("ws.disconnect", user_id=user_id)
    finally:
        await ws_manager.unregister(user_id, websocket)


async def _resolve_user(token: str | None) -> str:
    """dev: 没 token 用 anonymous;staging+: 解 JWT。"""
    if token is None or settings.is_dev:
        return "anonymous"
    from app.api.auth import decode_token

    return str(decode_token(token))
