# 「有了」(Youle)

> 你的专属 AI 工作团队 — 微信式群聊形态,1 个总裁助理 + 4 个分任务 Agent + 2 个支持 Agent

**V1 hero**:反诈视频制作 + 电商详情图制作

## 三件套(Vibe Coding)

- **`CLAUDE.md`** — Claude Code / Cursor 默认读这份(操作指令,22 条铁律)
- **`docs/ARCHITECTURE.md`** — 技术细节(仓库结构 / 选型 / 18 张表)
- **`docs/CONSTITUTION.md`** — 治理决策(铁律详解 + ADR 全集)

## Sprint 路径(8 周到 V1-P0)

| Sprint | 主题 | 周 |
|---|---|---|
| 0 | 基础设施 | 1 |
| 1 | 7 个 MCP servers | 1 |
| 2 | 主编排 9 子模块 | 1.5 |
| 3 | 4 Agent + 反诈视频 happy path | 1.5 |
| 4 | Skill + HITL + 飞轮 + 三模式 | 1 |
| 5 | 前端 | 2 |
| 6 | 联调 + 上线 | 1 |

## 起步

```bash
# 1. 安装依赖
cd backend && uv sync
cd ../frontend && pnpm install

# 2. 起 mock 基础设施
cd infrastructure && docker compose -f docker-compose.yml -f docker-compose.mock.yml up -d

# 3. 跑迁移
cd backend && uv run alembic upgrade head

# 4. 起后端
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. 起前端
cd frontend && pnpm dev

# 6. 跑 smoke test
cd backend && uv run pytest tests/smoke/ -v
```

## ADR 速查

- ADR-001-rev:Agent 编号 1=文字 / 2=文档 / 3=图 / 4=影音
- ADR-009:MCP 协议作为工具集成唯一标准
- ADR-010:Hero 任务必有 HITL gate
- ADR-011:数据飞轮 4 类信号沉淀必做
- ADR-013:HR + 财务经理 共 7 个 AI 角色
- ADR-014:三模式(Plan/Ask/Auto)同群切换
- ADR-015:Agent 拟人化 V1 必做
- ADR-016:左栏导航简化

详见 `docs/CONSTITUTION.md`。

## 慢一点没事,做错代价大

> MCP / HITL / Agent 编号 / task_type 一旦上线就是产品 DNA,事后改是大手术。
>
> 不确定就问,不要猜——5 分钟问用户胜过 5 小时返工。
