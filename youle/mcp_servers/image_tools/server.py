"""mcp-image-tools:bg_remove / enhance / concat_long(PIL 真实拼接)/ quality_check / download_batch。"""

from __future__ import annotations

import asyncio
import io
import os
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import boto3
import httpx
import structlog
from botocore.client import Config
from PIL import Image

from mcp_servers._shared.http_app import make_app

log = structlog.get_logger(__name__)

OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "http://minio:9000")
OSS_BUCKET = os.getenv("OSS_BUCKET", "youle-dev")


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=OSS_ENDPOINT,
        aws_access_key_id=os.getenv("OSS_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("OSS_SECRET_KEY", "minioadmin"),
        config=Config(signature_version="s3v4"),
    )


def _read_oss(ref: str) -> bytes:
    """oss://bucket/key → bytes。"""
    if ref.startswith("oss://"):
        parsed = urlparse(ref)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    else:
        bucket = OSS_BUCKET
        key = ref
    obj = _s3().get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()


def _put_oss(key: str, data: bytes, content_type: str) -> str:
    _s3().put_object(Bucket=OSS_BUCKET, Key=key, Body=data, ContentType=content_type)
    return f"oss://{OSS_BUCKET}/{key}"


async def concat_long(arguments: dict[str, Any]) -> dict[str, Any]:
    """真实长图拼接:PIL 垂直拼接,等宽对齐。"""
    images = arguments.get("images", [])
    direction = arguments.get("direction", "vertical")
    if not images:
        return {"error": "no_images"}

    def _do() -> str:
        loaded: list[Image.Image] = []
        for ref in images:
            try:
                if str(ref).startswith("oss://"):
                    data = _read_oss(ref)
                elif str(ref).startswith(("http://", "https://")):
                    data = httpx.get(str(ref), timeout=20.0).content
                else:
                    data = _read_oss(ref)
                img = Image.open(io.BytesIO(data)).convert("RGB")
                loaded.append(img)
            except Exception as e:
                log.warning("concat.skip", ref=str(ref), err=str(e))

        if not loaded:
            raise RuntimeError("no images loaded")

        if direction == "vertical":
            target_w = max(img.width for img in loaded)
            resized = [
                (img if img.width == target_w else img.resize(
                    (target_w, int(img.height * target_w / img.width))
                ))
                for img in loaded
            ]
            total_h = sum(img.height for img in resized)
            canvas = Image.new("RGB", (target_w, total_h), (255, 255, 255))
            y = 0
            for img in resized:
                canvas.paste(img, (0, y))
                y += img.height
        else:
            target_h = max(img.height for img in loaded)
            resized = [
                (img if img.height == target_h else img.resize(
                    (int(img.width * target_h / img.height), target_h)
                ))
                for img in loaded
            ]
            total_w = sum(img.width for img in resized)
            canvas = Image.new("RGB", (total_w, target_h), (255, 255, 255))
            x = 0
            for img in resized:
                canvas.paste(img, (x, 0))
                x += img.width

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        buf.seek(0)
        key = f"long-concat/{uuid4().hex}.png"
        return _put_oss(key, buf.getvalue(), "image/png")

    try:
        oss_ref = await asyncio.to_thread(_do)
        return {"oss_ref": oss_ref, "count": len(images)}
    except Exception as e:
        log.warning("concat.failed", err=str(e))
        return {"error": str(e), "_mock": True, "oss_ref": f"oss://{OSS_BUCKET}/mock-concat.png"}


async def download_batch(arguments: dict[str, Any]) -> dict[str, Any]:
    """从 URL 列表下载图片 → 落 OSS,可选质检过滤。"""
    urls = arguments.get("urls", [])
    check_quality = bool(arguments.get("check_quality", False))
    min_width = 1080 if arguments.get("min_resolution") == "1080p" else 720

    saved: list[str] = []
    rejected = 0

    async def _fetch(u: str) -> bytes | None:
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                resp = await client.get(u, headers={"User-Agent": "youle/1.0"})
                if resp.status_code == 200:
                    return resp.content
        except Exception as e:
            log.warning("download.failed", url=u, err=str(e))
        return None

    for u in urls:
        data = await _fetch(str(u))
        if data is None:
            rejected += 1
            continue
        try:
            img = Image.open(io.BytesIO(data))
            if check_quality and img.width < min_width:
                rejected += 1
                continue
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            buf.seek(0)
            key = f"downloads/{uuid4().hex}.jpg"
            saved.append(await asyncio.to_thread(_put_oss, key, buf.getvalue(), "image/jpeg"))
        except Exception:
            rejected += 1

    return {
        "downloaded_count": len(saved),
        "rejected_count": rejected,
        "image_refs": saved,
        "oss_ref": f"oss://{OSS_BUCKET}/downloads/manifest-{uuid4().hex}/",
    }


async def bg_remove(arguments: dict[str, Any]) -> dict[str, Any]:
    # TODO(mcp-image): rembg
    return {"oss_ref": f"oss://{OSS_BUCKET}/bg-removed.png", "_mock": True}


async def enhance(arguments: dict[str, Any]) -> dict[str, Any]:
    # TODO(mcp-image): Real-ESRGAN
    return {"oss_ref": f"oss://{OSS_BUCKET}/enhanced.png", "_mock": True}


async def quality_check(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"score": 0.85, "issues": [], "suggestion": "", "_mock": True}


app = make_app(
    server_name="image-tools",
    tools={
        "concat_long": concat_long,
        "download_batch": download_batch,
        "bg_remove": bg_remove,
        "enhance": enhance,
        "quality_check": quality_check,
    },
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7002)
