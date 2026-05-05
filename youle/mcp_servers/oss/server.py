"""mcp-oss:upload / download / sign_url(后端 OSS 接口的 MCP 包装)。"""

from __future__ import annotations

from typing import Any

from mcp_servers._shared.http_app import make_app


async def upload_bytes(arguments: dict[str, Any]) -> dict[str, Any]:
    object_key = arguments.get("object_key", "default.bin")
    return {"object_key": object_key, "ok": True}


async def download_bytes(arguments: dict[str, Any]) -> dict[str, Any]:
    return {"object_key": arguments.get("object_key"), "size": 0}


async def sign_url(arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "url": f"https://oss.example.com/{arguments.get('object_key')}?sig=mock",
        "expires_in": 3600,
    }


app = make_app(
    server_name="oss",
    tools={
        "upload_bytes": upload_bytes,
        "download_bytes": download_bytes,
        "sign_url": sign_url,
    },
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7006)
