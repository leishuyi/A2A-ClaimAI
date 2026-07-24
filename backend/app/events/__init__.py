"""轻量事件总线：解耦 Agent 链路的跨模块通知。

参考 grid-qa 的 quality_event_bus 模式，使用 fnmatch 模式匹配订阅。
"""
from fnmatch import fnmatch
from typing import Any, Callable, Awaitable

from loguru import logger

EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """同步事件总线（后续可升级为 Redis pub/sub）"""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler):
        """订阅事件，支持 fnmatch 通配符: 'agent.*' 匹配 'agent.completed'"""
        self._handlers.setdefault(event_type, []).append(handler)
        logger.debug("事件订阅", event_type=event_type, handler=handler.__name__)

    def publish(self, event_type: str, payload: dict[str, Any]):
        """发布事件，通知所有匹配的处理器"""
        for pattern, handlers in self._handlers.items():
            if fnmatch(event_type, pattern):
                for handler in handlers:
                    try:
                        handler(payload)
                    except Exception as e:
                        logger.error("事件处理失败", event_type=event_type, handler=handler.__name__, error=str(e))

    def clear(self):
        """清除所有订阅（测试用）"""
        self._handlers.clear()


event_bus = EventBus()
