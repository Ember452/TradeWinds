"""Editor 摘要 schema:单条目摘要与推荐理由。"""

from pydantic import BaseModel, Field


class ItemDigest(BaseModel):
    summary: str = Field(min_length=1, max_length=2000, description="面向用户的中文摘要")
    reason: str = Field(min_length=1, max_length=1000, description="为什么推荐这条:与主题的关系")
