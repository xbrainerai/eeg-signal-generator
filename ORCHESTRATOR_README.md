# Execution Orchestrator

This document describes the implementation of the `ExecutionOrchestrator` class that drives the real-time task pipeline with priority-based execution, deadline management, and rollback capabilities.

## Overview

The `ExecutionOrchestrator` is a comprehensive task execution system that provides:

- **Priority-based task scheduling** with 4 priority levels (LOW, NORMAL, HIGH, CRITICAL)
- **Deadline management** with automatic timeout handling
- **Execution gating** via `GateManager` for controlled task execution
- **State management** with `ExecutionStateMachine` for tracking task states
- **Rollback capabilities** with `RollbackHandler` for state snapshots
- **Event-driven architecture** with `ExecutionEventBus` for task events
- **Violation handling** with automatic rollback on failures
- **Prometheus metrics** for monitoring queue depth, execution latency, and failures
- **Structured logging** with precise timestamps and event IDs

## Architecture Components

### 1. TaskQueue
- Priority queue implementation using heapq
- Automatic deadline checking and expired task removal
- Thread-safe operations with asyncio.Lock
- Prometheus metrics for queue depth by priority

### 2. GateManager
- Controls task execution through configurable gates
- Supports individual gate checks and multi-gate validation
- Thread-safe gate state management

### 3. RollbackHandler
- Creates state snapshots before task execution
- Manages snapshot lifecycle (create, retrieve, clear)
- Supports custom rollback implementations

### 4. ExecutionStateMachine
- Manages task state transitions (READY → RUNNING → COMPLETE/FAILED/ROLLED_BACK)
- Validates state transitions to prevent invalid states
- Thread-safe state management

### 5. ExecutionEventBus
- Publish/subscribe event system for task events
- Supports multiple event types (task_completed, task_failed, etc.)
- Asynchronous event handling with error isolation

### 6. ViolationHandler
- Handles task violations (timeouts, exceptions, gate violations)
- Automatically triggers rollback operations
- Publishes failure events with detailed error information

## Usage

### Basic Task Submission

```python
from src.execution_orchestrator import (
    ExecutionOrchestrator,
    TaskPriority,
    TaskContext
)
from datetime import datetime, timedelta

# Create orchestrator
orchestrator = ExecutionOrchestrator()

# Start the orchestrator
asyncio.create_task(orchestrator.run())

# Submit a task
async def my_task(context: TaskContext):
    # Your task logic here
    await asyncio.sleep(0.1)
    return {"result": "success"}

task_id = await orchestrator.submit_task(
    handler=my_task,
    priority=TaskPriority.HIGH,
    deadline=datetime.utcnow() + timedelta(seconds=30),
    context=TaskContext(user_id="user123", session_id="session456")
)
```

### Task with Gates

```python
# Set up gates
await orchestrator.gate_manager.set_gate("signal_processing", True)
await orchestrator.gate_manager.set_gate("validation", False)

# Submit task that requires specific gates
task_id = await orchestrator.submit_task(
    handler=process_signal,
    priority=TaskPriority.NORMAL,
    required_gates=["signal_processing", "validation"],  # Will fail due to disabled validation gate
    context=TaskContext(user_id="user123")
)
```

### Event Handling

```python
# Subscribe to events
async def on_task_completed(data):
    print(f"Task {data['task_id']} completed in {data['execution_time']:.3f}s")

async def on_task_failed(data):
    print(f"Task {data['task_id']} failed: {data['error']}")

await orchestrator.event_bus.subscribe("task_completed", on_task_completed)
await orchestrator.event_bus.subscribe("task_failed", on_task_failed)
```

### Synchronous Tasks

```python
def cpu_intensive_task(context: TaskContext):
    # This will run in a thread pool
    import time
    time.sleep(0.5)
    return {"status": "completed"}

task_id = await orchestrator.submit_task(
    handler=cpu_intensive_task,
    priority=TaskPriority.LOW,
    context=TaskContext(user_id="user123")
)
```

## Integration with Existing Codebase

The orchestrator has been integrated into the main application:

### Main Application Integration

```python
# In main.py
from src.execution_orchestrator import ExecutionOrchestrator

# Create orchestrator
orchestrator = ExecutionOrchestrator()

# Start orchestrator in FastAPI startup
@app.on_event("startup")
async def _start_adapter() -> None:
    # Start the execution orchestrator
    asyncio.create_task(orchestrator.run())
    # ... other startup tasks
```

### REST API Endpoints

The orchestrator exposes REST endpoints for task submission and monitoring:

- `GET /orchestrator/stats` - Get queue statistics
- `POST /orchestrator/submit` - Submit a new task

Example API usage:
```bash
# Submit a task
curl -X POST "http://localhost:8080/orchestrator/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "signal_processing",
    "priority": "HIGH",
    "deadline_seconds": 30,
    "user_id": "user123"
  }'

# Get statistics
curl "http://localhost:8080/orchestrator/stats"
```

## Prometheus Metrics

The orchestrator exposes the following Prometheus metrics:

- `task_execution_latency_seconds` - Histogram of task execution times
- `task_failures_total` - Counter of task failures by type and reason
- `task_queue_depth` - Gauge of queue depth by priority
- `execution_jitter_seconds` - Histogram of execution timing jitter
- `rollback_operations_total` - Counter of rollback operations

## Monitoring and Observability

### Structured Logging

The orchestrator provides detailed logging with:
- Precise timestamps for all operations
- Task IDs for correlation
- Execution durations
- State transitions
- Error details

### Event Correlation

Each task has a unique ID that correlates across:
- Task submission
- State transitions
- Event publications
- Metrics collection
- Log entries

### Health Checks

The orchestrator provides health check information:
- Queue depth and status
- Running state
- Task completion rates
- Failure rates

## Testing

Run the test suite to verify functionality:

```bash
# Run all orchestrator tests
pytest test/test_orchestrator.py -v

# Run example
python src/orchestrator_example.py
```

## Configuration

### Priority Levels

- `LOW` - Background tasks, non-critical operations
- `NORMAL` - Standard processing tasks
- `HIGH` - Important tasks with time sensitivity
- `CRITICAL` - System-critical tasks that must complete

### Default Settings

- Default deadline: 30 seconds
- Default priority: NORMAL
- Default gates: All enabled
- Task timeout: Based on deadline

## Error Handling

### Violation Types

1. **Timeout Violations** - Task exceeds its deadline
2. **Exception Violations** - Task raises an unhandled exception
3. **Gate Violations** - Required gates are disabled

### Rollback Behavior

When a violation occurs:
1. Task state transitions to FAILED
2. RollbackHandler attempts to restore from snapshot
3. Task state transitions to ROLLED_BACK if successful
4. Failure event is published with detailed information
5. Prometheus metrics are updated

## Performance Considerations

### High-Resolution Timers

The orchestrator uses high-resolution timers for:
- Deadline checking with microsecond precision
- Execution time measurement
- Jitter calculation
- Latency histograms

### Memory Management

- Task objects are cleaned up after completion
- Snapshots are cleared on successful completion
- State machine entries are maintained for audit purposes

### Scalability

- Asynchronous design supports high concurrency
- Thread pool for synchronous tasks
- Efficient priority queue implementation
- Minimal blocking operations

## Future Enhancements

Potential improvements:
- Persistent task queue with database backing
- Distributed orchestrator with leader election
- Advanced scheduling algorithms
- Task dependencies and workflows
- Real-time task monitoring dashboard
- Advanced rollback strategies
- Task result caching
- Dynamic priority adjustment based on system load
