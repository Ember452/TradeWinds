"""汇总邮件模板:双版本(HTML/纯文本),必须含退订链接与来源标注。"""

from html import escape

from tradewinds.models.item import Item
from tradewinds.models.report import Report, ReportPeriodType
from tradewinds.models.topic import Topic
from tradewinds.push.base import PushPayload


def render_digest_email(
    *, topic: Topic, items: list[Item], to: str, app_base_url: str
) -> PushPayload:
    unsubscribe_url = f"{app_base_url}/api/v1/topics/{topic.id}/mute"
    subject = f"TradeWinds 汇总:{topic.name}({len(items)} 条新内容)"

    rows_html = "".join(
        f'<li><a href="{escape(item.url)}">{escape(item.title)}</a>'
        f"<small> 来源:{escape(item.source)}</small>"
        f"<p>{escape(item.summary or '')}</p></li>"
        for item in items
    )
    html = (
        f"<html><body>"
        f"<p>您订阅的主题「{escape(topic.name)}」有以下新内容:</p>"
        f"<ul>{rows_html}</ul>"
        f'<p><a href="{escape(unsubscribe_url)}">退订此主题</a></p>'
        f"</body></html>"
    )

    lines_text = [
        f"您订阅的主题「{topic.name}」有以下新内容:",
        "",
    ]
    lines_text += [
        f"- {item.title}(来源:{item.source})\n  {item.url}\n  {item.summary or ''}"
        for item in items
    ]
    lines_text += ["", f"退订此主题:{unsubscribe_url}"]
    text = "\n".join(lines_text)

    return PushPayload(to=to, subject=subject, html=html, text=text)


def render_item_alert_email(*, topic: Topic, item: Item, to: str, app_base_url: str) -> PushPayload:
    """即时提醒邮件:单条高分条目,含退订链接与来源标注。"""
    unsubscribe_url = f"{app_base_url}/api/v1/topics/{topic.id}/mute"
    subject = f"TradeWinds 即时提醒:{item.title}"

    html = (
        "<html><body>"
        f"<p>您订阅的主题「{escape(topic.name)}」出现高相关性内容:</p>"
        f'<p><a href="{escape(item.url)}">{escape(item.title)}</a>'
        f"<small> 来源:{escape(item.source)}"
        f" · 评分:{item.score if item.score is not None else '-'}</small></p>"
        + (f"<p>{escape(item.summary or '')}</p>" if item.summary else "")
        + (f"<p><em>推荐理由:{escape(item.reason or '')}</em></p>" if item.reason else "")
        + f'<p><a href="{escape(unsubscribe_url)}">退订此主题</a></p>'
        "</body></html>"
    )
    text = "\n".join(
        [
            f"您订阅的主题「{topic.name}」出现高相关性内容:",
            f"{item.title}(来源:{item.source})",
            item.url,
            item.summary or "",
            item.reason or "",
            "",
            f"退订此主题:{unsubscribe_url}",
        ]
    )
    return PushPayload(to=to, subject=subject, html=html, text=text)


def render_report_email(*, topic: Topic, report: Report, to: str, app_base_url: str) -> PushPayload:
    """周期报告邮件:统计区间 + 报告内容,含退订链接。"""
    unsubscribe_url = f"{app_base_url}/api/v1/topics/{topic.id}/mute"
    kind = "周报" if report.period_type is ReportPeriodType.weekly else "日报"
    span = f"{report.period_start.date().isoformat()} ~ {report.period_end.date().isoformat()}"
    subject = (
        f"TradeWinds 周期报告:{topic.name} {kind}({report.period_start.date().isoformat()} 起)"
    )

    html = (
        "<html><body>"
        f"<p>您订阅的主题「{escape(topic.name)}」的{kind}已生成({escape(span)},UTC):</p>"
        f"<pre>{escape(report.content)}</pre>"
        f'<p><a href="{escape(unsubscribe_url)}">退订此主题</a></p>'
        "</body></html>"
    )
    text = "\n".join(
        [
            f"您订阅的主题「{topic.name}」的{kind}已生成({span},UTC):",
            "",
            report.content,
            "",
            f"退订此主题:{unsubscribe_url}",
        ]
    )
    return PushPayload(to=to, subject=subject, html=html, text=text)
