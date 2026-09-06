"""core/text:无业务语义的文本工具。"""

import re

_WHITESPACE = re.compile(r"\s+")


def truncate_text(text: str, max_chars: int, *, suffix: str = "…") -> str:
    """按字符数截断长文本;截断处补省略号,保证产物长度可预期。"""
    if max_chars <= 0:
        raise ValueError("max_chars 必须为正数")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def normalize_whitespace(text: str) -> str:
    """压平空白字符:抓取的正文/标题常含换行与多空格。"""
    return _WHITESPACE.sub(" ", text).strip()
