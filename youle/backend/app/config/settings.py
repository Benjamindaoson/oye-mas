"""统一配置(Pydantic Settings)。env 来源:.env / 环境变量。"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── 环境 ──
    ENV: Literal["dev", "staging", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = True

    # ── DB ──
    DATABASE_URL: str = "postgresql+asyncpg://youle:youle_dev@localhost:5432/youle"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── OSS ──
    OSS_ENDPOINT: str = "http://localhost:9000"
    OSS_ACCESS_KEY: str = "minioadmin"
    OSS_SECRET_KEY: str = "minioadmin"
    OSS_BUCKET: str = "youle-dev"
    OSS_REGION: str = "cn-hangzhou"
    OSS_USE_SSL: bool = False

    # ── Qdrant ──
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # ── LiteLLM ──
    LITELLM_URL: str = "http://localhost:4000"
    LITELLM_API_KEY: str = "sk-mock-1234"
    LITELLM_MOCK: bool = True

    # ── 外部 ──
    TAVILY_API_KEY: str = ""
    ALIYUN_ACCESS_KEY: str = ""
    ALIYUN_SECRET_KEY: str = ""
    VOLCENGINE_TTS_APP_ID: str = ""
    VOLCENGINE_TTS_TOKEN: str = ""

    # ── Auth ──
    JWT_SECRET: str = "change_me_to_a_long_random_string_in_prod"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 72
    SMS_DEV_MODE: bool = True

    # ── CORS / WS ──
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"
    WS_HEARTBEAT_SECONDS: int = 30

    # ── 监控 ──
    SENTRY_DSN: str = ""

    # ── LangGraph 接入(对齐 CLAUDE.md §4.4:Skill 编译为 LangGraph)──
    # 默认开:任务编排 / HITL / time-travel / streaming 全部走 LangGraph。
    # TaskRunner(V1 自写)保留作为单测兼容兜底,prod 不再使用。
    USE_LANGGRAPH_RUNNER: bool = True
    LANGGRAPH_CHECKPOINT_INMEMORY: bool = False
    LANGGRAPH_CHECKPOINT_URL: str = ""  # 留空 = 复用 DATABASE_URL
    LANGGRAPH_PG_POOL_MAX: int = 10

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_dev(self) -> bool:
        return self.ENV == "dev"

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"


settings = Settings()  # type: ignore[call-arg]
