# from __future__ import annotations
# import asyncio
# from collections import deque
# from fastapi import FastAPI, Request, HTTPException
# from fastapi.responses import PlainTextResponse
# import uvicorn
# from src.stream_adapter import StreamAdapter, ws_packet_stream
# from src.stream_metrics import MetricsHandler
# from src.disk_queue import DiskQueue

# API_KEY = "secretkey"  

# # ───────────────────────── Shared instances ──────────────────────────
# metrics = MetricsHandler()
# buffer = deque(maxlen=2048)  # Supports 2s of 256Hz stream
# disk_queue = DiskQueue("buffer.db")

# # Connecting to the local mock EEG stream
# mock_stream = ws_packet_stream("ws://localhost:8001/ws")

# adapter = StreamAdapter(
#     stream=mock_stream,
#     buffer=buffer,
#     metrics=metrics,
#     disk_queue=disk_queue,
#     buffer_limit=2048,
#     throttle_hz=256,  # Add back-pressure when buffer is too full
# )

# # ─────────────────────────── FastAPI App ─────────────────────────────
# app = FastAPI(title="EEG Stream Adapter Service")

# @app.on_event("startup")
# async def _start_adapter() -> None:
#     asyncio.create_task(adapter.consume_stream())

# @app.get("/metrics", response_class=PlainTextResponse)
# async def _metrics(req: Request) -> str:
#     if req.headers.get("x-api-key") != API_KEY:
#         raise HTTPException(status_code=403, detail="Forbidden")
#     return metrics.prometheus_format()

# # ─────────────────────────── Entry point ─────────────────────────────
# if __name__ == "__main__":  # pragma: no cover
#     uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
from __future__ import annotations

import asyncio
import datetime
import sys
from collections import deque
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
import uvicorn

from src.stream_adapter import StreamAdapter, ws_packet_stream
from src.stream_metrics import MetricsHandler
from src.disk_queue import DiskQueue

API_KEY = "secretkey" 
metrics = MetricsHandler()
buffer = deque(maxlen=2048) 
disk_queue = DiskQueue("buffer.db")

# Connecting to the local mock EEG stream
mock_stream = ws_packet_stream("ws://localhost:8001/ws")

adapter = StreamAdapter(
    stream=mock_stream,
    buffer=buffer,
    metrics=metrics,
    disk_queue=disk_queue,
    buffer_limit=2048,
    throttle_hz=256,  # back-pressure when buffer is too full
)

app = FastAPI(title="EEG Stream Adapter Service")

async def report_metrics(interval: int = 5) -> None:
    """Print latency, buffer %, and dropped-packet count every N seconds."""
    while True:
        now = datetime.datetime.now().strftime("%H:%M:%S")
        snap = metrics.prometheus_format().splitlines()
        latency = next(line for line in snap if line.startswith("stream_latency_99p"))
        buf_fill = next(line for line in snap if line.startswith("stream_buffer_fill_percent"))
        drops = next(line for line in snap if line.startswith("stream_dropped_packets"))
        print(f"[{now}] {latency} | {buf_fill} | {drops}", file=sys.stdout)
        await asyncio.sleep(interval)

@app.on_event("startup")
async def _start_adapter() -> None:
    asyncio.create_task(adapter.consume_stream())
    asyncio.create_task(report_metrics())  # ← new: CLI stream

@app.get("/metrics", response_class=PlainTextResponse)
async def _metrics(req: Request) -> str:
    if req.headers.get("x-api-key") != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return metrics.prometheus_format()
if __name__ == "__main__":  # pragma: no cover
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)
