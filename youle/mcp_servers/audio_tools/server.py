"""mcp-audio-tools:tts / asr / bgm_match。

TTS 优先走 LiteLLM(Volcengine);无 key 时降级 — 用 pyttsx3 或 silent mp3 占位。
"""

from __future__ import annotations

import asyncio
import io
import os
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
import httpx
import structlog
from botocore.client import Config

from mcp_servers._shared.http_app import make_app

log = structlog.get_logger(__name__)

OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "http://minio:9000")
OSS_BUCKET = os.getenv("OSS_BUCKET", "youle-dev")
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm-proxy:4000")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "")


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=OSS_ENDPOINT,
        aws_access_key_id=os.getenv("OSS_ACCESS_KEY", "minioadmin"),
        aws_secret_access_key=os.getenv("OSS_SECRET_KEY", "minioadmin"),
        config=Config(signature_version="s3v4"),
    )


def _put_oss(key: str, data: bytes, content_type: str) -> str:
    _s3().put_object(Bucket=OSS_BUCKET, Key=key, Body=data, ContentType=content_type)
    return f"oss://{OSS_BUCKET}/{key}"


async def tts(arguments: dict[str, Any]) -> dict[str, Any]:
    """文字转语音。优先 LiteLLM;无 key 时返回 silent mp3(让 video_compose 不崩)。"""
    text = arguments.get("text", "")
    voice = arguments.get("voice", "female_warm")
    if not text:
        return {"error": "tts: text 必填"}

    # 优先 LiteLLM /v1/audio/speech
    if LITELLM_API_KEY and not os.getenv("LITELLM_MOCK", "true").lower() == "true":
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{LITELLM_URL}/v1/audio/speech",
                    headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
                    json={
                        "model": "volcengine-tts",
                        "input": text,
                        "voice": voice,
                        "response_format": "mp3",
                    },
                )
                if resp.status_code == 200:
                    audio_bytes = resp.content
                    key = f"audio/tts-{uuid4().hex}.mp3"
                    oss_ref = await asyncio.to_thread(_put_oss, key, audio_bytes, "audio/mpeg")
                    return {
                        "oss_ref": oss_ref,
                        "duration_seconds": _estimate_tts_duration(text),
                        "size_bytes": len(audio_bytes),
                    }
        except Exception as e:
            log.warning("tts.litellm_failed", err=str(e))

    # 降级:生成静音 mp3(让 pipeline 不崩,产物可识别为占位)
    silent = await asyncio.to_thread(_make_silent_mp3, _estimate_tts_duration(text))
    key = f"audio/tts-silent-{uuid4().hex}.mp3"
    oss_ref = await asyncio.to_thread(_put_oss, key, silent, "audio/mpeg")
    return {
        "oss_ref": oss_ref,
        "duration_seconds": _estimate_tts_duration(text),
        "size_bytes": len(silent),
        "_fallback": "silent",
    }


def _estimate_tts_duration(text: str) -> int:
    """中文 ~3.5 字/秒,英文 ~2.5 词/秒。"""
    chinese_chars = sum(1 for c in text if "一" <= c <= "鿿")
    other = len(text) - chinese_chars
    return max(3, int(chinese_chars / 3.5 + other / 12))


def _make_silent_mp3(duration_seconds: int) -> bytes:
    """用 ffmpeg 生成静音 mp3。降级路径。"""
    import subprocess

    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "silent.mp3"
        cmd = [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=44100:cl=mono:d={duration_seconds}",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "64k",
            "-y",
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
            return out.read_bytes()
        except Exception:
            # 完全没 ffmpeg 也不挂:返回最小有效 mp3 头(空帧)
            return b"\xff\xfb\x90\x00" + b"\x00" * 1024


async def asr(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"text": "[mock] asr transcript", "_mock": True}


async def bgm_match(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"oss_ref": "oss://bgm/sample.mp3", "_mock": True}


app = make_app(
    server_name="audio-tools",
    tools={"tts": tts, "asr": asr, "bgm_match": bgm_match},
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7004)
