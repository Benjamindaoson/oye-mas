"""Agent 端 MCP 客户端 — 与 backend.app.mcp_client 对齐。"""

from __future__ import annotations

import os
from typing import Any

import httpx

MCP_ENDPOINTS: dict[str, str] = {
    "search": os.getenv("MCP_SEARCH_URL", "http://mcp-search:7001"),
    "image_tools": os.getenv("MCP_IMAGE_TOOLS_URL", "http://mcp-image-tools:7002"),
    "video_tools": os.getenv("MCP_VIDEO_TOOLS_URL", "http://mcp-video-tools:7003"),
    "audio_tools": os.getenv("MCP_AUDIO_TOOLS_URL", "http://mcp-audio-tools:7004"),
    "document_tools": os.getenv("MCP_DOCUMENT_TOOLS_URL", "http://mcp-document-tools:7005"),
    "oss": os.getenv("MCP_OSS_URL", "http://mcp-oss:7006"),
    "platform_publish": os.getenv("MCP_PLATFORM_PUBLISH_URL", "http://mcp-platform-publish:7007"),
}


class AgentMCPClient:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=5.0))

    async def call_tool(self, *, server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        url = f"{MCP_ENDPOINTS[server]}/tools/{tool}"
        resp = await self._http.post(url, json={"arguments": arguments})
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    async def aclose(self) -> None:
        await self._http.aclose()


mcp_client = AgentMCPClient()
