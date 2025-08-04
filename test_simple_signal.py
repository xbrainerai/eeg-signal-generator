#!/usr/bin/env python3
"""
Simple test script to verify signal handling works correctly.
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
    # Schedule the shutdown in the event loop
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.call_soon_threadsafe(shutdown_event.set)

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

class MockComponent:
    def __init__(self, name):
        self.name = name
        self._running = True

    def stop(self):
        """Stop the component"""
        self._running = False
        print(f"{self.name} stopped")

    async def run(self):
        """Simulate component execution"""
        count = 0
        while self._running:
            try:
                count += 1
                print(f"{self.name}: Processing item {count}")
                await asyncio.sleep(0.5)  # Simulate work
            except asyncio.CancelledError:
                print(f"{self.name} cancelled")
                break
        print(f"{self.name}: Processed {count} items")

async def run_component_with_shutdown(component):
    """Run a component with shutdown awareness"""
    try:
        await component.run()
    except asyncio.CancelledError:
        print(f"{component.name} task cancelled")
        component.stop()
    except Exception as e:
        print(f"{component.name} error: {e}")

async def monitor_shutdown(tasks):
    """Monitor for shutdown signal and cancel all tasks"""
    await shutdown_event.wait()
    print("Shutdown signal received, cancelling all tasks...")

    # Cancel all tasks gracefully
    for task in tasks:
        task.cancel()

    # Wait for all tasks to complete
    await asyncio.gather(*tasks, return_exceptions=True)
    print("All tasks cancelled successfully.")

async def main():
    """Main function to test signal handling"""
    print("Starting Simple Signal Test...")
    print("Press Ctrl+C to test graceful shutdown")

    # Setup signal handlers
    setup_signal_handlers()

    # Create mock components
    components = [
        MockComponent("Component A"),
        MockComponent("Component B"),
        MockComponent("Component C")
    ]

    # Create tasks
    tasks = []
    for component in components:
        task = asyncio.create_task(run_component_with_shutdown(component))
        tasks.append(task)

    # Start monitoring for shutdown
    monitor_task = asyncio.create_task(monitor_shutdown(tasks))

    # Wait for shutdown
    await shutdown_event.wait()

    # Wait for monitor task to complete
    await monitor_task

    print("Test completed successfully!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received, but should have been handled by signal handler")
    except Exception as e:
        print(f"Unexpected error: {e}")
