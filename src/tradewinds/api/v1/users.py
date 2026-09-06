"""用户路由:当前用户信息。"""

from fastapi import APIRouter, Depends

from tradewinds.api.deps import get_current_user
from tradewinds.api.v1.auth import UserRead
from tradewinds.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)
