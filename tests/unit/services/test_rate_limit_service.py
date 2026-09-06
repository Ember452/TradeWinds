"""RateLimitService 单元测试:INCR+EXPIRE 计数、超限拒绝、Redis 故障放行。"""

from redis.exceptions import ConnectionError as RedisConnectionError

from tradewinds.services.rate_limit_service import RateLimitService


class FakePipeline:
    def __init__(self, store: dict[str, int], fail_on_execute: bool) -> None:
        self._store = store
        self._fail = fail_on_execute
        self._ops: list[tuple[str, tuple[object, ...]]] = []

    def incr(self, key: str) -> None:
        self._ops.append(("incr", (key,)))

    def expire(self, key: str, window_seconds: int, *, nx: bool = False) -> None:
        self._ops.append(("expire", (key, window_seconds, nx)))

    async def execute(self) -> list[object]:
        if self._fail:
            raise RedisConnectionError("redis down")
        results: list[object] = []
        for op, args in self._ops:
            if op == "incr":
                key = str(args[0])
                self._store[key] = self._store.get(key, 0) + 1
                results.append(self._store[key])
            elif op == "expire":
                results.append(True)
        return results


class FakeRedis:
    def __init__(self, fail_on_execute: bool = False) -> None:
        self.store: dict[str, int] = {}
        self._fail = fail_on_execute

    def pipeline(self, *, transaction: bool = True) -> FakePipeline:
        return FakePipeline(self.store, self._fail)


async def test_within_limit_returns_true() -> None:
    service = RateLimitService(FakeRedis())

    assert await service.check("rl:auth:1.2.3.4", limit=3, window_seconds=60)
    assert await service.check("rl:auth:1.2.3.4", limit=3, window_seconds=60)


async def test_over_limit_returns_false() -> None:
    service = RateLimitService(FakeRedis())

    assert await service.check("k", limit=2, window_seconds=60)
    assert await service.check("k", limit=2, window_seconds=60)
    assert not await service.check("k", limit=2, window_seconds=60)


async def test_redis_unavailable_allows_request() -> None:
    # 限流是保护措施:Redis 不可用必须放行,不能因此停服
    service = RateLimitService(FakeRedis(fail_on_execute=True))

    assert await service.check("k", limit=1, window_seconds=60)


async def test_keys_are_isolated_per_client() -> None:
    service = RateLimitService(FakeRedis())

    assert await service.check("k:a", limit=1, window_seconds=60)
    assert await service.check("k:b", limit=1, window_seconds=60)
