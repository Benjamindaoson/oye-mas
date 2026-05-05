# Backend

## 起步

```bash
uv sync
cp ../.env.example ../.env

# 起基础设施
cd ../infrastructure && docker compose -f docker-compose.yml -f docker-compose.mock.yml up -d

# 跑迁移
cd ../backend && uv run alembic upgrade head

# 启服务
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 测试

```bash
uv run pytest tests/smoke/ -v       # Sprint 0 健康检查
uv run pytest                       # 全套
uv run ruff check .
uv run mypy app/
```

## 目录结构

见 `docs/ARCHITECTURE.md §1`。

## 铁律

任何代码必须符合 `CLAUDE.md` 的 22 条铁律和 §3 代码模式黑名单。grep-able 的违规模式由 CI 兜底。
