"""API v1 路由聚合。"""

from fastapi import APIRouter

from tradewinds.api.v1 import auth, topics, users

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(topics.router)
