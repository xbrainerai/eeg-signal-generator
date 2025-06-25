import asyncio
import pytest
import tempfile
import os
from collections import deque
from httpx import AsyncClient
from stream_adapter import StreamAdapter
from stream_metrics import MetricsHandler
from disk_queue import DiskQueue
from main import app  # FastAPI app with /metrics endpoint
class MockStream:
    def __init__(self, burst=True):
        self.burst = burst
        self.counter = 0
    async def __aiter__(self):
        while self.counter < 200:
            if self.burst and self.counter % 10 == 0:
                await asyncio.sleep(0.01)
            elif not self.burst and self.counter % 10 == 0:
                await asyncio.sleep(0.2)
            yield {
                "timestamp": asyncio.get_event_loop().time(),
                "data": [0.1, 0.2],
                "channel_count": 2
            }
            self.counter += 1
@pytest.mark.asyncio
async def test_burst_and_silence_handling():
    buffer = deque(maxlen=512)
    metrics = MetricsHandler()
    stream = MockStream(burst=True)
    adapter = StreamAdapter(stream=stream, buffer=buffer, metrics=metrics)
    await adapter.consume_stream()
    assert metrics.buffer_fill_pct > 0
    assert isinstance(metrics.latency_list, list)
@pytest.mark.asyncio
async def test_disk_queue_integration(tmp_path):
    db_path = tmp_path / "test_buffer.db"
    dq = DiskQueue(str(db_path))
    dq.push(1234567890, '{"timestamp": 1234567890, "data": [1,2,3]}')
    result = dq.pop(limit=1)
    assert isinstance(result, list)
    assert len(result) == 1
def test_cli_runner_script_exists():
    assert os.path.exists("adapter_cli.py")
def test_replay_functionality(tmp_path):
    db_path = tmp_path / "test_buffer.db"
    dq = DiskQueue(str(db_path))
    buffer = deque(maxlen=512)
    dq.push(1234567890, '{"timestamp": 1234567890, "data": [1,2,3]}')
    adapter = StreamAdapter(stream=None, buffer=buffer, disk_queue=dq)
    adapter.replay_from_disk(batch_size=1)
    assert len(buffer) == 1
@pytest.mark.asyncio
async def test_metrics_endpoint_auth():
    async with AsyncClient(app=app, base_url="<http://test>") as ac:
        headers = {"x-api-key": "supersecretkey"}
        response = await ac.get("/metrics", headers=headers)
        assert response.status_code == 200
        assert "stream_latency_99p" in response.text