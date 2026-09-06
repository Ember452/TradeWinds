"""汇总邮件模板:双版本(HTML/纯文本),必须含退订链接与来源标注。"""

from html import escape

from tradewinds.models.item import Item
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
