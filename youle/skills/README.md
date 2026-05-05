# Skills

铁律 9:Skill YAML 是契约,行为变更 = YAML 改 + version bump(v1.0 → v1.1)。

## V1 必上(2 个 hero)

- [`anti_fraud_video.yaml`](anti_fraud_video.yaml) — 反诈视频(3 道 HITL gate;V1 终审无回滚按钮)
- [`ecommerce_detail_image.yaml`](ecommerce_detail_image.yaml) — 电商详情图(1 道 quality_review gate)

## V1.5 路线

- [`short_video.yaml`](short_video.yaml) — **通用短视频制作 v0.5**(visibility=subscribed,与 anti_fraud_video v1.0 共享 video_compose 引擎)
- 海报模板 / 长文 / PPT 创作

> 短视频制作在 V2.0 曾为 hero,v3.0 回归反诈+电商详情图后降级 V1.5。技术上与 anti_fraud_video 共享同一条流水线和 Celery video_workflow,差异仅在 inputs_schema(主题/风格/平台)和 prompt_template。

## 校验

每个 Skill YAML 必须通过 `python -m skill_validator <file>`(Sprint 4 实现)。
