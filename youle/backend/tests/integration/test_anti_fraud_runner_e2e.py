"""端到端反诈视频:5 step + 3 HITL gate 全流程,无需 Redis。

策略:
- 用 testcontainers 起一次性 PG(pgvector + JSONB + Vector)
- alembic upgrade head 跑 schema
- 注入 fake dispatcher → 收集 AgentTask 列表
- 注入 fake publisher → 收集 WS 事件列表
- 手工灌 AgentResult 给 runner.handle_result,模拟 Agent 完成
- 在 HITL gate 处停下来,调 runner.resolve_hitl(approve)继续
- 最终断言:5 step 全 completed,3 gate 全 closed,task.status=completed,产物表有记录

注:此测试需要 docker。Run with: pytest tests/integration/test_anti_fraud_runner_e2e.py -v
若 docker 不可用,skip。
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# 仅当 testcontainers 可用 + docker 可用时跑
testcontainers = pytest.importorskip("testcontainers.postgres")  # noqa
PG = testcontainers.PostgresContainer  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def pg_url() -> AsyncIterator[str]:
    """启一次性 pgvector PG 容器。docker 不可用则整组 skip。"""
    image = os.getenv("TEST_PG_IMAGE", "pgvector/pgvector:pg16")
    try:
        container = PG(image=image, username="youle", password="youle_dev", dbname="youle")
        container.start()
    except Exception as e:
        pytest.skip(f"docker / pg container not available: {e}")
    try:
        url = container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")
        if "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        yield url
    finally:
        container.stop()


@pytest.fixture(scope="module")
async def session_factory(pg_url: str):
    """跑 alembic + 灌种子 skill,返回 sessionmaker。"""
    # 先把 DATABASE_URL 注到环境(alembic env.py 读 settings)
    os.environ["DATABASE_URL"] = pg_url
    os.environ["LITELLM_MOCK"] = "true"

    # alembic upgrade head — 用 subprocess 比内置 API 简单
    backend_dir = Path(__file__).resolve().parents[2]
    proc = await asyncio.create_subprocess_exec(
        "alembic",
        "upgrade",
        "head",
        cwd=str(backend_dir),
        env={**os.environ},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    if proc.returncode != 0:
        pytest.fail(f"alembic failed: {err.decode()}")

    engine = create_async_engine(pg_url)
    Session = async_sessionmaker(bind=engine, expire_on_commit=False)

    # 灌种子:user / conversation / skill
    from app.models.conversation import Conversation
    from app.models.skill import Skill
    from app.models.user import User

    skill_yaml_text = (
        Path(__file__).resolve().parents[3] / "skills" / "anti_fraud_video.yaml"
    ).read_text(encoding="utf-8")

    async with Session() as session:
        user = User(id=uuid4(), phone="13800000001", nickname="test", plan="free")
        session.add(user)
        await session.flush()

        skill = Skill(
            id=uuid4(),
            skill_id="anti_fraud_video",
            name="反诈视频制作",
            domain="video",
            scenario="anti_fraud",
            version="1.0",
            yaml_content=skill_yaml_text,
            status="published",
        )
        session.add(skill)
        await session.flush()

        conv = Conversation(
            id=uuid4(),
            user_id=user.id,
            name="反诈视频群",
            mode="group",
            work_mode="auto",
            skill_id=skill.id,
        )
        session.add(conv)
        await session.commit()

    try:
        yield Session, user.id, conv.id, skill.id
    finally:
        await engine.dispose()


@pytest.fixture
def collected_dispatch():
    """注入式 dispatcher — 收集所有派发的 AgentTask 到列表。"""
    items: list = []

    async def fake_dispatch(task) -> str:
        items.append(task)
        return f"fake-msg-{len(items)}"

    return items, fake_dispatch


@pytest.fixture
def collected_publish():
    """注入式 ws publisher — 收集所有 WS 事件。"""
    events: list[dict[str, Any]] = []

    async def fake_publish(user_id: str, payload: dict[str, Any]) -> None:
        events.append({"user_id": user_id, **payload})

    return events, fake_publish


# ════════════════════════════════════════════════════════════════
# 反诈视频端到端
# ════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_anti_fraud_full_e2e(
    session_factory, collected_dispatch, collected_publish
) -> None:
    Session, user_id, conv_id, skill_id = session_factory
    dispatched, fake_dispatch = collected_dispatch
    ws_events, fake_publish = collected_publish

    from app.models.hitl_gate import HITLGate
    from app.models.task import Task, TaskStep
    from app.orchestrator.runner import TaskRunner
    from app.schemas.agent import AgentResult, ArtifactRef

    # 1. 创建 Task(模拟 messages.py 已经走完意图 + 校验)
    task_id = uuid4()
    async with Session() as session:
        task = Task(
            id=task_id,
            user_id=user_id,
            conversation_id=conv_id,
            skill_id=skill_id,
            skill_version="1.0",
            status="pending",
            collected_fields={
                "年份": 2026,
                "骗局类型": "电信诈骗",
                "受众": "城市老人",
                "时长": "60s",
            },
            progress={"current": 0, "total": 5},
        )
        session.add(task)
        await session.commit()

    # 2. start → 派发 research(唯一无依赖的入口 step)
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        first = await runner.start(task_id)
        assert first == ["research"], f"expected only research, got {first}"
        assert len(dispatched) == 1
        assert dispatched[0].step_id == "research"
        assert dispatched[0].agent_id == "agent_1"  # ADR-001-rev:文字 = 1

    # 3. 模拟 Agent 1 完成 research → 应自动派发 script + image_process(都依赖 research)
    research_artifact = ArtifactRef(
        artifact_id=uuid4(),
        type="structured",
        reference="oss://test/research.xlsx",
        extra_metadata={"row_count": 10},
    )
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(
                task_id=task_id,
                step_id="research",
                status="completed",
                output=research_artifact,
                duration_ms=1200,
                cost_usd=0.0003,
                model_used="deepseek-v4-pro",
            )
        )
    # 现在应有 3 个 dispatch:research + script + image_process
    assert len(dispatched) == 3
    by_step = {t.step_id: t for t in dispatched}
    assert "script" in by_step
    assert "image_process" in by_step
    # 模板上下文:script 的 inputs 应该有 research 的 reference
    assert by_step["script"].inputs.get("research", {}).get("reference") == "oss://test/research.xlsx"

    # 4. 完成 script → script 有 hitl_gate(version_select),应开 gate,不派下游
    script_artifact = ArtifactRef(
        artifact_id=uuid4(),
        type="text",
        reference="oss://test/script.txt",
    )
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(
                task_id=task_id,
                step_id="script",
                status="completed",
                output=script_artifact,
                duration_ms=2400,
                cost_usd=0.0008,
            )
        )
    # 没新派发(还差 image_process 完成 + script gate 未关)
    assert len(dispatched) == 3
    # 应有 1 个 hitl_gate:script(version_select)
    async with Session() as session:
        rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
        gates = list(rows.scalars().all())
    open_script_gate = next(g for g in gates if g.step_id == "script")
    assert open_script_gate.gate_type == "version_select"
    assert open_script_gate.closed_at is None

    # 5. 完成 image_process → image_process 有 hitl_gate(quality_review),开 gate
    image_artifact = ArtifactRef(
        artifact_id=uuid4(),
        type="image_collection",
        reference="oss://test/images/",
        extra_metadata={"count": 6},
    )
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(
                task_id=task_id,
                step_id="image_process",
                status="completed",
                output=image_artifact,
                duration_ms=8000,
            )
        )
    async with Session() as session:
        rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
        gates = list(rows.scalars().all())
    image_gate = next(g for g in gates if g.step_id == "image_process")
    assert image_gate.gate_type == "quality_review"
    assert image_gate.closed_at is None

    # 6. 用户 approve script gate → 还需要 image_process gate 也关,bgm 才能跑
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        out = await runner.resolve_hitl(open_script_gate.id, resolution="approved")
        # bgm 依赖 script(已 completed + gate 已关),但还不能派 video_compose(等 image_process gate)
        assert "bgm" in out, f"approve script should dispatch bgm, got {out}"
    assert "bgm" in [t.step_id for t in dispatched]

    # 7. 用户 approve image_process gate → 仍不能派 video_compose,因为 bgm 还没完成
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        out = await runner.resolve_hitl(image_gate.id, resolution="approved")
        assert out == [], f"image_process gate close shouldn't dispatch yet, got {out}"

    # 8. 完成 bgm → 应派 video_compose(它依赖 script + image_process + bgm)
    bgm_artifact = ArtifactRef(
        artifact_id=uuid4(),
        type="audio",
        reference="oss://bgm/warning.mp3",
    )
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(
                task_id=task_id,
                step_id="bgm",
                status="completed",
                output=bgm_artifact,
                duration_ms=200,
            )
        )
    assert "video_compose" in [t.step_id for t in dispatched]

    # 9. 完成 video_compose → 开 final_approval gate(第 3 个 HITL)
    video_artifact = ArtifactRef(
        artifact_id=uuid4(),
        type="video",
        reference="oss://videos/output.mp4",
        extra_metadata={"resolution": "1080p", "duration_seconds": 60},
    )
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(
                task_id=task_id,
                step_id="video_compose",
                status="completed",
                output=video_artifact,
                duration_ms=420_000,
            )
        )
    async with Session() as session:
        rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
        gates = list(rows.scalars().all())
    final_gate = next(g for g in gates if g.step_id == "video_compose")
    assert final_gate.gate_type == "final_approval"

    # 10. 用户 approve 终审 → task 应 completed
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.resolve_hitl(final_gate.id, resolution="approved")

    # 11. 验收
    async with Session() as session:
        task = await session.get(Task, task_id)
        assert task is not None
        assert task.status == "completed", f"task status: {task.status}"
        assert task.completed_at is not None

        rows = await session.execute(
            select(TaskStep).where(TaskStep.task_id == task_id)
        )
        steps = list(rows.scalars().all())
        statuses = {s.step_id: s.status for s in steps}
        assert statuses == {
            "research": "completed",
            "script": "completed",
            "image_process": "completed",
            "bgm": "completed",
            "video_compose": "completed",
        }

        rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
        gates = list(rows.scalars().all())
        assert len(gates) == 3
        assert all(g.resolution == "approved" for g in gates)
        assert all(g.closed_at is not None for g in gates)

    # WS 事件:至少有 5 个 step_started + 5 个 step_completed + 3 个 hitl_gate_opened/closed + 1 个 task_completed
    types_count: dict[str, int] = {}
    for ev in ws_events:
        types_count[ev["type"]] = types_count.get(ev["type"], 0) + 1
    assert types_count.get("step_started", 0) == 5
    assert types_count.get("step_completed", 0) == 5
    assert types_count.get("hitl_gate_opened", 0) == 3
    assert types_count.get("hitl_gate_closed", 0) == 3
    assert types_count.get("task_completed", 0) == 1


@pytest.mark.asyncio
async def test_modify_redispatches_target_step(
    session_factory, collected_dispatch, collected_publish
) -> None:
    """HITL modify:用户在 final 终审说"换 BGM" → bgm step 应该重派。"""
    Session, user_id, conv_id, skill_id = session_factory
    dispatched, fake_dispatch = collected_dispatch
    _, fake_publish = collected_publish

    from app.models.hitl_gate import HITLGate
    from app.models.task import Task
    from app.orchestrator.runner import TaskRunner
    from app.schemas.agent import AgentResult, ArtifactRef

    task_id = uuid4()
    async with Session() as session:
        session.add(
            Task(
                id=task_id,
                user_id=user_id,
                conversation_id=conv_id,
                skill_id=skill_id,
                skill_version="1.0",
                status="pending",
                collected_fields={
                    "年份": 2026,
                    "骗局类型": "电信诈骗",
                    "受众": "城市老人",
                    "时长": "60s",
                },
                progress={"current": 0, "total": 5},
            )
        )
        await session.commit()

    # 跑到 bgm 完成前,简化:把 research/script/image/bgm 串起来到 video_compose 的 final gate
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.start(task_id)

    def _ar(step_id: str, kind: str = "text") -> ArtifactRef:
        return ArtifactRef(
            artifact_id=uuid4(), type=kind, reference=f"oss://test/{step_id}"
        )

    # research
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(task_id=task_id, step_id="research", status="completed", output=_ar("research", "structured"))
        )
    # script(开 gate)+ image_process(开 gate)
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(task_id=task_id, step_id="script", status="completed", output=_ar("script"))
        )
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(task_id=task_id, step_id="image_process", status="completed", output=_ar("image", "image_collection"))
        )
    # 关 script + image gate
    async with Session() as session:
        rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
        gates = {g.step_id: g for g in rows.scalars().all()}
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.resolve_hitl(gates["script"].id, resolution="approved")
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.resolve_hitl(gates["image_process"].id, resolution="approved")
    # bgm
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(task_id=task_id, step_id="bgm", status="completed", output=_ar("bgm", "audio"))
        )
    # video_compose
    async with Session() as session:
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        await runner.handle_result(
            AgentResult(task_id=task_id, step_id="video_compose", status="completed", output=_ar("video", "video"))
        )

    # 用户在 final 终审:modify 换 BGM
    async with Session() as session:
        rows = await session.execute(select(HITLGate).where(HITLGate.task_id == task_id))
        final_gate = next(
            g for g in rows.scalars().all() if g.step_id == "video_compose" and g.closed_at is None
        )
        runner = TaskRunner(session, dispatcher=fake_dispatch, publisher=fake_publish)
        out = await runner.resolve_hitl(
            final_gate.id,
            resolution="modified",
            user_choice={"target_step": "bgm"},
        )

    # bgm 应该被重置 + 重派
    assert "bgm" in out, f"modify should re-dispatch bgm, got {out}"
    redispatched_bgm_count = sum(1 for t in dispatched if t.step_id == "bgm")
    assert redispatched_bgm_count == 2  # 第一次 + modify 重派
