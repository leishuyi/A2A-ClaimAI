"""降级装饰器：将静默失败转换为可观测的降级状态。

参考 grid-qa 的 degraded() 模式，确保外部依赖故障不阻塞主流程。
"""
from functools import wraps
from typing import Any, Callable, TypeVar, ParamSpec

from loguru import logger

P = ParamSpec("P")
T = TypeVar("T")


def degraded(
    fallback: T,
    tag: str = "",
    message: str = "",
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """将函数调用包裹在 try/except 中，失败时返回 fallback 并记录日志。

    Args:
        fallback: 失败时返回的降级值
        tag: 降级标签，用于监控区分
        message: 降级日志信息

    Usage:
        @degraded(fallback=[], tag="milvus_query", message="向量检索失败")
        def search_vectors(query): ...
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                tag_str = f"[降级:{tag}] " if tag else ""
                logger.warning(f"{tag_str}{message or str(e)}")
                return fallback
        return wrapper
    return decorator
