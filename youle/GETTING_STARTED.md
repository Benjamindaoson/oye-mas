# Getting Started

> 第一次进仓库的工程师必读。Sprint 0 acceptance 的逐步骤验证。

## 0. 前置依赖

- Docker Desktop(Win 推荐 WSL2 后端)
- Python 3.12+ 与 [uv](https://docs.astral.sh/uv/)
- Node 20+ 与 pnpm 9+

## 1. 起基础设施(docker-compose mock 模式)

```bash
cd infrastructure
docker compose -f docker-compose.yml -f docker-compose.mock.yml up -d
docker compose ps   # 看 5 个 service 都 healthy
```

容器:
- postgres(5432)+ pgvector
- redis(6379)
- minio(9000 / 9001 控制台)→ 自动建 bucket `youle-dev`
- qdrant(6333 / 6334)
- litellm-mock(4000)

## 2. 后端

```bash
cp .env.example .env
cd backend
uv sync --extra dev
uv run alembic upgrade head        # 跑通 18+ 张表
uv run uvicorn app.main:app --reload --port 8000
```

打开 http://localhost:8000/docs 看 API。

```bash
# Sprint 0 acceptance:
uv run pytest tests/smoke/ -v       # 全绿即通过
```

## 3. 启 4 个 Agent(分别开 4 个终端)

```bash
cd agents && uv pip install -e .
uv run python -m text.main           # Agent 1 文字
uv run python -m document.main       # Agent 2 文档
uv run python -m image.main          # Agent 3 图
uv run python -m av.main             # Agent 4 影音
```

## 4. 启 7 个 MCP server

```bash
cd mcp_servers && uv pip install -e .
uv run python -m search.server         # 7001
uv run python -m image_tools.server    # 7002
uv run python -m video_tools.server    # 7003
uv run python -m audio_tools.server    # 7004
uv run python -m document_tools.server # 7005
uv run python -m oss.server            # 7006
uv run python -m platform_publish.server # 7007(V1.5)
```

## 5. 启前端

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000
pnpm gen:api      # 后端起来后,生成 lib/api-types.ts

# Playwright E2E(Sprint 5 acceptance)
pnpm exec playwright install chromium   # 首次需要装浏览器
pnpm test:e2e                            # 跑 e2e/*.spec.ts
```

## 6. 跑通 happy path(Sprint 3 acceptance)

待 Sprint 3 实现完。预期:
- 用户消息 → 主编排 → Agent 派活 → 拿到产物(全 mock)

## 7. 接真服务(Sprint 4+)

- LiteLLM:把 .env 中 `LITELLM_MOCK=false` + 配真 API key + 起 litellm-proxy 容器
- Tavily:`TAVILY_API_KEY=...`
- Volcengine TTS:`VOLCENGINE_TTS_APP_ID/TOKEN`
- 阿里云 OSS:dev MinIO → prod 切阿里云 OSS

## 8. 排错

- `pytest` 报 db 连接错 → 确认 docker-compose 起来了 + alembic 跑过了
- WS 不连 → 检查 token / NEXT_PUBLIC_WS_URL
- 视频 handler 卡死 → 不要在 Agent 进程跑 FFmpeg,走 Celery(铁律 5)

## 9. 何时停下来问用户(CLAUDE.md §7)

- Sprint 完成后 → 不开下一个 Sprint
- 删除 / 重构 > 50 行 → 必先解释意图
- 引入 ARCHITECTURE.md §2.13 没列的依赖 → 必问
- API 设计偏离 spec → 必问
- 改 prompt → 必更新对应回归测试 yaml,然后问
