"""事件总线 — subscribe / publish，线程安全"""

from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

# 事件类型常量
TEMPLATE_LOADED = "template.loaded"
DATA_COLLECTED = "data.collected"
ANALYSIS_DONE = "analysis.done"
REPORT_GENERATED = "report.generated"
PACK_DONE = "pack.done"

ALL_EVENTS = [TEMPLATE_LOADED, DATA_COLLECTED, ANALYSIS_DONE, REPORT_GENERATED, PACK_DONE]


class EventBus:
    """事件总线，支持异步订阅与发布。

    内部使用 dict + threading.Lock 保证线程安全。
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, handler: Callable) -> None:
        """订阅指定事件类型。

        Args:
            event_type: 事件类型，如 "analysis.done"
            handler: 回调函数，接收 event_data 作为参数
        """
        with self._lock:
            self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable) -> None:
        """取消订阅"""
        with self._lock:
            if event_type in self._handlers:
                self._handlers[event_type] = [h for h in self._handlers[event_type] if h is not handler]
                if not self._handlers[event_type]:
                    del self._handlers[event_type]

    def publish(self, event_type: str, data: Any = None) -> None:
        """发布事件，同步调用所有已注册的 handler。

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    asyncio.get_event_loop().run_until_complete(handler(data))
                else:
                    handler(data)
            except Exception:
                pass  # 单个 handler 出错不影响其他 handler

    def publish_async(self, event_type: str, data: Any = None) -> None:
        """异步发布事件（非阻塞）"""
        loop = asyncio.new_event_loop()
        try:
            tasks = []
            with self._lock:
                handlers = list(self._handlers.get(event_type, []))

            for handler in handlers:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(loop.create_task(handler(data)))
            if tasks:
                loop.run_until_complete(asyncio.gather(*tasks))
        finally:
            loop.close()

    def registered_events(self) -> list[str]:
        """返回已订阅的事件类型列表"""
        with self._lock:
            return list(self._handlers.keys())
