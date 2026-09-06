"""检索计划(RetrievalPlan):Planner 的产物,Retriever 的输入。

字段契约见实施计划 Task 2.4 与 design.md 4.2;扩展字段须同步金标集与 prompt。
"""

import enum

from pydantic import BaseModel, Field


class SourceName(enum.StrEnum):
    arxiv = "arxiv"
    hackernews = "hackernews"
    github = "github"
    web = "web"


class GitHubQuery(BaseModel):
    """GitHub 搜索参数:语言与 star 下限可选。"""

    keywords: list[str] = Field(min_length=1, max_length=8)
    language: str | None = None
    min_stars: int | None = Field(default=None, ge=0)


class RetrievalPlan(BaseModel):
    """主题编译产物:关键词、源选择、arXiv 分类、GitHub 参数、时间窗与相关性标准。"""

    keywords: list[str] = Field(min_length=2, max_length=12)
    sources: list[SourceName] = Field(min_length=1)
    arxiv_categories: list[str] = Field(default_factory=list, max_length=8)
    github: GitHubQuery | None = None
    window_days: int = Field(ge=1, le=31)
    relevance_criteria: list[str] = Field(min_length=1, max_length=8)
