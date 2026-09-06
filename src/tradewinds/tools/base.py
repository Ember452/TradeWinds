"""信息源客户端公共协议:候选条目、URL 指纹去重、速率控制。

所有源客户端同构(architecture.md 第 5 节 SourceClient),新增源=新增一个实现。
"""

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, TypeVar
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel

from tradewinds.agents.schemas.retrieval_plan import RetrievalPlan

T = TypeVar("T")


class CandidateItem(BaseModel):
    """单源检索产出的原始候选条目,未经评分。"""

    source: str
    url: str
    title: str
    raw_content: str
    published_at: datetime | None = None


def normalize_url(url: str) -> str:
    """URL 规范化:小写 host、去默认端口、去尾部斜杠、去常见跟踪参数、稳定排序查询串。"""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower() or "https"
    host = (parts.hostname or "").lower()
    port = parts.port
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    params = sorted(parse_qsl(parts.query, keep_blank_values=True))
    tracking = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref"}
    filtered = [(k, v) for k, v in params if k not in tracking]

    path = parts.path.rstrip("/") if len(parts.path) > 1 else parts.path
    query = urlencode(filtered, quote_via=quote)
    return urlunsplit((scheme, netloc, path, query, ""))


def url_hash(url: str, topic_id: int) -> str:
    """条目指纹 = sha256(规范化 url + topic_id):同一 URL 在不同主题互不干扰。"""
    normalized = normalize_url(url)
    return hashlib.sha256(f"{normalized}|{topic_id}".encode()).hexdigest()


def is_seen(url: str, topic_id: int, seen_hashes: set[str]) -> bool:
    """指纹集合以 '<topic_id>:<hash>' 为元素;客户端据此做增量过滤。"""
    return f"{topic_id}:{url_hash(url, topic_id)}" in seen_hashes


class SourceClient(Protocol):
    """所有信息源同构;search 内部须用 seen_hashes 过滤已见 URL。"""

    name: str

    async def search(
        self, plan: RetrievalPlan, *, topic_id: int, seen_hashes: set[str]
    ) -> list[CandidateItem]: ...


class RateLimiter:
    """并发信号量 + 最小请求间隔,所有客户端共享同一实例;透传操作结果。"""

    def __init__(self, max_concurrency: int = 5, min_interval_seconds: float = 0.5) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._min_interval = min_interval_seconds
        self._last_request = 0.0
        self._lock = asyncio.Lock()

    async def run(self, operation: Callable[[], Awaitable[T]]) -> T:
        async with self._semaphore:
            async with self._lock:
                elapsed = time.monotonic() - self._last_request
                if elapsed < self._min_interval:
                    await asyncio.sleep(self._min_interval - elapsed)
                self._last_request = time.monotonic()
            return await operation()


@dataclass(frozen=True)
class SourceDegraded:
    """单源降级标记:Retriever 据此记 warning,不上抛中断管道。"""

    source: str
    reason: str
