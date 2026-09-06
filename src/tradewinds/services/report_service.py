"""周期报告服务:按主题 x 周期聚合 accepted 条目,幂等 upsert,分享 token。

聚合口径:条目按 created_at 落入周期桶;每次管道 run 重算当前周期报告
(同周期多次 run 只更新一份报告)。分享页经 share_token 公开访问。
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tradewinds.core.exceptions import NotFoundError
from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.report import Report, ReportPeriodType
from tradewinds.models.topic import Cadence, Topic


def period_bounds(now: datetime, cadence: Cadence) -> tuple[datetime, datetime]:
    """周期桶边界(UTC):daily=[当日 00:00,+1d);weekly=[本周一 00:00,+7d)。"""
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if cadence is Cadence.daily:
        return day_start, day_start + timedelta(days=1)
    monday = day_start - timedelta(days=day_start.weekday())
    return monday, monday + timedelta(days=7)


def render_report_markdown(
    topic: Topic, items: list[Item], *, bounds: tuple[datetime, datetime]
) -> str:
    """聚合为 Markdown:标题+条目列表(链接/来源/评分/摘要)。"""
    start, end = bounds
    heading = f"# {topic.name} 周报" if topic.cadence is Cadence.weekly else f"# {topic.name} 日报"
    lines = [
        heading,
        f"\n统计区间:{start.date().isoformat()} ~ {end.date().isoformat()}"
        f"(UTC),共 {len(items)} 条。",
        "",
    ]
    for item in sorted(items, key=lambda i: i.score or 0, reverse=True):
        score = f"{item.score:.1f}" if item.score is not None else "-"
        lines.append(f"- [{item.title}]({item.url})(来源:{item.source},评分:{score})")
        if item.summary:
            lines.append(f"  {item.summary}")
    return "\n".join(lines)


class ReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_period_report(self, topic: Topic, *, now: datetime) -> Report | None:
        """重算当前周期报告(主题内 accepted 条目);周期内无条目返回 None。"""
        period_type = (
            ReportPeriodType.daily if topic.cadence is Cadence.daily else ReportPeriodType.weekly
        )
        bounds = period_bounds(now, topic.cadence)
        start, end = bounds

        items = list(
            (
                await self._session.scalars(
                    select(Item)
                    .where(Item.topic_id == topic.id)
                    .where(Item.status == ItemStatus.accepted)
                    .where(Item.created_at >= start)
                    .where(Item.created_at < end)
                )
            ).all()
        )
        if not items:
            return None

        report = await self._session.scalar(
            select(Report).where(
                Report.topic_id == topic.id,
                Report.period_type == period_type,
                Report.period_start == start,
            )
        )
        if report is None:
            report = Report(
                topic_id=topic.id,
                user_id=topic.user_id,
                period_type=period_type,
                period_start=start,
                period_end=end,
                item_ids=[item.id for item in items],
                content=render_report_markdown(topic, items, bounds=bounds),
            )
            self._session.add(report)
        else:
            report.item_ids = [item.id for item in items]
            report.content = render_report_markdown(topic, items, bounds=bounds)
        await self._session.commit()
        await self._session.refresh(report)
        return report

    async def list_for_topic(self, user_id: int, topic_id: int) -> list[Report]:
        # 归属校验:跨用户访问主题 → 404,不泄露存在性
        topic = await self._session.get(Topic, topic_id)
        if topic is None or topic.user_id != user_id:
            raise NotFoundError("主题不存在")
        result = await self._session.scalars(
            select(Report)
            .where(Report.topic_id == topic_id, Report.user_id == user_id)
            .order_by(Report.period_start.desc())
        )
        return list(result)

    async def get(self, user_id: int, report_id: int) -> Report:
        report = await self._session.get(Report, report_id)
        if report is None or report.user_id != user_id:
            raise NotFoundError("报告不存在")
        return report

    async def share(self, user_id: int, report_id: int) -> Report:
        """生成(或复用)公开分享 token。"""
        report = await self.get(user_id, report_id)
        if report.share_token is None:
            report.share_token = secrets.token_urlsafe(16)
            await self._session.commit()
            await self._session.refresh(report)
        return report

    async def get_by_share_token(self, token: str) -> Report:
        report = await self._session.scalar(select(Report).where(Report.share_token == token))
        if report is None:
            raise NotFoundError("报告不存在")
        return report

    async def topic_title_of(self, report: Report) -> str:
        topic = await self._session.get(Topic, report.topic_id)
        return topic.name if topic else "报告"
