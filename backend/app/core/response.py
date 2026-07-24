from typing import Any, Optional
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """统一 API 响应格式。HTTP 状态码始终 200，业务状态码在 body 中。"""
    code: int = 0
    message: str = "ok"
    data: Optional[Any] = None


class BizError(Exception):
    """业务异常：HTTP 200 + 业务错误码"""
    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.message = message
        self.data = data


# 业务错误码定义
class ErrCode:
    # 通用 (0xxxx)
    SUCCESS = 0
    UNKNOWN = 10000
    VALIDATION = 10001

    # 案件 (4xxxx)
    CASE_NOT_FOUND = 40401
    CASE_INVALID_STATUS = 40402
    CASE_DUPLICATE = 40403

    # 权限 (3xxxx)
    PERMISSION_DENIED = 30001
    UNAUTHORIZED = 30002
