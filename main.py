from __future__ import annotations

import asyncio
import datetime
import sys
from collections import deque
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
import uvicorn

from metrics.metrics_collector import MetricsCollector
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
    adapters = []
    buffer = deque(maxlen=2048)
    disk_queue = DiskQueue("buffer.db")
    mock_stream = MockEEGStreamReader("ws://localhost:8001/ws")

    adapter = StreamAdapter(
        stream=mock_stream,
        buffer=buffer,
        disk_queue=disk_queue,
        buffer_limit=2048,
        throttle_hz=256,
    )
    adapters.append(adapter)

    mock_stream = MockEEGStreamReader("ws://localhost:8002/ws")

    adapter2 = StreamAdapter(
        stream=mock_stream,
        buffer=buffer,
        disk_queue=disk_queue,
        buffer_limit=2048,
        throttle_hz=256,
    )
    adapters.append(adapter2)
    metrics_collector = MetricsCollector()
    # Force metric registration (shows up in Prometheus even before increment)
    stream_dropped_packets.inc(0)
    stream_total_ingested.inc(0)
    validation_failures.inc(0)
    stream_latency_99p.set(0)
    stream_buffer_fill.set(0)

    #asyncio.create_task(execution_orchestrator.run())
    for adapter in adapters:
        asyncio.create_task(adapter.consume_stream())
    asyncio.create_task(metrics_collector.collect_metrics())
    # TODO spin off thread for the metrics collector
    #asyncio.create_task(report_metrics())

# ─────────── Prometheus /metrics Endpoint ───────────
@app.get("/metrics", response_class=PlainTextResponse)
async def _metrics() -> str:
    return generate_latest().decode("utf-8")

# ─────────── Run Uvicorn ───────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
