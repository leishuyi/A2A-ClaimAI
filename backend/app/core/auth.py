"""认证中间件 — JWT + API Key 双模式

开发环境（feature_rbac=False）跳过鉴权，
生产环境（feature_rbac=True）支持两种认证方式：
  - Authorization: Bearer <JWT>  — 前端用户登录后
  - X-API-Key: <key>             — 外部服务调用
"""
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import settings

# 无需鉴权的路径
PUBLIC_PATHS = {
    "/api/v1/health", "/docs", "/openapi.json", "/redoc",
    "/api/v1/auth/login",  # 登录接口公开
}


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT + API Key 双模式认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 开发环境 or 公开路径 → 跳过
        if not settings.feature_rbac or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        api_key = request.headers.get("X-API-Key", "")

        # 方式1: JWT Bearer Token
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                jwt.decode(token, settings.api_key or "starshield-dev-secret-key",
                          algorithms=["HS256"])
                return await call_next(request)
            except JWTError:
                return JSONResponse(
                    status_code=401,
                    content={"code": 30002, "message": "JWT Token 无效或已过期"},
                )

        # 方式2: API Key
        if api_key and api_key == settings.api_key:
            return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={"code": 30002, "message": "未授权访问，请提供有效的 Token 或 API Key"},
        )
