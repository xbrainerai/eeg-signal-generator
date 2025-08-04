#!/usr/bin/env python3
"""
Test script to verify signal handling works correctly.
This simulates the main components of the EEG signal generator.
"""

import asyncio
import signal
import sys
import time

# Global shutdown event
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\nReceived signal {signum}. Shutting down gracefully...")
    shutdown_event.set()

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

class MockStreamAdapter:
    def __init__(self, stream_id):
        self.stream_id = stream_id
        self._running = True
    
    def stop(self):
        """Stop the stream adapter"""
        self._running = False
        print(f"Adapter {self.stream_id} stopped")
    
    async def consume_stream(self):
        """Simulate stream consumption"""
        packet_count = 0
        while self._running:
            try:
                packet_count += 1
                print(f"Adapter {self.stream_id}: Processing packet {packet_count}")
                await asyncio.sleep(0.1)  # Simulate processing time
            except asyncio.CancelledError:
                print(f"Adapter {self.stream_id} cancelled")
                break
        print(f"Adapter {self.stream_id}: Processed {packet_count} packets")

class MockMetricsCollector:
    def __init__(self):
        self._running = True
    
    def stop(self):
        """Stop the metrics collector"""
        self._running = False
        print("Metrics collector stopped")
    
    async def collect_metrics(self):
        """Simulate metrics collection"""
        metric_count = 0
        while self._running:
            try:
                metric_count += 1
                print(f"Collecting metric {metric_count}")
                await asyncio.sleep(0.2)  # Simulate collection time
            except asyncio.CancelledError:
                print("Metrics collector cancelled")
                break
        print(f"Collected {metric_count} metrics")

class MockExecutionOrchestrator:
    def __init__(self):
        self._running = True
    
    def stop(self):
        """Stop the orchestrator"""
        self._running = False
        print("Execution orchestrator stopped")
    
    async def run(self):
        """Simulate orchestrator execution"""
        task_count = 0
        while self._running:
            try:
                task_count += 1
                print(f"Executing task {task_count}")
                await asyncio.sleep(0.15)  # Simulate task execution time
            except asyncio.CancelledError:
                print("Execution orchestrator cancelled")
                break
        print(f"Executed {task_count} tasks")

async def run_component_with_shutdown(component, name):
    """Run a component with shutdown awareness"""
    try:
        if hasattr(component, 'consume_stream'):
            await component.consume_stream()
        elif hasattr(component, 'collect_metrics'):
            await component.collect_metrics()
        elif hasattr(component, 'run'):
            await component.run()
    except asyncio.CancelledError:
        print(f"{name} task cancelled")
        component.stop()
    except Exception as e:
        print(f"{name} error: {e}")

async def main():
    """Main function to test signal handling"""
    print("Starting EEG Signal Generator Test...")
    print("Press Ctrl+C to test graceful shutdown")
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Create mock components
    adapters = [MockStreamAdapter(i) for i in range(1, 3)]
    metrics_collector = MockMetricsCollector()
    execution_orchestrator = MockExecutionOrchestrator()
    
    # Create tasks
    tasks = []
    
    # Create orchestrator task
    orchestrator_task = asyncio.create_task(run_component_with_shutdown(execution_orchestrator, "Orchestrator"))
    tasks.append(orchestrator_task)
    
    # Create metrics collector task
    metrics_task = asyncio.create_task(run_component_with_shutdown(metrics_collector, "Metrics"))
    tasks.append(metrics_task)
    
    # Create adapter tasks
    for i, adapter in enumerate(adapters):
        adapter_task = asyncio.create_task(run_component_with_shutdown(adapter, f"Adapter {adapter.stream_id}"))
        tasks.append(adapter_task)
    
    # Wait for shutdown signal
    await shutdown_event.wait()
    
    # Cancel all tasks gracefully
    print("\nCancelling all tasks...")
    for task in tasks:
        task.cancel()
    
    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    print("All tasks cancelled successfully.")
    print("Test completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received, but should have been handled by signal handler")
    except Exception as e:
        print(f"Unexpected error: {e}") 