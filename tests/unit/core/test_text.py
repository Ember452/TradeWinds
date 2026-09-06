"""truncate_text 文本工具测试。"""

import pytest

from tradewinds.core.text import normalize_whitespace, truncate_text


def test_short_text_unchanged() -> None:
    assert truncate_text("短文本", 10) == "短文本"


def test_long_text_truncated_with_suffix() -> None:
    text = "a" * 100

    result = truncate_text(text, 10)

    assert result == "a" * 9 + "…"
    assert len(result) == 10


def test_exact_boundary_unchanged() -> None:
    text = "a" * 10

    assert truncate_text(text, 10) == text


def test_invalid_max_chars_raises() -> None:
    with pytest.raises(ValueError):
        truncate_text("x", 0)


def test_normalize_whitespace() -> None:
    assert normalize_whitespace("  hello \n world\t! ") == "hello world !"
