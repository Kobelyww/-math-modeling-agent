"""Production security helpers for FastAPI."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .settings import WebSettings


PUBLIC_PATHS = {"/health", "/ready"}


class ApiTokenMiddleware(BaseHTTPMiddleware):
    """Require an API token for production API routes."""

    def __init__(self, app, settings: WebSettings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next):
        if not self.settings.require_auth:
            return await call_next(request)
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        expected = self.settings.web_api_token
        supplied = _request_token(request)
        if not expected or supplied != expected:
            return JSONResponse(status_code=401, content={"error": "Unauthorized"})
        return await call_next(request)


def _request_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-zh-api-key", "").strip()


def install_security(app: FastAPI, settings: WebSettings) -> None:
    app.add_middleware(ApiTokenMiddleware, settings=settings)
