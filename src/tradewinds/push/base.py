"""推送渠道协议:渠道失败以 PushReceipt 返回(不抛异常),由推送服务记入 push_log。"""

from typing import Protocol

from pydantic import BaseModel


class PushPayload(BaseModel):
    to: str
    subject: str
    html: str
    text: str


class PushReceipt(BaseModel):
    ok: bool
    error: str | None = None


class PushChannel(Protocol):
    name: str

    async def send(self, payload: PushPayload) -> PushReceipt: ...
