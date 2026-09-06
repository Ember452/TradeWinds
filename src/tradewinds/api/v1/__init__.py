"""API v1 路由聚合。"""

from fastapi import APIRouter

from tradewinds.api.v1 import (
    auth,
    chat,
    conversations,
    items,
    ops,
    reports,
    topics,
    usage,
    users,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(topics.router)
api_v1_router.include_router(items.router)
api_v1_router.include_router(usage.router)
api_v1_router.include_router(ops.router)
api_v1_router.include_router(reports.router)
api_v1_router.include_router(conversations.router)
api_v1_router.include_router(chat.router)
