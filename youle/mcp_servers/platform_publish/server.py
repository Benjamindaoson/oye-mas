"""mcp-platform-publish(V1.5):douyin / xhs / wechat 发布 API 集成。"""

from __future__ import annotations

from typing import Any

from mcp_servers._shared.http_app import make_app


async def douyin_publish(arguments: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("V1.5 范围 — 抖音开放平台 API 集成")


async def xhs_publish(arguments: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("V1.5 范围")


async def wechat_publish(arguments: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("V1.5 范围")


app = make_app(
    server_name="platform-publish",
    tools={
        "douyin_publish": douyin_publish,
        "xhs_publish": xhs_publish,
        "wechat_publish": wechat_publish,
    },
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7007)
