"""邮件渠道:aiosmtplib 异步发送;SMTP 未配置/发送失败均以 receipt 返回。"""

import asyncio
from email.message import EmailMessage

import aiosmtplib
from pydantic import BaseModel

from tradewinds.push.base import PushPayload, PushReceipt


class EmailChannelConfig(BaseModel):
    host: str = ""
    port: int = 587
    username: str = ""
    password: str = ""
    sender: str = ""
    start_tls: bool = True


class EmailChannel:
    name = "email"

    def __init__(self, config: EmailChannelConfig) -> None:
        self._config = config

    async def send(self, payload: PushPayload) -> PushReceipt:
        if not self._config.host or not self._config.sender:
            return PushReceipt(ok=False, error="email_disabled")

        message = EmailMessage()
        message["From"] = self._config.sender
        message["To"] = payload.to
        message["Subject"] = payload.subject
        message.set_content(payload.text)
        message.add_alternative(payload.html, subtype="html")

        try:
            await asyncio.wait_for(
                aiosmtplib.send(
                    message,
                    hostname=self._config.host,
                    port=self._config.port,
                    username=self._config.username or None,
                    password=self._config.password or None,
                    start_tls=self._config.start_tls,
                ),
                timeout=30.0,
            )
        except (aiosmtplib.SMTPException, OSError, TimeoutError) as exc:
            return PushReceipt(ok=False, error=str(exc))
        return PushReceipt(ok=True)
