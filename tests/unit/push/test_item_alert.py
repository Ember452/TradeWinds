"""即时提醒邮件模板单元测试。"""

from datetime import UTC, datetime

from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.topic import Cadence, Topic
from tradewinds.push.templates import render_item_alert_email


def _item() -> Item:
    return Item(
        topic_id=9,
        source="arxiv",
        url="https://example.com/hot",
        url_hash="h",
        title="重大进展 <b>",
        raw_content="c",
        score=9.5,
        summary="摘要内容",
        reason="因为重要",
        status=ItemStatus.accepted,
        published_at=datetime(2026, 9, 6, tzinfo=UTC),
    )


def _topic() -> Topic:
    return Topic(id=9, user_id=1, name="AI 动态", description="d", cadence=Cadence.daily)


def test_alert_email_contains_key_info() -> None:
    payload = render_item_alert_email(
        topic=_topic(), item=_item(), to="u@example.com", app_base_url="https://tw.test"
    )

    assert payload.subject.startswith("TradeWinds 即时提醒:")
    assert "https://example.com/hot" in payload.html
    assert "来源:arxiv" in payload.html
    assert "9.5" in payload.html
    assert "推荐理由:因为重要" in payload.html
    assert "/api/v1/topics/9/mute" in payload.html


def test_alert_email_escapes_html() -> None:
    payload = render_item_alert_email(
        topic=_topic(), item=_item(), to="u@example.com", app_base_url="https://tw.test"
    )

    assert "重大进展 &lt;b&gt;" in payload.html
