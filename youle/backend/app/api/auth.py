"""鉴权:短信验证码 + JWT。

dev 模式(SMS_DEV_MODE=True)直接 console.log 验证码,不发真短信。
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, status
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.user import User
from app.redis_client import get_redis

router = APIRouter()
log = structlog.get_logger(__name__)


class SmsSendRequest(BaseModel):
    phone: str = Field(min_length=11, max_length=20)


class SmsLoginRequest(BaseModel):
    phone: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str


@router.post("/sms/send", status_code=status.HTTP_204_NO_CONTENT)
async def sms_send(req: SmsSendRequest) -> None:
    code = "123456" if settings.SMS_DEV_MODE else f"{secrets.randbelow(900000) + 100000:06d}"
    redis = await get_redis()
    await redis.setex(f"sms:{req.phone}", 300, code)

    if settings.SMS_DEV_MODE:
        log.info("sms.dev_code", phone=req.phone, code=code)
    else:
        # TODO(#sms): 接阿里云短信 send_sms
        log.warning("sms.not_implemented", phone=req.phone)


@router.post("/login", response_model=TokenResponse)
async def login(req: SmsLoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    redis = await get_redis()
    expected = await redis.get(f"sms:{req.phone}")
    if not expected or expected != req.code:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "验证码错误或已过期")
    await redis.delete(f"sms:{req.phone}")

    user = (await session.execute(select(User).where(User.phone == req.phone))).scalar_one_or_none()
    if user is None:
        user = User(phone=req.phone, nickname=f"用户{req.phone[-4:]}")
        session.add(user)
        await session.flush()
    user.last_login_at = datetime.now(UTC)
    await session.commit()

    token = _create_token(user.id)
    return TokenResponse(access_token=token, user_id=str(user.id))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(user_id: UUID = Depends(lambda: None)) -> TokenResponse:  # 简化:dev 跳过
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未授权")
    return TokenResponse(access_token=_create_token(user_id), user_id=str(user_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    return None


@router.get("/me")
async def me(
    user_id: UUID = Depends(lambda: None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未授权")
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return {"id": str(user.id), "phone": user.phone, "nickname": user.nickname or ""}


# ── 工具 ──
def _create_token(user_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(UTC) + timedelta(hours=settings.JWT_EXPIRE_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token 无效") from e


def get_current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    """FastAPI dependency:从 `Authorization: Bearer <jwt>` 解出 user_id。"""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "缺少 Authorization 头")
    return decode_token(authorization.split(None, 1)[1].strip())
