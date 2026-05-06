"""Checkpointer 工厂 — 选 InMemorySaver(开发)或 AsyncPostgresSaver(生产)。

PostgresSaver 用独立连接池(不挂 SQLAlchemy session)以避免 transaction 嵌套。
表自动 setup(LangGraph 自带 migration)。
"""

from __future__ import annotations

import os

import structlog

log = structlog.get_logger(__name__)


# ── 全局持有的 saver 实例(app lifespan 管理)──
_saver = None
_psyco_pool = None


async def init_postgres_checkpointer(database_url: str | None = None):
    """app 启动时调一次。返回 saver 实例(可传给 init_checkpointer)。"""
    global _saver, _psyco_pool
    if _saver is not None:
        return _saver

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    url = database_url or os.getenv("LANGGRAPH_CHECKPOINT_URL") or os.getenv("DATABASE_URL")
    if not url or url.startswith("sqlite") or os.getenv("LANGGRAPH_CHECKPOINT_INMEMORY") == "true":
        log.info("lg.checkpointer.in_memory", reason="no postgres url")
        _saver = InMemorySaver()
        return _saver

    # SQLAlchemy URL → libpq URL(兼容 asyncpg / psycopg async 驱动写法)
    pq_url = (
        url.replace("postgresql+asyncpg://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )
    try:
        from psycopg_pool import AsyncConnectionPool

        _psyco_pool = AsyncConnectionPool(
            conninfo=pq_url,
            max_size=int(os.getenv("LANGGRAPH_PG_POOL_MAX", "10")),
            kwargs={"autocommit": True, "prepare_threshold": 0},
            open=False,
        )
        await _psyco_pool.open(wait=True)
        _saver = AsyncPostgresSaver(_psyco_pool)
        await _saver.setup()  # 创建 langgraph 表
        log.info("lg.checkpointer.postgres", url_redacted=pq_url.split("@")[-1])
        return _saver
    except Exception as e:
        log.warning("lg.checkpointer.postgres_failed", err=str(e))
        _saver = InMemorySaver()
        return _saver


async def close_postgres_checkpointer() -> None:
    global _saver, _psyco_pool
    if _psyco_pool is not None:
        try:
            await _psyco_pool.close()
        except Exception as e:  # noqa: BLE001
            log.warning("lg.checkpointer.close_failed", err=str(e))
    _saver = None
    _psyco_pool = None
