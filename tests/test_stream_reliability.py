import asyncio
from collections import deque

import pytest
from httpx import AsyncClient

from stream.stream_adapter import StreamAdapter
from src.stream_metrics import MetricsHandler

from stream.disk_queue import DiskQueue
from main import app  # FastAPI app with /metrics
from unittest.mock import Mock

class MockStream:
    """Async iterator emitting 200 packets with burst & silence patterns."""
    def __init__(self, burst: bool = True) -> None:
        self.burst = burst
        self.counter = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.counter >= 200:
            raise StopAsyncIteration
        if self.burst and self.counter % 10 == 0:
            await asyncio.sleep(0.01)
        elif not self.burst and self.counter % 10 == 0:
            await asyncio.sleep(0.20)
        self.counter += 1
        return {
            "timestamp": asyncio.get_event_loop().time(),
            "data": [0.1, 0.2],
            "channel_count": 2,
        }

@pytest.mark.asyncio
async def test_burst_and_silence_handling():
    buffer = deque(maxlen=512)
    metrics = MetricsHandler()
    stream = MockStream(burst=True)
    adapter = StreamAdapter(stream=stream, buffer=buffer, metrics=metrics)
    await adapter.consume_stream()
    assert metrics.buffer_fill_pct > 0
    assert metrics.latency_list, "Latency list should not be empty"

@pytest.mark.asyncio
async def test_disk_queue_roundtrip(tmp_path):
    db = tmp_path / "buf.db"
    dq = DiskQueue(str(db))
    dq.push(123.4, '{"foo": "bar"}')
    out = dq.pop(limit=1)
    assert out == ['{"foo": "bar"}']
    assert dq.size() == 0

@pytest.mark.asyncio
async def test_metrics_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        res = await ac.get("/metrics", headers={"x-api-key": "supersecretkey"})
        assert res.status_code == 200
        assert "stream_latency_99p" in res.text
