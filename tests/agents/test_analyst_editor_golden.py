"""Analyst/Editor 金标集评测:prompt 变更回归门禁,CI 必跑。

与 Planner 金标同一模式(录制固件 + 期望断言,不逐字比对):
固件为"模型产物录制",期望为"业务要点"。prompt 或 schema 变更导致
产物结构/业务语义漂移时,这里的断言会失败——这就是回归门禁。
"""

import json
import pathlib
from typing import Any

import pytest

GOLDEN_DIR = pathlib.Path(__file__).parent / "golden"

ANALYST_MIN_CASES = 8
EDITOR_MIN_CASES = 6


def _load(name: str) -> list[dict[str, Any]]:
    return json.loads((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def _assert_analyst_expectations(case: dict[str, Any]) -> None:
    expect = case["expect"]
    items = {entry["url"]: entry for entry in case["model_output"]["items"]}

    if "url" in expect:
        entry = items.get(expect["url"])
        assert entry is not None, "期望评分的条目未被输出"
        assert entry["score"] >= expect["min_score"], f"评分低于下限:{entry}"
        assert entry["score"] <= expect["max_score"], f"评分高于上限:{entry}"

    if expect.get("shared_cluster"):
        clusters = {entry["cluster_key"] for entry in case["model_output"]["items"]}
        assert len(clusters) == 1, f"同一事件的聚类键应一致,实际:{clusters}"

    if expect.get("coverage") == "all_inputs_in_output":
        assert expect["url"] in items, "输入条目必须出现在输出中"


@pytest.mark.parametrize("case", _load("analyst_cases.json"), ids=lambda c: c["id"])
def test_analyst_golden_case(case: dict[str, Any]) -> None:
    _assert_analyst_expectations(case)


def test_analyst_scores_within_ten_band() -> None:
    for case in _load("analyst_cases.json"):
        for entry in case["model_output"]["items"]:
            assert 0 <= entry["score"] <= 10, f"{case['id']}: 评分越界 {entry}"
            assert entry["cluster_key"] == entry["cluster_key"].lower(), (
                f"{case['id']}: 聚类键必须小写 {entry}"
            )


def _assert_editor_expectations(case: dict[str, Any]) -> None:
    expect = case["expect"]
    output = case["model_output"]

    assert expect["min_summary_len"] <= len(output["summary"]) <= expect["max_summary_len"], (
        f"摘要长度越界:{len(output['summary'])}"
    )
    assert output["reason"], "reason 不得为空"
    if "reason_min_len" in expect:
        assert len(output["reason"]) >= expect["reason_min_len"]
    if "entity" in expect:
        assert expect["entity"] in output["summary"], (
            f"摘要必须保留核心实体 {expect['entity']!r}:{output['summary']}"
        )
    if expect.get("forbidden_numbers"):
        # 内容未披露数字时,摘要不得出现编造的数字
        import re

        assert not re.search(r"\d+%|\d+\.\d", output["summary"]), (
            f"内容未含数据,摘要不得出现编造数字:{output['summary']}"
        )


@pytest.mark.parametrize("case", _load("editor_cases.json"), ids=lambda c: c["id"])
def test_editor_golden_case(case: dict[str, Any]) -> None:
    _assert_editor_expectations(case)


def test_golden_sets_scale_guards() -> None:
    """门禁守卫:金标集被清空/裁剪时让测试显式失败,而非静默失去保护。"""
    assert len(_load("analyst_cases.json")) >= ANALYST_MIN_CASES
    assert len(_load("editor_cases.json")) >= EDITOR_MIN_CASES
    planner_cases = json.loads((GOLDEN_DIR / "planner_cases.json").read_text(encoding="utf-8"))
    assert len(planner_cases) >= 10
