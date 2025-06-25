# run_adapter_service.py (entry point to run the adapter, metrics server, and optional CLI)
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from stream_adapter import StreamAdapter
from stream_metrics import MetricsHandler
from disk_queue import DiskQueue
import asyncio
from collections import deque
import uvicorn
API_KEY = "supersecretkey"  # Change this in production
metrics = MetricsHandler()
buffer = deque(maxlen=512)
disk_queue = DiskQueue("buffer.db")
# Initialize app and adapter
app = FastAPI()
mock_stream = None  # Replace with actual stream source in prod
adapter = StreamAdapter(stream=mock_stream, buffer=buffer, metrics=metrics, disk_queue=disk_queue)
@app.on_event("startup")
async def start_adapter():
    if adapter.stream:
        asyncio.create_task(adapter.consume_stream())
@app.get("/metrics", response_class=PlainTextResponse)
async def metrics_endpoint(request: Request):
    api_key = request.headers.get("x-api-key")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")
    return metrics.prometheus_format()
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
