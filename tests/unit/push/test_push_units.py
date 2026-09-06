"""推送单元测试:邮件模板与内容指纹(纯函数,不依赖数据库)。"""

from datetime import UTC, datetime

from tradewinds.models.item import Item, ItemStatus
from tradewinds.models.report import Report, ReportPeriodType
from tradewinds.models.topic import Cadence, Topic
from tradewinds.push.templates import render_digest_email, render_report_email
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


def _report() -> Report:
    return Report(
        topic_id=9,
        user_id=1,
        period_type=ReportPeriodType.weekly,
        period_start=datetime(2026, 8, 31, tzinfo=UTC),
        period_end=datetime(2026, 9, 7, tzinfo=UTC),
        item_ids=[1, 2],
        content="# AI <动态> 周报\n- [条目A](https://example.com/1)",
    )


def test_report_email_contains_period_and_unsubscribe() -> None:
    payload = render_report_email(
        topic=_topic(), report=_report(), to="u@example.com", app_base_url="https://tw.test"
    )

    assert "周期报告" in payload.subject
    assert "AI <动态>" in payload.subject
    assert "2026-08-31" in payload.text and "2026-09-07" in payload.text
    assert "/api/v1/topics/9/mute" in payload.html
    assert "退订" in payload.text
    assert "条目A" in payload.text


def test_report_email_escapes_html() -> None:
    payload = render_report_email(
        topic=_topic(), report=_report(), to="u@example.com", app_base_url="https://tw.test"
    )

    assert "AI &lt;动态&gt;" in payload.html
