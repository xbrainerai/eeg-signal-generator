import logging
from enum import Enum
from typing import Dict, List
from stream.task_queue import Task


class TaskState(Enum):
    """Enumeration of possible task states"""
    READY = "ready"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStateMachine:
    """Manages task state transitions"""

    def __init__(self):
        self._task_states: Dict[str, TaskState] = {}
        self._state_history: Dict[str, List[TaskState]] = {}
        self.logger = logging.getLogger(__name__)

        # Define valid state transitions
        self._valid_transitions = {
            TaskState.READY: [TaskState.RUNNING, TaskState.CANCELLED],
            TaskState.RUNNING: [TaskState.COMPLETE, TaskState.FAILED, TaskState.CANCELLED],
            TaskState.COMPLETE: [],  # Terminal state
            TaskState.FAILED: [],    # Terminal state
            TaskState.CANCELLED: []  # Terminal state
        }

    def update(self, task: Task, new_state: str) -> bool:
        """Update the state of a task"""
        try:
            new_state_enum = TaskState(new_state)
            current_state = self._task_states.get(task.id, TaskState.READY)

            # Check if transition is valid
            if new_state_enum not in self._valid_transitions.get(current_state, []):
                self.logger.warning(
                    f"Invalid state transition from {current_state.value} to {new_state} for task {task.id}"
                )
                return False

            # Update state
            self._task_states[task.id] = new_state_enum

            # Track state history
            if task.id not in self._state_history:
                self._state_history[task.id] = []
            self._state_history[task.id].append(new_state_enum)

            self.logger.debug(f"Task {task.id} state: {current_state.value} -> {new_state}")
            return True

        except ValueError as e:
            self.logger.error(f"Invalid state '{new_state}' for task {task.id}: {e}")
            return False

    def get_state(self, task_id: str) -> TaskState:
        """Get the current state of a task"""
        return self._task_states.get(task_id, TaskState.READY)

    def get_state_history(self, task_id: str) -> List[TaskState]:
        """Get the state history of a task"""
        return self._state_history.get(task_id, [])

    def cleanup(self, task_id: str) -> None:
        """Clean up state tracking for a task"""
        if task_id in self._task_states:
            del self._task_states[task_id]
        if task_id in self._state_history:
            del self._state_history[task_id]
        self.logger.debug(f"Cleaned up state tracking for task {task_id}")

    def get_active_tasks(self) -> Dict[str, TaskState]:
        """Get all active tasks and their states"""
        return self._task_states.copy()
