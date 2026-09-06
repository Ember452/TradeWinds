"""Planner 金标集评测:CI 必跑,防止 prompt/Schema 改动引入回归。

机制说明:每个用例含"描述→计划要点"的期望(assert)与一段"模型产物固件"
(model_output,录制自真实 LLM 输出)。测试回放固件产物并断言期望要点,
断言"关键词覆盖与源选择",不做逐字比对(design.md 第 9 节)。
引入真实 LLM 在线评测时,只需把回放 provider 换成真实 provider,断言不变。
"""

import json
import pathlib
from typing import Any

import pytest

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan

CASES_PATH = pathlib.Path(__file__).parent / "golden" / "planner_cases.json"


def _cases() -> list[dict[str, Any]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def _keyword_matched(plan_keywords: list[str], terms: list[str]) -> list[str]:
    folded = [k.casefold() for k in plan_keywords]
    return [term for term in terms if any(term.casefold() in k for k in folded)]


def _assert_expectations(plan: RetrievalPlan, expect: dict[str, Any]) -> None:
    matched = _keyword_matched(plan.keywords, expect["keywords_any"])
    assert len(matched) >= expect["keywords_min_matched"], (
        f"关键词覆盖不足:{matched} / 期望任一命中 {expect['keywords_any']}"
    )

    for source in expect["sources_must_include"]:
        assert source in [s.value for s in plan.sources], f"缺少必需信息源:{source}"

    assert plan.window_days <= expect["window_days_max"]

    if expect["require_arxiv_categories"]:
        assert plan.arxiv_categories, "选择了 arxiv 但未给出分类"
    if expect["require_github_query"]:
        assert plan.github is not None, "选择了 github 但未给出查询参数"


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["id"])
def test_planner_golden_case(case: dict[str, Any]) -> None:
    # 固件产物必须先通过 Schema 校验——这是 Planner 管道的第一道闸
    plan = RetrievalPlan.model_validate(case["model_output"])

    _assert_expectations(plan, case["expect"])


def test_golden_set_has_at_least_10_cases() -> None:
    # 金标集随迭代扩充(design.md 第 9 节),规模下限防止目录被清空后测试静默变空
    assert len(_cases()) >= 10


def test_golden_cases_are_unique_and_wellformed() -> None:
    ids = [c["id"] for c in _cases()]
    assert len(ids) == len(set(ids))
    for case in _cases():
        assert case["cadence"] in ("daily", "weekly")
        assert set(case["expect"]) == {
            "keywords_any",
            "keywords_min_matched",
            "sources_must_include",
            "window_days_max",
            "require_arxiv_categories",
            "require_github_query",
        }
