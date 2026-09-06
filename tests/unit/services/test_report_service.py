"""周期报告单元测试:周期桶边界与 Markdown 渲染(纯函数)。"""

from datetime import UTC, datetime

from tradewinds.models.topic import Cadence, Topic
from tradewinds.services.report_service import period_bounds, render_report_markdown


def _topic(cadence: Cadence) -> Topic:
    return Topic(id=1, user_id=1, name="AI Agent 动态", description="d", cadence=cadence)


def test_daily_period_bounds_is_utc_day() -> None:
    now = datetime(2026, 9, 6, 15, 30, tzinfo=UTC)
    start, end = period_bounds(now, Cadence.daily)

    assert start == datetime(2026, 9, 6, 0, 0, tzinfo=UTC)
    assert (end - start).days == 1


def test_weekly_period_bounds_start_on_monday() -> None:
    now = datetime(2026, 9, 6, 15, 30, tzinfo=UTC)  # 周日

    start, end = period_bounds(now, Cadence.weekly)

    assert start.weekday() == 0  # 周一
    assert start == datetime(2026, 8, 31, 0, 0, tzinfo=UTC)
    assert (end - start).days == 7


def test_render_report_markdown_contains_items_sorted_by_score() -> None:
    from tradewinds.models.item import Item, ItemStatus

    def item(url: str, title: str, score: float) -> Item:
        return Item(
            topic_id=1,
            source="arxiv",
            url=url,
            url_hash=url,
            title=title,
            raw_content="c",
            score=score,
            summary=f"{title} 的摘要",
            status=ItemStatus.accepted,
        )

    items = [item("https://a/1", "低分条目", 3.0), item("https://a/2", "高分条目", 9.0)]
    bounds = period_bounds(datetime(2026, 9, 6, tzinfo=UTC), Cadence.daily)

    content = render_report_markdown(_topic(Cadence.daily), items, bounds=bounds)

    assert "# AI Agent 动态 日报" in content
    assert "共 2 条" in content
    # 按评分倒序:高分在前
    assert content.index("高分条目") < content.index("低分条目")
    assert "[高分条目](https://a/2)" in content
