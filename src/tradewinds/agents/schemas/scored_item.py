"""Analyst 评分 schema:LLM 结构化输出与角色间传递模型。"""

from pydantic import BaseModel, Field

from tradewinds.tools.base import CandidateItem


class ItemScore(BaseModel):
    """LLM 对单条候选的评分产物。"""

    url: str
    score: float = Field(ge=0, le=10)
    cluster_key: str = Field(description="聚类键:同一事件/主题的小写短标识")


class AnalystOutput(BaseModel):
    items: list[ItemScore]


class ScoredItem(BaseModel):
    """合并后的评分条目:原候选 + 评分与聚类键。"""

    item: CandidateItem
    score: float
    cluster_key: str
