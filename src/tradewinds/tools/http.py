"""HTTP 请求助手:统一包一层速率控制与错误转换(→ SourceError)。"""

from typing import Any

import httpx

from tradewinds.core.exceptions import SourceError
from tradewinds.core.text import truncate_text
from tradewinds.tools.base import Limiter

RESPONSE_MAX_CHARS = 20_000


async def fetch_text(
    limiter: Limiter,
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> str:
    """GET 文本响应;网络错误/非 2xx 统一转 SourceError,响应体做上限截断。"""

    async def _do() -> str:
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise SourceError(f"请求失败 {url}:{exc}") from exc
        return truncate_text(response.text, RESPONSE_MAX_CHARS, suffix="")

    return await limiter.run(_do)
