#!/usr/bin/env python3
"""Test script for execution orchestrator integration"""

import asyncio
import logging
from stream.stream_adapter import StreamAdapter
from stream.execution_orchestrator import ExecutionOrchestrator
from stream.task_queue import TaskQueue, Task
from stream.gate_manager import GateManager
from stream.rollback_handler import RollbackHandler
from stream.execution_state_machine import ExecutionStateMachine
from stream.execution_event_bus import ExecutionEventBus
from stream.violation_handler import ViolationHandler
from stream.buffer_management_handler import BufferManagementHandler
from collections import deque

# Set up logging
logging.basicConfig(level=logging.INFO)

async def test_buffer_management_task():
    """Test that buffer management tasks work correctly"""
    print("Testing buffer management task...")

    # Create components
    buffer = deque(maxlen=5)
    task_queue = TaskQueue()
    gate_manager = GateManager()
    rollback_handler = RollbackHandler()
    state_machine = ExecutionStateMachine()
    event_bus = ExecutionEventBus()
    violation_handler = ViolationHandler(rollback_handler)

    # Create buffer handler
    buffer_handler = BufferManagementHandler(buffer, 5)

    # Create orchestrator
    orchestrator = ExecutionOrchestrator(
        task_queue=task_queue,
        gate_manager=gate_manager,
        rollback_handler=rollback_handler,
        state_machine=state_machine,
        event_bus=event_bus,
        violation_handler=violation_handler
    )

    # Start orchestrator
    orchestrator_task = asyncio.create_task(orchestrator.run())

    # Wait a moment for orchestrator to start
    await asyncio.sleep(0.1)

    # Create and submit a buffer management task
    test_packet = {"timestamp": 1234567890, "data": "test_packet"}
    buffer_task = Task(
        priority=10,
        deadline_ms=1000,
        context={
            'task_type': 'buffer_management',
            'packet': test_packet
        },
        handler=buffer_handler.handle_buffer_management
    )

    await task_queue.push(buffer_task)
    print(f"Submitted task {buffer_task.id}")

    # Wait for task to complete
    await asyncio.sleep(0.5)

    # Check results
    print(f"Buffer size: {len(buffer)}")
    print(f"Buffer contents: {list(buffer)}")

    # Stop orchestrator
    orchestrator.stop()
    await asyncio.sleep(0.1)

    print("Test completed!")

async def test_stream_adapter_integration():
    """Test the stream adapter with execution orchestrator"""
    print("Testing stream adapter integration...")

    # Create stream adapter
    adapter = StreamAdapter(buffer_limit=5)

    # Start the orchestrator by calling consume_stream
    # We'll simulate this by starting the orchestrator manually
    if adapter._orchestrator_task is None:
        adapter._orchestrator_task = asyncio.create_task(adapter.orchestrator.run())

    await asyncio.sleep(0.1)

    # Create a test packet
    test_packet = {"timestamp": 1234567890, "data": "test_packet"}
    test_metric = None  # We'll create this in the actual implementation

    # Test the buffer management
    await adapter._process_packet(test_packet, test_metric, 1234567890.0)

    await asyncio.sleep(0.5)

    print(f"Buffer size: {len(adapter.buffer)}")
    print(f"Buffer contents: {list(adapter.buffer)}")

    # Stop orchestrator
    adapter.orchestrator.stop()
    await asyncio.sleep(0.1)

    print("Stream adapter integration test completed!")

async def main():
    """Run all tests"""
    print("Starting execution orchestrator tests...")

    await test_buffer_management_task()
    print("\n" + "="*50 + "\n")
    await test_stream_adapter_integration()

    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
