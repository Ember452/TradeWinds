"""RetrievalPlan schema 测试:字段契约与边界校验。"""

import pytest
from pydantic import ValidationError

from tradewinds.agents.schemas.retrieval_plan import GitHubQuery, RetrievalPlan, SourceName


def _valid_plan_data() -> dict:
    return {
        "keywords": ["AI Agent", "tool use"],
        "sources": ["arxiv", "hackernews"],
        "arxiv_categories": ["cs.AI"],
        "github": {"keywords": ["agent framework"], "language": "python"},
        "window_days": 7,
        "relevance_criteria": ["近一周内与 LLM Agent 直接相关"],
    }


def test_valid_plan_parses() -> None:
    plan = RetrievalPlan.model_validate(_valid_plan_data())

    assert plan.keywords == ["AI Agent", "tool use"]
    assert SourceName("arxiv") in plan.sources
    assert plan.github is not None
    assert plan.github.language == "python"


def test_sources_restricted_to_known_set() -> None:
    data = _valid_plan_data()
    data["sources"] = ["twitter"]

    with pytest.raises(ValidationError):
        RetrievalPlan.model_validate(data)


def test_window_days_bounded() -> None:
    for bad in (0, 32):
        data = _valid_plan_data()
        data["window_days"] = bad
        with pytest.raises(ValidationError):
            RetrievalPlan.model_validate(data)


def test_keywords_min_and_max() -> None:
    data = _valid_plan_data()
    data["keywords"] = ["only-one"]
    with pytest.raises(ValidationError):
        RetrievalPlan.model_validate(data)

    data["keywords"] = [f"kw{i}" for i in range(13)]
    with pytest.raises(ValidationError):
        RetrievalPlan.model_validate(data)


def test_github_query_optional() -> None:
    data = _valid_plan_data()
    data["github"] = None

    plan = RetrievalPlan.model_validate(data)

    assert plan.github is None


def test_github_query_language_optional() -> None:
    query = GitHubQuery(keywords=["rag"])

    assert query.keywords == ["rag"]
    assert query.language is None
