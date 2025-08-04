import asyncio
import heapq
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime, timedelta


@dataclass
class Task:
    """Represents a task to be executed by the orchestrator"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 0  # Higher number = higher priority
    deadline_ms: int = 1000  # Deadline in milliseconds
    context: Any = None
    handler: Callable = None
    retry_delay: float = 0.1  # Delay before retry if gate is closed
    created_at: datetime = field(default_factory=datetime.now)

    def __lt__(self, other):
        # Priority first, then deadline (earlier deadline = higher priority)
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.deadline_ms < other.deadline_ms


class TaskQueue:
    """Manages tasks with priority and deadline ordering"""

    def __init__(self):
        self._queue = []
        self._lock = asyncio.Lock()

    async def push(self, task: Task) -> None:
        """Add a task to the queue"""
        async with self._lock:
            heapq.heappush(self._queue, task)

    async def pop_next(self) -> Optional[Task]:
        """Get the next highest priority task"""
        async with self._lock:
            if not self._queue:
                return None
            return heapq.heappop(self._queue)

    def depth(self) -> int:
        """Get the current queue depth"""
        return len(self._queue)
