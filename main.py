from __future__ import annotations

import asyncio
import datetime
import signal
import sys
from collections import deque
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn

from metrics.metrics_collector import MetricsCollector
from protocol.protocol_stream_file import ProtocolStreamFile
from stream.stream_adapter import StreamAdapter
from stream.stream_metrics import (
    stream_buffer_fill,
    stream_dropped_packets,
    stream_latency_ms,
    stream_latency_99p,
    stream_total_ingested,
    validation_failures
)
from stream.disk_queue import DiskQueue
from prometheus_client import generate_latest  # Prometheus metrics
from protocol.protocol_stream_mock import MockEEGStreamReader
from stream.execution_orchestrator import ExecutionOrchestrator
from stream.task_queue import TaskQueue
from stream.gate_manager import GateManager
from stream.rollback_handler import RollbackHandler
from stream.execution_state_machine import ExecutionStateMachine
from stream.execution_event_bus import ExecutionEventBus
from stream.violation_handler import ViolationHandler
from stream.stream_adapter import load_stream_config


# ─────────── Global Variables for Shutdown ───────────
adapters = []
execution_orchestrator = None
metrics_collector = None
background_tasks = []

# ─────────── Orchestrator Variables ───────────

execution_orchestrator = ExecutionOrchestrator(
    task_queue=TaskQueue(),
    gate_manager=GateManager(),
    rollback_handler=RollbackHandler(),
    state_machine=ExecutionStateMachine(),
    event_bus=ExecutionEventBus(),
    violation_handler=ViolationHandler(rollback_handler=RollbackHandler())
)

# ─────────── FastAPI App ───────────
app = FastAPI(title="EEG Stream Adapter Service")

# ─────────── Startup Initialization ───────────
@app.on_event("startup")
async def _start_adapter() -> None:
    # ─────────── Adapter Setup ───────────
    global adapters, execution_orchestrator, metrics_collector, background_tasks
    stream_config = load_stream_config()
    token = stream_config['token']

    buffer = deque(maxlen=2048)
    disk_queue = DiskQueue("buffer.db")
    mock_stream = MockEEGStreamReader("ws://localhost:8001/ws?token=" + token)

    adapter = StreamAdapter(
        stream=mock_stream,
        buffer=buffer,
        disk_queue=disk_queue,
        buffer_limit=2048,
        throttle_hz=256,
        execution_orchestrator=execution_orchestrator,
        task_priority=3
    )
    adapters.append(adapter)

    #mock_stream = ProtocolStreamFile("protocol/signal.json")
    mock_stream = MockEEGStreamReader("ws://localhost:8002/ws?token=" + token)
    adapter2 = StreamAdapter(
        stream=mock_stream,
        buffer=buffer,
        disk_queue=disk_queue,
        buffer_limit=2048,
        throttle_hz=256,
        execution_orchestrator=execution_orchestrator,
        task_priority=2
    )
    adapters.append(adapter2)
    metrics_collector = MetricsCollector()
    # Force metric registration (shows up in Prometheus even before increment)
    stream_dropped_packets.inc(0)
    stream_total_ingested.inc(0)
    validation_failures.inc(0)
    stream_latency_99p.set(0)
    stream_buffer_fill.set(0)

    # Create background tasks
    background_tasks.clear()

    # Create the orchestrator task
    orchestrator_task = asyncio.create_task(run_orchestrator_with_shutdown())
    background_tasks.append(orchestrator_task)

    # Create the metrics collector task
    metrics_task = asyncio.create_task(run_metrics_with_shutdown())
    background_tasks.append(metrics_task)

    # Create adapter tasks
    for adapter in adapters:
        adapter_task = asyncio.create_task(run_adapter_with_shutdown(adapter))
        background_tasks.append(adapter_task)

    print("All background tasks started successfully")

@app.on_event("shutdown")
async def _shutdown_adapter() -> None:
    """Handle FastAPI shutdown"""
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

async def run_orchestrator_with_shutdown():
    """Run orchestrator with shutdown awareness"""
    global execution_orchestrator
    if execution_orchestrator is None:
        print("Error: execution_orchestrator not initialized")
        return
    try:
        await execution_orchestrator.run()
    except asyncio.CancelledError:
        print("Orchestrator task cancelled")
        execution_orchestrator.stop()
    except Exception as e:
        print(f"Orchestrator error: {e}")

async def run_metrics_with_shutdown():
    """Run metrics collector with shutdown awareness"""
    global metrics_collector
    if metrics_collector is None:
        print("Error: metrics_collector not initialized")
        return
    try:
        await metrics_collector.collect_metrics()
    except asyncio.CancelledError:
        print("Metrics collector task cancelled")
        metrics_collector.stop()
    except Exception as e:
        print(f"Metrics collector error: {e}")

async def run_adapter_with_shutdown(adapter):
    """Run adapter with shutdown awareness"""
    try:
        await adapter.consume_stream()
    except asyncio.CancelledError:
        print(f"Adapter {adapter.stream_id} task cancelled")
        adapter.stop()
    except Exception as e:
        print(f"Adapter {adapter.stream_id} error: {e}")

# ─────────── Prometheus /metrics Endpoint ───────────
@app.get("/metrics", response_class=PlainTextResponse)
async def _metrics() -> str:
    return generate_latest().decode("utf-8")

# ─────────── Run Uvicorn ───────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
