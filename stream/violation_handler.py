import logging
from typing import Any
from stream.task_queue import Task
from stream.rollback_handler import RollbackHandler


class ViolationHandler:
    """Manages rollback on failures and violations"""

    def __init__(self, rollback_handler: RollbackHandler):
        self.rollback_handler = rollback_handler
        self.logger = logging.getLogger(__name__)
        self._violation_count = 0

    async def handle(self, task: Task) -> bool:
        """Handle a task violation by attempting rollback"""
        try:
            self._violation_count += 1
            self.logger.warning(f"Handling violation for task {task.id}")

            # Attempt to restore from snapshot
            success = self.rollback_handler.restore(task)

            if success:
                self.logger.info(f"Successfully rolled back task {task.id}")
            else:
                self.logger.error(f"Failed to rollback task {task.id}")

            # Clean up the snapshot after rollback attempt
            self.rollback_handler.cleanup(task)

            return success

        except Exception as e:
            self.logger.error(f"Error in violation handler for task {task.id}: {e}")
            return False

    def get_violation_count(self) -> int:
        """Get the total number of violations handled"""
        return self._violation_count

    def reset_violation_count(self) -> None:
        """Reset the violation count"""
        self._violation_count = 0
