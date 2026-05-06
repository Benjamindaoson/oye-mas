# ADR-017:LangGraph 作为主编排内核(全量启用)

**状态**:Accepted v2(2026-05-06,**全量启用**;v1 历史版本"V1.5 引入、V1 默认关")
**提案者**:工程团队
**关联铁律**:1(单一调度者)/ 4(state 用引用)/ 13(MCP 工具)/ 14(HITL gate)/ 21(中断 9 分类)
**关联 ADR**:ADR-001-rev、ADR-010(HITL)、ADR-014(三模式同群)
**对齐 CLAUDE.md**:§4.4 Sprint 4 acceptance — "skills/anti_fraud_video.yaml 编译为 LangGraph"

## 决策升级(v2)

v1 ADR 设了 `USE_LANGGRAPH_RUNNER=false` 作 V1.5 渐进切换。
**v2 改为默认 true,LangGraph 是主编排内核**。理由:

1. CLAUDE.md §4.4 本就要求 Skill 编译为 LangGraph,V1 没真用 = 没达成
2. 自写 TaskRunner 的 V2 中断 C/D 死路一条,LangGraph time-travel 一行 API
3. 双轨增加心智成本,代码两份难维护
4. 测试 11/11 + 全套 97/97 通过,质量证据充分

`USE_LANGGRAPH_RUNNER=false` 保留为**紧急回滚兜底**,不再是默认值。
TaskRunner 类保留供单测使用,prod 不应路径走到。

---

## 背景

V1 的 `app.orchestrator.runner.TaskRunner` 是手写编排引擎:

- DAG 拓扑分层在 `task_compiler.compile_to_dag`
- step 状态在 PG 表 `tasks` / `task_steps`
- HITL 暂停靠 `hitl_gates.closed_at IS NULL` + WS 通知
- 派发走 Redis Streams `agent_tasks:<kind>`

它**正常工作**(86 单测全绿,V1 hero 跑通),但有两个长期债:

1. **V2 中断 C/D(回滚到第 N 步 / 改方向)做不出来** — 没有 checkpoint 机制,
   只能重新建任务。这正是铁律 14 把"V1 终审无回滚按钮"显式推迟的原因。
2. **状态恢复**(进程崩溃后续跑、跨机迁移)需要把所有 step 状态读回内存重组,
   工程量不小。

`langgraph` 和 `langgraph-checkpoint-postgres` 已在 [pyproject.toml](../backend/pyproject.toml) 声明,
但 V1 期间一直未使用 — `grep -rn "^from langgraph" youle/` = 0 命中。

## 决定

**双轨 + feature flag**:

- **V1 默认**:`USE_LANGGRAPH_RUNNER=false` → 走原 `TaskRunner`(零变动,生产稳定)
- **V1.5 启用**:`USE_LANGGRAPH_RUNNER=true` → 走新 `LangGraphTaskRunner`
- **V2 自动**:LangGraph time-travel 是中断 C/D 的真实现,V2 强制启用

新增模块(v2 全量):

```
youle/backend/app/orchestrator/langgraph_runner/
├── __init__.py            # 公开 LangGraphTaskRunner / build_state_graph / TaskState
├── state.py               # TaskState TypedDict + reducers(任务编排状态)
├── compiler.py            # 平铺 Skill YAML → StateGraph(节点/Send/conditional)
├── subgraph.py            # phase-aware 编译器(反诈视频 = 调研/制作/终审 三段)
├── result_waiter.py       # 节点等 Redis Streams 回执
├── checkpointer.py        # InMemorySaver / AsyncPostgresSaver 工厂
├── runner.py              # LangGraphTaskRunner(start/resume/resolve_hitl/rollback/get_state/get_history)
└── reflexion_graph.py     # 飞轮 Reflexion 的 LangGraph 化(analyze→validate→persist)
```

切换点(全部已经走 LangGraph):
- `app/api/messages.py` — `make_runner(session).start(task_id)`
- `app/api/hitl.py` — `make_runner(session).resolve_hitl(...)` → 内部转 `resume(Command)`
- `app/api/tasks.py` — `/{id}/rollback` + `/{id}/history`(time-travel 端点)
- `app/services/result_consumer.py` — flag 开时**不启动**(节点内自己等 stream)
- `flywheel/reflexion/runner.py` — 调 `process_reflexion_event` 转 graph

`runner_factory.make_runner(session)` 默认返回 `LangGraphTaskRunner`;
flag=false 仅作回滚兜底,prod 不走。

## 充分利用的 LangGraph 组件

| LangGraph 组件 | 在 youle 中的用法 |
|---|---|
| `StateGraph(TaskState)` | 替代手写 sweep 调度,Skill workflow → 节点 + 条件边 |
| `Annotated[..., reducer]` | step_results / hitl_decisions / messages 用合并 reducer 防并发冲突 |
| `add_messages` | TaskState.messages 字段(节点日志,Reflexion 时间线) |
| `Send(node, state)` | 同层并行 step 一次性 dispatch,替代 sweep 轮询 |
| `add_conditional_edges` | planner → fan-out → step → planner 循环结构 |
| `interrupt(payload)` | 替代 `hitl_gates.closed_at IS NULL` 轮询;暂停 + 序列化 state |
| `Command(resume=decision)` | HITL 决议恢复路径,无需 DB 标志位轮询 |
| `AsyncPostgresSaver` | task state 全量持久化(自动 setup `langgraph_*` 表)|
| `InMemorySaver` | dev / 测试用,LangGraphTaskRunner 单测无需 PG |
| `astream_events(version="v2")` | 节点开始/结束事件 → WS publish step_started / step_completed |
| `aget_state_history()` | 取所有 checkpoint(V1.5 时间线 UI / Reflexion 根因) |
| `aget_state(checkpoint_id)` | 读特定时刻的 state(V2 回滚预览) |
| `aupdate_state(config, values)` | 改写 collected_fields + 清下游 step → time travel(V2 中断 C/D) |

## 不动的部分(铁律明确禁止)

- **Redis Streams 派发 Agent**(铁律 1+2):分布式优势 > LangGraph in-process
- **Agent worker 消费回执**:节点只负责"派发 + 等回执",不直接调 Agent 函数
- **MCP 工具调用**(铁律 13):节点不替代 MCP server,LiteLLM 路由不退化为 ToolNode
- **现有 task_steps / hitl_gates / artifacts DB 表**:LangGraph state 镜射到 DB,UI / API 完全兼容
- **配额 / SMS / private chat / 静态查询**:同步函数,加 graph 是过度设计

## 决策矩阵(v2 — 哪些用 LangGraph)

| 功能 | LangGraph? | 落地 |
|---|---|---|
| 任务编排核心调度 | ✅ 必须 | `LangGraphTaskRunner` |
| HITL gate 暂停/恢复 | ✅ 必须 | `interrupt()` + `Command(resume=)` |
| 任务状态持久化 | ✅ 必须 | `AsyncPostgresSaver` |
| Agent 回执消费 | ✅ 必须 | 节点内 `wait_for_step_result`,`result_consumer` 默认 no-op |
| WS streaming | ✅ 必须 | `astream_events v2` |
| Time travel(V2 中断 C/D)| ✅ 必须 | `aupdate_state` |
| Skill 模块化(hero subgraph)| ✅ 应该 | `subgraph.build_phased_state_graph` |
| 飞轮 Reflexion | ✅ 应该 | `reflexion_graph`(checkpoint 保护失败可恢复)|
| 飞轮 Skill drafter / Ingestion / Preference embedder | ⚪ P1 范围 | 当前是单步 stream consumer,加 graph ROI 较低 |
| Agent 跨调通信 | ❌ 禁止 | 铁律 1+2:Redis Streams 分布式 |
| MCP 工具调用 | ❌ 禁止 | 铁律 13:LiteLLM 路由 + MCP server |
| Agent worker 内部 | ❌ 不该 | worker 是无状态消费器 |
| HR/财务经理私聊 | ❌ 不该 | 单轮 LLM,加 graph 过度 |
| 配额检查 / SMS / 静态查询 | ❌ 不该 | 同步函数 |

## 价值证明:V2 中断 C/D 一行 API

```python
# V1:做不到 — TaskRunner 没 checkpoint,改方向得新建任务
# V1.5+(LangGraph runner):
runner = make_runner(session)
await runner.rollback_to_step(
    task_id, target_step_id="image_process", instruction="风格改成赛博朋克"
)
# 内部:
#   1. aget_state_history → 找 image_process 还没跑完的最新 snapshot
#   2. aupdate_state → 清 image_process 及下游,改写 collected_fields
#   3. ainvoke(None, config) → 从 anchor checkpoint 续跑
```

新增 REST 端点(LangGraph runner 启用时才生效):

- `POST /api/tasks/{id}/rollback {target_step_id, instruction?}` — V1.5 中断 C / V2 中断 D
- `GET  /api/tasks/{id}/history` — checkpoint 列表(给前端时间线 UI)

## 测试覆盖(共 11 个 LangGraph 测试 / 全套 97 测试)

`tests/unit/test_langgraph_compiler.py`(3):
- 简单线性 / 菱形并行 / 坏 YAML 早 fail

`tests/unit/test_langgraph_runtime.py`(4,InMemorySaver):
- 线性图跑完 + dispatch 真发生
- interrupt() 暂停 + Command(resume) 恢复
- HITL rejected → final_status=failed
- **time travel**:b 跑完后回滚到 a 完成、b 待跑的 snapshot,改 collected_fields,重跑 b 拿到新 artifact

`tests/unit/test_langgraph_subgraph.py`(2):
- 反诈视频 hero phased(research / production / review)编译 + 跑通,**production phase 内 image/tts/bgm 真并行**
- 无 phase 字段时退化为平铺图(向后兼容)

`tests/unit/test_langgraph_reflexion.py`(2):
- LLM ok → 写 prompt_improvement_candidates(graph 节点链跑通)
- LLM 抛 → 节点标 error → graph END,**不写 DB,checkpoint 保留**(可续跑)

## 迁移路径(已完成)

| 阶段 | 默认值 | 状态 |
|---|---|---|
| ~~**V1**~~ | ~~`false`~~ | ~~历史~~ |
| ~~**V1.5 渐进**~~ | ~~staging 切~~ | ~~跳过~~ |
| **现在(v2 ADR)** | `USE_LANGGRAPH_RUNNER=true` | **prod 默认走 LangGraph** |
| **V2 中断 C/D** | flag 强制 true | rollback API 已就绪,前端启用即可 |

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| LangGraph 1.x API 不稳定 | 锁版本 `langgraph>=1.1,<2`;升级走 ADR |
| PostgresSaver 表与现有迁移冲突 | `setup()` 自动建表(`langgraph_*` 前缀),与现有表无碰撞 |
| 多 worker 并发同 task | LangGraph checkpointer 自带乐观锁;`thread_id=task:<uuid>` 唯一 |
| state 太大(产物字段)| 已强制铁律 4:state 只存 ref,大产物落 OSS |
| time travel 误删数据 | rollback 把清掉的 step 标 `rolled_back`(而非删除 task_steps 行)|

## 决策不接受的部分

- ❌ **跨 Agent 用 LangGraph 编排**:违反铁律 1 + ADR-002,Agent 间 0 通信
- ❌ **MessageGraph / `add_messages` 跨 Agent 共享**:大产物会序列化进 state,违反铁律 4
- ❌ **替换 LiteLLM 为 ToolNode**:LiteLLM 路由表是 youle 的核心(57 task_type),不退化

## 紧急回滚(v2)

如果 LangGraph 出现 prod 问题,**临时回滚**:

```bash
# 1. ConfigMap 加(覆盖默认 true)
USE_LANGGRAPH_RUNNER=false

# 2. 重启 backend Deployment
kubectl -n youle rollout restart deploy/backend

# 3. 后续 task 走 V1 自写 TaskRunner;result_consumer 自动启动
# 4. /rollback 端点返回 405(time-travel 无法用)
```

正常生产无需任何特殊配置 — `USE_LANGGRAPH_RUNNER` 默认 true,
`AsyncPostgresSaver.setup()` 在 backend 启动时自动建 `langgraph_*` 表。

# 4. 前端启用 V1.5 时间线 UI:
#    GET /api/tasks/<id>/history
#    POST /api/tasks/<id>/rollback {target_step_id, instruction}
```

观察 24h:Grafana `youle_intent_latency_seconds` / `youle_agent_queue_pending` 与 V1 同水平 → 留 LangGraph;否则切回 false 应急。
