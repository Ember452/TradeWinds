"""条目落库与查询:指纹去重、批量创建、keyset 分页读取。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.exceptions import NotFoundError
from tradewinds.core.text import truncate_text
from tradewinds.models.engagement import ItemClick
from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.topic import Topic
from tradewinds.tools.base import CandidateItem, url_hash

_TITLE_MAX = 500


async def load_seen_hashes(session: AsyncSession, topic_id: int) -> set[str]:
    """返回该主题全部已入库指纹,元素格式 '<topic_id>:<hash>'(与 is_seen 口径一致)。"""
    rows = await session.scalars(select(Item.url_hash).where(Item.topic_id == topic_id))
    return {f"{topic_id}:{url_hash_value}" for url_hash_value in rows}


async def create_pending_items(
    session: AsyncSession, topic_id: int, candidates: list[CandidateItem]
) -> list[Item]:
    """把新候选落库为 pending 条目;批内与库内指纹均去重,返回真正新建的条目。"""
    seen_in_batch: set[str] = set()
    items: list[Item] = []
    for candidate in candidates:
        digest = url_hash(candidate.url, topic_id)
        if digest in seen_in_batch:
            continue
        seen_in_batch.add(digest)
        items.append(
            Item(
                topic_id=topic_id,
                source=candidate.source,
                url=candidate.url,
                url_hash=digest,
                title=truncate_text(candidate.title, _TITLE_MAX, suffix=""),
                raw_content=candidate.raw_content,
                published_at=candidate.published_at,
                status=ItemStatus.pending,
            )
        )
    if items:
        session.add_all(items)
        await session.flush()
    return items


async def record_click(session: AsyncSession, user_id: int, item_id: int) -> bool:
    """记录一次点击;重复点击幂等(返回是否新建)。

    归属校验:条目所属主题不属于该用户 → 404(不泄露存在性)。
    """
    item = await session.get(Item, item_id)
    if item is None:
        raise NotFoundError("条目不存在")
    topic = await session.get(Topic, item.topic_id)
    if topic is None or topic.user_id != user_id:
        raise NotFoundError("条目不存在")

    existing = await session.scalar(
        select(ItemClick).where(ItemClick.user_id == user_id, ItemClick.item_id == item_id)
    )
    if existing is not None:
        return False
    session.add(ItemClick(user_id=user_id, item_id=item_id))
    await session.commit()
    return True


async def list_items(
    session: AsyncSession,
    topic_id: int,
    *,
    cursor: int | None = None,
    min_score: float | None = None,
    limit: int = 20,
) -> tuple[list[Item], int | None]:
    """keyset 分页(禁止 offset 深翻页):按 id 倒序,返回 (条目, 下一页游标)。

    默认只返回 accepted 条目;命中 limit+1 条说明还有下一页,第 limit+1 条不返回。
    查询条件均为 (topic_id, id) 前缀,走 ix_items_topic_id 索引。
    """
    query = (
        select(Item)
        .where(Item.topic_id == topic_id)
        .where(Item.status == ItemStatus.accepted)
        .order_by(Item.id.desc())
        .limit(limit + 1)
    )
    if cursor is not None:
        query = query.where(Item.id < cursor)
    if min_score is not None:
        query = query.where(Item.score >= min_score)

    rows = list((await session.scalars(query)).all())
    next_cursor = rows[limit].id if len(rows) > limit else None
    return rows[:limit], next_cursor
