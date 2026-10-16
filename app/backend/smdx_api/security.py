"""CSRF 対策。

状態を変える API(POST/PUT/PATCH/DELETE)は、画面が付ける独自ヘッダ
`X-Requested-With: smdx` が無い要求を 403 で拒否する。
"""
from collections.abc import Mapping

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "smdx"
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
FORBIDDEN_DETAIL = "この操作を行う権限がありません"


def is_csrf_safe(method: str, headers: Mapping[str, str]) -> bool:
    if method.upper() not in STATE_CHANGING_METHODS:
        return True
    # ヘッダ名は大文字小文字を区別しない
    lowered = {k.lower(): v for k, v in headers.items()}
    return lowered.get(CSRF_HEADER.lower()) == CSRF_VALUE


class CsrfMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not is_csrf_safe(scope["method"], Headers(scope=scope)):
            response = JSONResponse({"detail": FORBIDDEN_DETAIL}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
