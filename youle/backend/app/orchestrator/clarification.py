"""子模块 4:澄清生成器(铁律 6:永远选择题)。

4 种形式:single_select / multi_select / image_compare / version_compare
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ClarificationForm = Literal["single_select", "multi_select", "image_compare", "version_compare", "image_upload"]


class Clarification(BaseModel):
    field: str
    form: ClarificationForm
    question: str
    options: list[Any] = Field(default_factory=list)
    default: Any | None = None
    timeout_seconds: int = 60


def generate_clarification(missing_fields: list[dict[str, Any]]) -> Clarification | None:
    """优先选第一个缺失字段;返回 None 表示无需澄清。"""
    if not missing_fields:
        return None
    field = missing_fields[0]
    form: ClarificationForm = field.get("clarification_form", "single_select")
    return Clarification(
        field=field["name"],
        form=form,
        question=f"请选择 {field['name']}",
        options=field.get("options", []),
        default=field.get("default"),
        timeout_seconds=60,
    )
