"""
事件总线 — asyncio.Queue 实现

Phase 1-2: 进程内 asyncio.Queue（零运维）
Phase 3: 可迁移到 Redis Pub/Sub

事件类型：
- data.pump_snapshot    — 内盘快照更新
- data.hot_coin_update  — 热币扫描更新
- data.kol_signal       — KOL 信号更新
- data.custom_source    — 自定义数据更新
- strategy.triggered    — 策略触发
- alert.created         — 告警生成

Python 3.9 兼容。
"""
import asyncio
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# 事件回调类型
EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]


class EventBus:
    """
    异步事件总线

    用法：
        bus = EventBus()

        # 订阅事件
        async def on_trigger(event):
            print(f"Strategy triggered: {event}")
        bus.subscribe("strategy.triggered", on_trigger)

        # 发布事件
        await bus.publish("strategy.triggered", {"strategy_id": "xxx"})

        # 启动事件处理循环（在后台 task 中）
        asyncio.create_task(bus.start())
    """

    def __init__(self, max_queue_size: int = 10000):
        self._queue = asyncio.Queue(maxsize=max_queue_size)  # type: asyncio.Queue
        self._subscribers = {}  # type: Dict[str, List[EventHandler]]
        self._running = False
        self._stats = {
            "published": 0,
            "processed": 0,
            "errors": 0,
        }  # type: Dict[str, int]

    def subscribe(self, event_type: str, handler: EventHandler):
        """订阅事件类型"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
        log.debug(f"Subscribed to '{event_type}': {handler.__name__}")

    def unsubscribe(self, event_type: str, handler: EventHandler):
        """取消订阅"""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    async def publish(self, event_type: str, data: Dict[str, Any]):
        """发布事件（非阻塞）"""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._queue.put_nowait(event)
            self._stats["published"] += 1
        except asyncio.QueueFull:
            log.warning(f"Event queue full, dropping event: {event_type}")

    async def start(self):
        """启动事件处理循环"""
        self._running = True
        log.info("EventBus started")

        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
                await self._dispatch(event)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"EventBus error: {e}")
                self._stats["errors"] += 1

        log.info("EventBus stopped")

    async def stop(self):
        """停止事件处理循环"""
        self._running = False
        # 处理队列中剩余事件
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                await self._dispatch(event)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                log.error(f"EventBus drain error: {e}")

    async def _dispatch(self, event: Dict[str, Any]):
        """分发事件到订阅者"""
        event_type = event.get("type", "")
        handlers = self._subscribers.get(event_type, [])

        if not handlers:
            log.debug(f"No handlers for event: {event_type}")
            return

        for handler in handlers:
            try:
                await handler(event["data"])
                self._stats["processed"] += 1
            except Exception as e:
                log.error(
                    f"Handler {handler.__name__} error for {event_type}: {e}"
                )
                self._stats["errors"] += 1

    @property
    def stats(self) -> Dict[str, int]:
        """返回统计信息"""
        return dict(self._stats)

    @property
    def queue_size(self) -> int:
        """当前队列大小"""
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        return self._running


# 全局单例
_global_bus = None  # type: Optional[EventBus]


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus
