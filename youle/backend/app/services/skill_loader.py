"""Skill YAML 加载器(Sprint 4 用)。

铁律 9:Skill YAML 是契约;启动时把 skills/ 下的 yaml load 到 DB(idempotent upsert)。
也提供 by skill_id 直接读 yaml 文件的快捷方式(测试 / dev)。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

# 项目内 skills 目录(相对于本文件;运行容器里也挂相同位置)
SKILLS_DIR = Path(__file__).resolve().parents[3] / "skills"


@lru_cache(maxsize=64)
def load_skill_by_id(skill_id: str) -> dict[str, Any]:
    """从 skills/<skill_id>.yaml 读取(失败抛 KeyError)。"""
    path = SKILLS_DIR / f"{skill_id}.yaml"
    if not path.is_file():
        raise KeyError(f"skill {skill_id} not found at {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_available_skills() -> list[str]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p.stem for p in SKILLS_DIR.glob("*.yaml"))
