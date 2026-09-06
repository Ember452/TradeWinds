"""条目落库:指纹加载与批量创建(pending 状态),供管道调用。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.text import truncate_text
from tradewinds.models.item import Item, ItemStatus
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
