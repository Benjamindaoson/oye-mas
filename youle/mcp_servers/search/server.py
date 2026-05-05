"""mcp-search:web_search(Tavily,无 key 时降级)+ web_fetch(httpx)。"""

from __future__ import annotations

import os
from typing import Any

import httpx
import structlog

from mcp_servers._shared.http_app import make_app

log = structlog.get_logger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_URL = "https://api.tavily.com/search"


async def web_search(arguments: dict[str, Any]) -> dict[str, Any]:
    query = arguments.get("query", "").strip()
    max_results = int(arguments.get("max_results", 5))
    lang = arguments.get("lang", "zh")

    if not query:
        return {"results": []}

    if TAVILY_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    TAVILY_URL,
                    json={
                        "api_key": TAVILY_API_KEY,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "results": [
                        {
                            "title": r.get("title", ""),
                            "url": r.get("url", ""),
                            "snippet": r.get("content", "")[:300],
                            "image_url": r.get("image_url"),
                        }
                        for r in data.get("results", [])
                    ]
                }
        except Exception as e:
            log.warning("tavily.failed", err=str(e))
            # fallthrough to mock

    # 无 key 或失败:返回结构化 mock(用于 dev / CI)
    return {
        "results": [
            {
                "title": f"[mock] 关于「{query}」的结果 {i + 1}",
                "url": f"https://example.com/article/{i}",
                "snippet": "...",
                "image_url": None,
            }
            for i in range(max_results)
        ],
        "_mock": True,
    }


async def web_fetch(arguments: dict[str, Any]) -> dict[str, Any]:
    url = arguments.get("url", "")
    render_js = bool(arguments.get("render_js", False))
    if not url:
        return {"error": "missing_url"}
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "youle/1.0"})
            return {
                "url": url,
                "status": resp.status_code,
                "content_type": resp.headers.get("content-type", ""),
                "content": resp.text[:50_000],
                "render_js": render_js,
            }
    except Exception as e:
        return {"url": url, "error": str(e)}


app = make_app(
    server_name="search",
    tools={"web_search": web_search, "web_fetch": web_fetch},
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=7001)
