"""全局异常处理:业务异常 → 统一错误响应体 {code, message}。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tradewinds.core.exceptions import TradeWindsError


async def tradewinds_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Starlette 只对本模块注册的异常类型调用此 handler,断言仅为收窄类型
    assert isinstance(exc, TradeWindsError)
    return JSONResponse(
        status_code=exc.status_code, content={"code": exc.code, "message": exc.message}
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TradeWindsError, tradewinds_error_handler)
