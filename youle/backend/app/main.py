"""FastAPI 应用入口。"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, conversations, flywheel, hitl, messages, tasks, upload, ws
from app.config import settings
from app.logging import configure_logging
from app.mcp_client import close_mcp_client
from app.redis_client import close_redis
from app.router import close as close_llm
from app.services.result_consumer import result_consumer

configure_logging()
log = structlog.get_logger(__name__)


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
    return {"status": "ok", "env": settings.ENV}


# ── REST 路由 ──
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(messages.router, prefix="/api", tags=["messages"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])
app.include_router(hitl.router, prefix="/api/tasks", tags=["hitl"])
app.include_router(flywheel.router, prefix="/api", tags=["flywheel"])

# ── WebSocket ──
app.include_router(ws.router, tags=["ws"])
