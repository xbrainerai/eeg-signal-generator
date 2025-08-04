from typing import Dict, Any
from stream.task_queue import Task


class GateManager:
    """Manages execution gates to control task execution"""

    def __init__(self):
        self._gates: Dict[str, bool] = {
            'default': True,  # Default gate is always open
            'buffer_management': True,
            'disk_operations': True,
            'metrics_collection': True
        }

    def set_gate(self, gate_name: str, is_open: bool) -> None:
        """Set the state of a specific gate"""
        self._gates[gate_name] = is_open

    def get_gate(self, gate_name: str) -> bool:
        """Get the current state of a gate"""
        return self._gates.get(gate_name, True)

    def allow(self, task: Task) -> bool:
        """Check if a task is allowed to execute based on gates"""
        # For buffer management tasks, check the buffer_management gate
        if hasattr(task.context, 'task_type'):
            gate_name = task.context.get('task_type', 'default')
            return self.get_gate(gate_name)

        # Default to allowing execution
        return True

    def close_all_gates(self) -> None:
        """Close all gates except default"""
        for gate_name in self._gates:
            if gate_name != 'default':
                self._gates[gate_name] = False

    def open_all_gates(self) -> None:
        """Open all gates"""
        for gate_name in self._gates:
            self._gates[gate_name] = True
