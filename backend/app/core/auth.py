"""认证中间件 — API Key 鉴权

开发环境（feature_rbac=False）跳过鉴权，
生产环境（feature_rbac=True）校验 X-API-Key 请求头。
"""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


API_KEY_HEADER = "X-API-Key"


class AuthMiddleware(BaseHTTPMiddleware):
    """简单 API Key 鉴权中间件"""

    async def dispatch(self, request: Request, call_next):
        # 开发环境跳过鉴权
        if not settings.feature_rbac:
            return await call_next(request)

        # 健康检查和 Swagger 文档不鉴权
        if request.url.path in ("/api/v1/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # 校验 API Key
        api_key = request.headers.get(API_KEY_HEADER)
        if not api_key or api_key != settings.api_key:
            return JSONResponse(
                status_code=401,
                content={"code": 30002, "message": "未授权访问，请提供有效的 API Key"},
            )

        return await call_next(request)
