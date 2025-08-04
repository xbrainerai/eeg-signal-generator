import asyncio
import logging
from typing import Dict, List, Callable, Any
from collections import defaultdict


class ExecutionEventBus:
    """Publishes lifecycle events for task execution"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.logger = logging.getLogger(__name__)

    async def publish(self, event_type: str, data: Any = None) -> None:
        """Publish an event to all subscribers"""
        try:
            if event_type in self._subscribers:
                for callback in self._subscribers[event_type]:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(event_type, data)
                        else:
                            callback(event_type, data)
                    except Exception as e:
                        self.logger.error(f"Error in event callback for {event_type}: {e}")

            self.logger.debug(f"Published event: {event_type} with data: {data}")

        except Exception as e:
            self.logger.error(f"Error publishing event {event_type}: {e}")

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """Subscribe to an event type"""
        self._subscribers[event_type].append(callback)
        self.logger.debug(f"Added subscriber for event: {event_type}")

    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """Unsubscribe from an event type"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                self.logger.debug(f"Removed subscriber for event: {event_type}")
                return True
            except ValueError:
                self.logger.warning(f"Callback not found for event: {event_type}")
                return False
        return False

    def get_subscriber_count(self, event_type: str) -> int:
        """Get the number of subscribers for an event type"""
        return len(self._subscribers.get(event_type, []))

    def get_all_event_types(self) -> List[str]:
        """Get all registered event types"""
        return list(self._subscribers.keys())
