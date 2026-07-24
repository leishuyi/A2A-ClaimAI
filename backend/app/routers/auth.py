"""JWT 认证路由 — 登录/验证/刷新

生产环境替换 API Key 的方案。
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings

router = APIRouter()

# JWT 配置（生产环境应通过环境变量注入）
SECRET_KEY = settings.api_key or "starshield-dev-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

# 模拟用户库（生产应对接 LDAP/OAuth）
MOCK_USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "管理员"},
    "liwei": {"password": "liwei123", "role": "claims_adjuster", "name": "李薇"},
    "wangli": {"password": "wangli123", "role": "claims_adjuster", "name": "王丽"},
}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str = ""
    role: str = ""


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> dict:
    """验证 token，返回 payload。验证失败抛 HTTPException"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI 依赖注入 — 从请求头获取当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供认证 Token")
    token = authorization.split(" ", 1)[1]
    return verify_token(token)


@router.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """用户登录，返回 JWT Token"""
    user = MOCK_USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token({"sub": req.username, "role": user["role"], "name": user["name"]})
    return TokenResponse(access_token=token, user_name=user["name"], role=user["role"])


@router.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return {"username": current_user.get("sub"), "role": current_user.get("role"), "name": current_user.get("name")}
