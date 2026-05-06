"""FastAPI 应用入口。"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    auth,
    conversations,
    flywheel,
    hitl,
    library,
    messages,
    support,
    tasks,
    upload,
    ws,
)
from app.api import (
    skills as skills_api,
)
from app.config import settings
from app.db import SessionLocal
from app.logging import configure_logging
from app.mcp_client import close_mcp_client
from app.redis_client import close_redis, get_redis
from app.router import close as close_llm
from app.services.result_consumer import result_consumer

configure_logging()
log = structlog.get_logger(__name__)

# ── Sentry(prod / staging 接入)──
_SENTRY_DSN = os.getenv("SENTRY_DSN")
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            environment=settings.ENV,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
            integrations=[StarletteIntegration(), FastApiIntegration()],
            release=os.getenv("APP_VERSION", "dev"),
        )
        log.info("sentry.initialized", env=settings.ENV)
    except Exception as e:
        log.warning("sentry.init_failed", err=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("youle.startup", env=settings.ENV, mock=settings.LITELLM_MOCK)
    # 启动后台 reaper:消费 Agent 回执 → driving TaskRunner.handle_result
    result_consumer.start()
    yield
    log.info("youle.shutdown")
    await result_consumer.stop()
    await close_llm()
    await close_mcp_client()
    await close_redis()


app = FastAPI(
    title="「有了」后端",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    """liveness — 进程是否活着,1 行返回。K8s livenessProbe 用这个。"""
    return {"status": "ok", "env": settings.ENV, "version": os.getenv("APP_VERSION", "dev")}


@app.get("/ready")
async def ready() -> Response:
    """readiness — 实际能服务流量。检查 DB / Redis / LiteLLM 联通。"""
    checks: dict[str, str] = {}
    overall_ok = True
    # DB
    try:
        async with SessionLocal() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as e:
        checks["db"] = f"fail:{e!s}"[:100]
        overall_ok = False
    # Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"fail:{e!s}"[:100]
        overall_ok = False
    # LiteLLM(只 ping URL,不实际调模型)
    if not settings.LITELLM_MOCK:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{settings.LITELLM_URL}/health")
                checks["litellm"] = "ok" if resp.status_code < 500 else f"http:{resp.status_code}"
                if resp.status_code >= 500:
                    overall_ok = False
        except Exception as e:
            checks["litellm"] = f"fail:{e!s}"[:100]
            overall_ok = False
    else:
        checks["litellm"] = "mock"

    payload = {"status": "ok" if overall_ok else "degraded", "checks": checks}
    import json

    return Response(
        content=json.dumps(payload),
        status_code=200 if overall_ok else 503,
        media_type="application/json",
    )


@app.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape。简化版自实现:统计 result_consumer 队列指标。"""
    from app.services.metrics import render_prometheus_metrics

    body = await render_prometheus_metrics()
    return Response(content=body, media_type="text/plain; version=0.0.4")


# ── REST 路由 ──
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(messages.router, prefix="/api", tags=["messages"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(hitl.router, prefix="/api/tasks", tags=["hitl"])
app.include_router(flywheel.router, prefix="/api", tags=["flywheel"])
app.include_router(support.router, prefix="/api", tags=["support"])
app.include_router(library.router, prefix="/api", tags=["library"])
app.include_router(skills_api.router, prefix="/api", tags=["skills"])

# ── WebSocket ──
app.include_router(ws.router, tags=["ws"])
