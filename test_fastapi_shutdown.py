#!/usr/bin/env python3
"""
Simple FastAPI test to verify shutdown handling works correctly.
"""

import asyncio
import time
from fastapi import FastAPI
import uvicorn

# Global variables
background_tasks = []

app = FastAPI(title="Test App")

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
                await asyncio.sleep(1)  # Simulate work
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

@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    global background_tasks

    print("Starting background tasks...")

    # Create mock components
    components = [
        MockComponent("Component A"),
        MockComponent("Component B"),
        MockComponent("Component C")
    ]

    # Create background tasks
    background_tasks.clear()
    for component in components:
        task = asyncio.create_task(run_component_with_shutdown(component))
        background_tasks.append(task)

    print("All background tasks started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    global background_tasks

    print("FastAPI shutdown event triggered")
    print("Cancelling all background tasks...")

    # Cancel all background tasks
    for task in background_tasks:
        if not task.done():
            task.cancel()

    # Wait for tasks to complete
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
        print("All background tasks cancelled successfully.")

@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Test app running"}

@app.get("/status")
async def status():
    """Status endpoint"""
    return {
        "message": "App is running",
        "background_tasks": len(background_tasks),
        "tasks_done": sum(1 for task in background_tasks if task.done())
    }

if __name__ == "__main__":
    print("Starting FastAPI test app...")
    print("Press Ctrl+C to test graceful shutdown")
    uvicorn.run("test_fastapi_shutdown:app", host="0.0.0.0", port=8000, reload=False)
