"""Agent 端 LLM 客户端(铁律 7:走 LiteLLM,禁止 import openai/anthropic)。

backend.app.router 是后端用的;Agent 进程独立,这里复制最小必要逻辑(同样行为)。
两边路由策略由 LiteLLM Proxy 集中管理;客户端只是 HTTP 包装。
"""

from __future__ import annotations

import os
from typing import Any, Literal

import httpx
import structlog

log = structlog.get_logger(__name__)

LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm-proxy:4000")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY", "sk-mock-1234")
LITELLM_MOCK = os.getenv("LITELLM_MOCK", "true").lower() == "true"

# Agent 端 task_type → 主备模型(对齐 docs/4_附录/模型路由表.md)
AGENT_ROUTING: dict[str, dict[str, list[str]]] = {
    # Agent 1
    "short_writing": {"primary": ["deepseek-v4-flash"], "fallback": ["deepseek-v4-pro"]},
    "long_writing": {"primary": ["kimi-k2"], "fallback": ["deepseek-v4-pro", "claude-sonnet-4-6"]},
    "structured_writing": {"primary": ["deepseek-v4-pro"], "fallback": ["kimi-k2"]},
    "short_video_script": {"primary": ["deepseek-v4-pro"], "fallback": ["kimi-k2", "claude-sonnet-4-6"]},
    "web_search": {"primary": ["claude-sonnet-4-6"], "fallback": ["gpt-5"]},
    "version_compare": {"primary": ["deepseek-v4-flash"], "fallback": ["kimi-k2"]},
    # Agent 3
    "image_generate": {"primary": ["gpt-image-2"], "fallback": ["seedream-3"]},
    "batch_generate": {"primary": ["gpt-image-2"], "fallback": ["seedream-3"]},
    "image_quality_check": {"primary": ["gpt-5-vision"], "fallback": ["claude-sonnet-vision"]},
    "style_extract": {"primary": ["claude-sonnet-vision"], "fallback": ["gpt-5-vision"]},
    # Agent 4
    "tts_generate": {"primary": ["volcengine-tts"], "fallback": ["aliyun-tts"]},
    "text_to_video": {"primary": ["veo-3"], "fallback": ["seedance-2", "kling-2"]},
    "image_to_video": {"primary": ["seedance-2"], "fallback": ["kling-2"]},
}


class LLMResponse:
    def __init__(self, raw: dict[str, Any]) -> None:
        self.raw = raw

    @property
    def content(self) -> str:
        return self.raw["choices"][0]["message"]["content"]

    @property
    def model(self) -> str:
        return self.raw.get("model", "unknown")

    @property
    def usage(self) -> dict[str, int]:
        return self.raw.get("usage", {})

    @property
    def cost_usd(self) -> float | None:
        return self.raw.get("response_cost")


_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=LITELLM_URL,
            timeout=httpx.Timeout(120.0, connect=5.0),
            headers={"Authorization": f"Bearer {LITELLM_API_KEY}"},
        )
    return _http


async def complete(
    *,
    task_type: str,
    messages: list[dict[str, Any]],
    routing_hints: dict[str, Any] | None = None,
    response_format: dict[str, str] | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> LLMResponse:
    routing = AGENT_ROUTING.get(task_type, {})
    primary = (routing_hints or {}).get("primary") or (routing.get("primary") or ["deepseek-v4-flash"])[0]

    if LITELLM_MOCK:
        return LLMResponse(_mock_response(task_type, primary))

    payload: dict[str, Any] = {
        "model": primary,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if response_format:
        payload["response_format"] = response_format

    log.debug("agent.llm", task_type=task_type, model=primary)
    resp = await _client().post("/v1/chat/completions", json=payload)
    resp.raise_for_status()
    return LLMResponse(resp.json())


async def stream(
    *,
    task_type: str,
    messages: list[dict[str, Any]],
    routing_hints: dict[str, Any] | None = None,
    temperature: float = 0.7,
):
    """流式输出 — Agent 1 long_writing 用,逐 chunk yield。"""
    routing = AGENT_ROUTING.get(task_type, {})
    primary = (routing_hints or {}).get("primary") or (routing.get("primary") or ["deepseek-v4-flash"])[0]

    if LITELLM_MOCK:
        for chunk in [f"[mock-{task_type}] ", "段一。", "段二。", "段三。"]:
            yield chunk
        return

    async with _client().stream(
        "POST",
        "/v1/chat/completions",
        json={"model": primary, "messages": messages, "temperature": temperature, "stream": True},
    ) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: ") and line[6:] != "[DONE]":
                import json as _json

                try:
                    data = _json.loads(line[6:])
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    continue


def _mock_response(task_type: str, model: str) -> dict[str, Any]:
    if task_type == "web_search":
        body = '{"results": [{"title":"mock 反诈案例","url":"https://example.com/1","snippet":"..."}]}'
    elif task_type in {"long_writing", "short_video_script"}:
        body = (
            "【反诈视频脚本 - mock】\n"
            "钩子:你接到陌生电话,对方说你涉嫌洗钱,要求转账...\n"
            "案例:2026 年某地张大妈被骗 30 万。\n"
            "呼吁:遇陌生电话 96110 一键查询。"
        )
    elif task_type == "structured_writing":
        body = '[{"label":"主标题","content":"..."},{"label":"段二","content":"..."}]'
    elif task_type == "image_quality_check":
        body = '{"score": 0.85, "issues": [], "suggestion": ""}'
    else:
        body = f"[mock-{task_type}] result"
    return {
        "id": "chatcmpl-mock",
        "model": model,
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": body}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150},
        "response_cost": 0.0001,
    }


async def aclose() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None
