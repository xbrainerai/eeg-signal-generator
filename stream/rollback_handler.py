import copy
import logging
from typing import Dict, Any, Optional
from stream.task_queue import Task


class RollbackHandler:
    """Manages state snapshots for rollback functionality"""

    def __init__(self):
        self._snapshots: Dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

    def snapshot(self, task: Task) -> None:
        """Create a snapshot of the current state for a task"""
        try:
            # Create a deep copy of the task context for rollback
            if task.context:
                self._snapshots[task.id] = copy.deepcopy(task.context)
                self.logger.debug(f"Created snapshot for task {task.id}")
            else:
                self._snapshots[task.id] = None
        except Exception as e:
            self.logger.error(f"Failed to create snapshot for task {task.id}: {e}")

    def restore(self, task: Task) -> bool:
        """Restore the state from a snapshot"""
        try:
            if task.id in self._snapshots:
                snapshot = self._snapshots[task.id]
                if snapshot is not None:
                    # Restore the context from snapshot
                    task.context = copy.deepcopy(snapshot)
                self.logger.debug(f"Restored snapshot for task {task.id}")
                return True
            else:
                self.logger.warning(f"No snapshot found for task {task.id}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to restore snapshot for task {task.id}: {e}")
            return False

    def cleanup(self, task: Task) -> None:
        """Clean up the snapshot for a task"""
        if task.id in self._snapshots:
            del self._snapshots[task.id]
            self.logger.debug(f"Cleaned up snapshot for task {task.id}")

    def get_snapshot_count(self) -> int:
        """Get the number of active snapshots"""
        return len(self._snapshots)
