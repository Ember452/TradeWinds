"""用户偏好画像:跨会话记忆的第一步。

信号源(按权重降序):
1. 点击历史(用户点开过的条目 → 其聚类键,最强正反馈)
2. 同用户其他主题的关键词(兴趣面的粗粒度表达)

画像以关键词列表形式注入 Analyst 评分上下文(仅作参考信号,
判定仍以本主题判定标准为准),不改变评分契约。
"""

import structlog
from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.models.engagement import ItemClick
from tradewinds.models.item import Item
from tradewinds.models.topic import Topic

logger = structlog.get_logger(__name__)

_PREFERENCE_LIMIT = 12


def build_scoring_prompt_section(preferences: list[str]) -> str:
    """把偏好画像渲染为评分 prompt 的附加段落;空画像返回空串。"""
    if not preferences:
        return ""
    lines = ["", "用户历史偏好(该用户其他主题与点击历史的摘要,仅作参考信号):"]
    lines += [f"- {p}" for p in preferences]
    lines.append("判定仍以本主题判定标准为准;偏好仅用于评分接近时的取舍与推荐理由。")
    return "\n".join(lines)


async def build_profile(session: AsyncSession, user_id: int, *, exclude_topic_id: int) -> list[str]:
    """聚合用户偏好画像:点击条目的聚类键优先,其余主题关键词次之,去重限量。"""
    preferences: list[str] = []
    seen: set[str] = set()

    clicked_clusters = await session.scalars(
        select(distinct(Item.cluster_key))
        .join(ItemClick, ItemClick.item_id == Item.id)
        .where(ItemClick.user_id == user_id)
        .where(Item.cluster_key.is_not(None))
        .where(Item.topic_id != exclude_topic_id)
        .order_by(Item.id.desc())
        .limit(_PREFERENCE_LIMIT)
    )
    for cluster in clicked_clusters:
        label = f"关注过的内容方向:{cluster}"
        if label not in seen:
            seen.add(label)
            preferences.append(label)

    topics = await session.scalars(
        select(Topic).where(Topic.user_id == user_id, Topic.id != exclude_topic_id)
    )
    for topic in topics:
        plan = topic.plan or {}
        keywords = plan.get("keywords")
        if isinstance(keywords, list):
            for keyword in keywords[:4]:
                label = f"订阅过相关主题:{keyword}"
                if label not in seen:
                    seen.add(label)
                    preferences.append(label)
        if len(preferences) >= _PREFERENCE_LIMIT:
            break

    if preferences:
        logger.debug("preference_profile_built", user_id=user_id, size=len(preferences))
    return preferences[:_PREFERENCE_LIMIT]
