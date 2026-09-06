"""认证路由:注册、登录。业务逻辑在 AuthService。"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field

from tradewinds.api.deps import get_auth_service, ip_rate_limit
from tradewinds.models.user import User
from tradewinds.services.auth_service import AuthService, TokenPair

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(ip_rate_limit("auth"))])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, description="密码强度最低 8 位")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserRead(BaseModel):
    id: int
    email: str

    model_config = {"from_attributes": True}


def _to_user_read(user: User) -> UserRead:
    return UserRead.model_validate(user)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)
) -> UserRead:
    return _to_user_read(await auth_service.register(payload.email, payload.password))


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest, auth_service: AuthService = Depends(get_auth_service)
) -> TokenPair:
    return await auth_service.login(payload.email, payload.password)
