"""LiteLLM 客户端封装(铁律 7 / ADR-007)。

铁律:禁止 `import openai` / `import anthropic`。所有模型调用走 `app.router.complete`。

dev 环境(LITELLM_MOCK=True)走 mock-litellm 容器,返回固定文本。
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
import structlog

from app.config import settings

log = structlog.get_logger(__name__)

# 路由策略:task_type → 主备模型(详见 docs/4_附录/模型路由表.md)
TASK_TYPE_ROUTING: dict[str, dict[str, list[str]]] = {
    # ── L1 编排层 ──
    "intent_understanding": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5", "gpt-5-mini"]},
    "skill_matching": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},
    "interrupt_classification": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5", "gpt-5-mini"]},
    "brief_update": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},
    "hitl_decision_parsing": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},
    "rollback_target_compute": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},
    "mcp_tool_decision": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},
    "work_mode_switch": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},

    # ── L2 文字 ──
    "short_writing": {"primary": ["deepseek-v4-flash"], "fallback": ["deepseek-v4-pro", "claude-haiku-4-5"]},
    "long_writing": {"primary": ["kimi-k2"], "fallback": ["deepseek-v4-pro", "claude-sonnet-4-6"]},
    "structured_writing": {"primary": ["deepseek-v4-pro"], "fallback": ["kimi-k2", "claude-sonnet-4-6"]},
    "short_video_script": {"primary": ["deepseek-v4-pro"], "fallback": ["kimi-k2", "claude-sonnet-4-6"]},
    "short_video_hook": {"primary": ["claude-sonnet-4-6"], "fallback": ["gpt-5", "deepseek-v4-pro"]},
    "web_search": {"primary": ["claude-sonnet-4-6"], "fallback": ["gpt-5"]},
    "version_compare": {"primary": ["deepseek-v4-flash"], "fallback": ["kimi-k2"]},
    "summarization": {"primary": ["deepseek-v4-flash"], "fallback": ["kimi-k2"]},
    "analysis": {"primary": ["claude-sonnet-4-6"], "fallback": ["deepseek-v4-pro", "gpt-5"]},
    "translation": {"primary": ["deepseek-v4-pro"], "fallback": ["kimi-k2"]},
    "polish": {"primary": ["deepseek-v4-flash"], "fallback": ["kimi-k2"]},
    "extraction": {"primary": ["deepseek-v4-flash"], "fallback": ["claude-haiku-4-5"]},

    # ── L2 图 ──
    "image_generate": {"primary": ["gpt-image-2"], "fallback": ["seedream-3", "nano-banana-2"]},
    "batch_generate": {"primary": ["gpt-image-2"], "fallback": ["seedream-3", "nano-banana-2"]},
    "image_describe": {"primary": ["claude-sonnet-vision"], "fallback": ["gpt-5-vision"]},
    "image_quality_check": {"primary": ["gpt-5-vision"], "fallback": ["claude-sonnet-vision"]},
    "style_extract": {"primary": ["claude-sonnet-vision"], "fallback": ["gpt-5-vision"]},

    # ── L2 影音 ──
    "text_to_video": {"primary": ["veo-3"], "fallback": ["seedance-2", "kling-2"]},
    "image_to_video": {"primary": ["seedance-2"], "fallback": ["kling-2", "veo-3"]},
    "tts_generate": {"primary": ["volcengine-tts"], "fallback": ["aliyun-tts"]},
    "audio_to_text": {"primary": ["whisper-v3"], "fallback": ["aliyun-asr"]},
}


class LLMResponse(dict):  # type: ignore[type-arg]
    """LiteLLM 风格的响应,模型 / 内容 / token 用量。"""

    @property
    def content(self) -> str:
        return self["choices"][0]["message"]["content"]


class _LiteLLMClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.LITELLM_URL,
            timeout=httpx.Timeout(60.0, connect=5.0),
            headers={"Authorization": f"Bearer {settings.LITELLM_API_KEY}"},
        )

    async def complete(
        self,
        *,
        task_type: str,
        messages: list[dict[str, Any]],
        routing_hints: dict[str, Any] | None = None,
        response_format: dict[str, str] | None = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """统一入口。task_type 决定模型路由,routing_hints 可手动覆盖。"""
        routing = TASK_TYPE_ROUTING.get(task_type, {})
        primary = (routing_hints or {}).get("primary") or (routing.get("primary") or ["deepseek-v4-flash"])[0]

        payload: dict[str, Any] = {
            "model": primary,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if response_format:
            payload["response_format"] = response_format
        if stream:
            payload["stream"] = True

        log.debug("litellm.complete", task_type=task_type, model=primary)
        resp = await self._client.post("/v1/chat/completions", json=payload)
        resp.raise_for_status()
        return LLMResponse(resp.json())

    async def aclose(self) -> None:
        await self._client.aclose()


class _MockClient:
    """dev / 离线测试用。返回固定文本,不发网络请求。"""

    async def complete(
        self,
        *,
        task_type: str,
        messages: list[dict[str, Any]],
        routing_hints: dict[str, Any] | None = None,
        response_format: dict[str, str] | None = None,
        stream: bool = False,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        log.debug("mock.complete", task_type=task_type)
        body = "{\"intent_type\":\"task_request\",\"domain\":\"video\",\"scenario\":\"anti_fraud\",\"confidence\":0.9}"
        if (response_format or {}).get("type") != "json_object":
            body = f"[mock-{task_type}] 这是 mock 模型返回的固定文本。"
        return LLMResponse(
            {
                "id": "chatcmpl-mock-001",
                "object": "chat.completion",
                "model": (routing_hints or {}).get("primary", "deepseek-v4-flash"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": body},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            }
        )

    async def aclose(self) -> None:
        pass


_singleton: _LiteLLMClient | _MockClient | None = None


def _get_client() -> _LiteLLMClient | _MockClient:
    global _singleton
    if _singleton is None:
        _singleton = _MockClient() if settings.LITELLM_MOCK else _LiteLLMClient()
    return _singleton


async def complete(
    *,
    task_type: str,
    messages: list[dict[str, Any]],
    routing_hints: dict[str, Any] | None = None,
    response_format: dict[str, str] | None = None,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> LLMResponse:
    return await _get_client().complete(
        task_type=task_type,
        messages=messages,
        routing_hints=routing_hints,
        response_format=response_format,
        stream=stream,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def close() -> None:
    global _singleton
    if _singleton is not None:
        await _singleton.aclose()
        _singleton = None


# 类型别名导出
ModelRole = Literal["system", "user", "assistant", "tool"]
