"""推送单元测试:邮件模板与内容指纹(纯函数,不依赖数据库)。"""

from datetime import UTC, datetime

from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.topic import Cadence, Topic
from tradewinds.push.templates import render_digest_email
from tradewinds.services.push_service import digest_key_of


def _topic() -> Topic:
    return Topic(id=9, user_id=1, name="AI <动态>", description="d", cadence=Cadence.weekly)


def _item(i: int) -> Item:
    return Item(
        topic_id=9,
        source="arxiv",
        url=f"https://example.com/{i}",
        url_hash=f"h{i}",
        title=f"标题 {i} <b>",
        raw_content="c",
        summary=f"摘要 {i}",
        status=ItemStatus.accepted,
        published_at=datetime(2026, 9, 5, tzinfo=UTC),
    )


def test_digest_email_contains_unsubscribe_and_source() -> None:
    payload = render_digest_email(
        topic=_topic(), items=[_item(1)], to="u@example.com", app_base_url="https://tw.test"
    )

    assert "/api/v1/topics/9/mute" in payload.html
    assert "退订" in payload.text
    assert "来源:arxiv" in payload.html
    assert "标题 1" in payload.html


def test_digest_email_escapes_html() -> None:
    payload = render_digest_email(
        topic=_topic(), items=[_item(1)], to="u@example.com", app_base_url="https://tw.test"
    )

    assert "AI &lt;动态&gt;" in payload.html
    assert "标题 1 &lt;b&gt;" in payload.html


def test_digest_key_order_insensitive_and_stable() -> None:
    a = digest_key_of(["https://a", "https://b"])
    b = digest_key_of(["https://b", "https://a"])
    c = digest_key_of(["https://a", "https://c"])

    assert a == b
    assert a != c
