"""IP 限流服务:INCR+EXPIRE 原子计数。限流是保护措施,Redis 故障必须放行。"""

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = structlog.get_logger(__name__)


class RateLimitService:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check(self, key: str, limit: int, window_seconds: int) -> bool:
        """对 key 计数一次,窗口内计数超过 limit 返回 False(拒绝)。

        INCR+EXPIRE 在事务 pipeline 中原子执行;EXPIRE 带 NX,
        仅在 key 尚无过期时间时设置,保证窗口从首次访问起算。
        """
        try:
            pipeline = self._redis.pipeline(transaction=True)
            pipeline.incr(key)
            pipeline.expire(key, window_seconds, nx=True)
            results = await pipeline.execute()
        except RedisError:
            logger.warning("rate_limit_redis_unavailable", key=key, action="allow")
            return True

        count = int(results[0])
        return count <= limit
