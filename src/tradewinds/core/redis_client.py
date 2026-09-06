"""Redis 客户端工厂:统一在此创建,业务代码不自行连接。"""

from redis.asyncio import Redis


def create_redis_client(redis_url: str) -> Redis:
    """decode_responses:所有命令返回 str,业务侧不做 bytes 解码。"""
    return Redis.from_url(redis_url, decode_responses=True)
