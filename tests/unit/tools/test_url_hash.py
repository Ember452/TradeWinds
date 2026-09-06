"""URL 指纹与规范化测试。"""

from tradewinds.tools.base import normalize_url, url_hash


def test_normalize_lowercases_host_and_strips_default_port() -> None:
    assert normalize_url("HTTPS://EXAMPLE.com:443/a/b/") == "https://example.com/a/b"


def test_normalize_removes_tracking_params_and_sorts_query() -> None:
    url = "https://example.com/p?b=2&utm_source=x&a=1"

    assert normalize_url(url) == "https://example.com/p?a=1&b=2"


def test_normalize_keeps_nondefault_port_and_keeps_root_slash() -> None:
    assert normalize_url("http://example.com:8080") == "http://example.com:8080"
    assert normalize_url("https://example.com/") == "https://example.com/"


def test_same_article_with_tracking_variants_share_hash() -> None:
    topic = 1
    a = url_hash("https://blog.example.com/post?utm_source=hn", topic)
    b = url_hash("https://blog.example.com/post", topic)

    assert a == b


def test_same_url_different_topics_get_different_hashes() -> None:
    url = "https://example.com/post"

    assert url_hash(url, 1) != url_hash(url, 2)
