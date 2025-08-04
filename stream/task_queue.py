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
        self._queue = asyncio.PriorityQueue()
        self._lock = asyncio.Lock()
        self.size = 0

    async def push(self, task: Task) -> None:
        """Add a task to the queue"""
        #heapq.heappush(self._queue, task)
        await self._queue.put(task)
        self.size += 1


    async def pop_next(self) -> Optional[Task]:
        """Get the next highest priority task"""
        if not self._queue:
            return None
        retVal = await self._queue.get()
        self.size += 1

        return retVal

    def depth(self) -> int:
        """Get the current queue depth"""
        return self.size
