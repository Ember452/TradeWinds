"""RateLimiter 速率控制测试:并发上限与请求间隔。"""

import asyncio
import time
from itertools import pairwise

from tradewinds.tools.base import RateLimiter


async def test_min_interval_between_requests() -> None:
    limiter = RateLimiter(max_concurrency=5, min_interval_seconds=0.05)
    stamps: list[float] = []

    async def touch() -> None:
        stamps.append(time.monotonic())

    for _ in range(3):
        await limiter.run(touch)

    # 相邻两次请求的时间差
    gaps = [b - a for a, b in pairwise(stamps)]
    assert all(gap >= 0.04 for gap in gaps)


async def test_concurrency_capped_by_semaphore() -> None:
    limiter = RateLimiter(max_concurrency=2, min_interval_seconds=0.0)
    current = 0
    peak = 0

    async def work() -> None:
        nonlocal current, peak
        current += 1
        peak = max(peak, current)
        await asyncio.sleep(0.02)
        current -= 1

    await asyncio.gather(*(limiter.run(work) for _ in range(6)))

    assert peak <= 2
