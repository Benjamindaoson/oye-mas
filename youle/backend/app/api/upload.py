"""上传 API:走 OSS 预签名(铁律:OSS 凭证不下发客户端)。"""

from __future__ import annotations

from pydantic import BaseModel
from fastapi import APIRouter

from app.services.oss import oss_service

router = APIRouter()


class SignRequest(BaseModel):
    file_name: str
    content_type: str
    purpose: str = "user_upload"  # user_upload / artifact / bgm


class SignResponse(BaseModel):
    upload_url: str
    object_key: str
    expires_in: int


class ConfirmRequest(BaseModel):
    object_key: str
    size_bytes: int
    sha256: str | None = None


@router.post("/sign", response_model=SignResponse)
async def sign(body: SignRequest) -> SignResponse:
    object_key, upload_url, expires_in = await oss_service.create_presigned_put(
        file_name=body.file_name, content_type=body.content_type, purpose=body.purpose
    )
    return SignResponse(upload_url=upload_url, object_key=object_key, expires_in=expires_in)


@router.post("/confirm")
async def confirm(body: ConfirmRequest) -> dict[str, str]:
    return {"object_key": body.object_key, "status": "confirmed"}
