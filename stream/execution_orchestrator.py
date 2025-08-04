# stream/execution_orchestrator.py
import asyncio
import logging
import time
from prometheus_client import Gauge, Histogram, Counter

from stream.task_queue import TaskQueue, Task
from stream.gate_manager import GateManager
from stream.rollback_handler import RollbackHandler
from stream.execution_state_machine import ExecutionStateMachine
from stream.execution_event_bus import ExecutionEventBus
from stream.violation_handler import ViolationHandler

# Metrics
queue_depth = Gauge('task_queue_depth', 'Number of tasks waiting')
exec_latency = Histogram('task_execution_latency_ms', 'Handler execution latency', buckets=[1, 5, 10, 50, 100])
failure_count = Counter('task_failure_total', 'Total tasks failed')


class ExecutionOrchestrator:
    def __init__(self, task_queue: TaskQueue, gate_manager: GateManager,
                 rollback_handler: RollbackHandler, state_machine: ExecutionStateMachine,
                 event_bus: ExecutionEventBus, violation_handler: ViolationHandler):
        self.task_queue = task_queue
        self.gate_manager = gate_manager
        self.rollback_handler = rollback_handler
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.violation_handler = violation_handler
        self.logger = logging.getLogger('stream_adapter')
        self._running = False

    async def run(self):
        """Main orchestrator loop"""
        self._running = True
        self.logger.info("Starting ExecutionOrchestrator")

        while self._running:
            logger = self.logger
            try:
                # Update queue depth metric
                queue_depth.set(self.task_queue.depth())

                # Get next task
                task = await self.task_queue.pop_next()

                if task is None:
                    # No tasks available, yield control and continue
                    await asyncio.sleep(0.001)  # Small delay to prevent busy waiting
                    continue

                logger = task.get_logger()

                # Check if task is allowed to execute
                if not self.gate_manager.allow(task):
                    logger.info(f"Task {task.id} blocked by gate, retrying in {task.retry_delay}s")
                    await asyncio.sleep(task.retry_delay)
                    # Re-queue the task
                    await self.task_queue.push(task)
                    continue

                # Create snapshot before execution
                self.rollback_handler.snapshot(task)

                # Update state to running
                self.state_machine.update(task, 'running')

                # Execute task with timeout
                start = time.perf_counter()
                try:
                    await asyncio.wait_for(task.handler(task.context), timeout=task.deadline_ms / 1000.0)
                    duration = (time.perf_counter() - start) * 1000
                    exec_latency.observe(duration)

                    # Update state to complete
                    self.state_machine.update(task, 'complete')
                    await self.event_bus.publish('task_completed', task.id)

                    logger.info(f"Task {task.id} completed successfully in {duration:.2f}ms")

                except asyncio.TimeoutError:
                    duration = (time.perf_counter() - start) * 1000
                    exec_latency.observe(duration)
                    failure_count.inc()

                    # Update state to failed
                    self.state_machine.update(task, 'failed')
                    await self.event_bus.publish('task_failed', {'id': task.id, 'error': 'Timeout'})

                    # Handle violation
                    await self.violation_handler.handle(task)

                    self.logger.warning(f"Task {task.id} timed out after {duration:.2f}ms")

                except Exception as e:
                    duration = (time.perf_counter() - start) * 1000
                    exec_latency.observe(duration)
                    failure_count.inc()

                    # Update state to failed
                    self.state_machine.update(task, 'failed')
                    await self.event_bus.publish('task_failed', {'id': task.id, 'error': str(e)})

                    # Handle violation
                    await self.violation_handler.handle(task)

                    self.logger.error(f"Task {task.id} failed with error: {e}")

                # Clean up state tracking
                self.state_machine.cleanup(task.id)

                # Yield control to prevent blocking
                await asyncio.sleep(0)

            except Exception as e:
                self.logger.error(f"Error in orchestrator loop: {e}")
                await asyncio.sleep(0.1)  # Brief pause on error

    def stop(self):
        """Stop the orchestrator"""
        self._running = False
        self.logger.info("Stopping ExecutionOrchestrator")
