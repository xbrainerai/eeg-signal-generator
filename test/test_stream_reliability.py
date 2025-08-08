import asyncio
from collections import deque

import pytest
from httpx import AsyncClient

from stream.stream_adapter import StreamAdapter
from src.stream_metrics import MetricsHandler
from src.disk_queue import DiskQueue
from main import app  # FastAPI app with /metrics

class MockStream:
    """Async iterator emitting packets with configurable burst & silence patterns."""
    def __init__(self, burst: bool = True, total_packets: int = 200, target_fps: int | None = None) -> None:
        self.burst = burst
        self.counter = 0
        self.total_packets = total_packets
        self.target_fps = target_fps
        self.start_time = None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.counter >= self.total_packets:
            raise StopAsyncIteration

        if self.start_time is None:
            self.start_time = asyncio.get_event_loop().time()

        # Handle high-frequency streaming for stress tests
        if self.target_fps:
            target_interval = 1.0 / self.target_fps
            current_time = asyncio.get_event_loop().time()
            expected_time = self.start_time + (self.counter * target_interval)

            if current_time < expected_time:
                await asyncio.sleep(expected_time - current_time)
        else:
            # Original burst/silence pattern
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

@pytest.mark.asyncio
async def test_high_frequency_stress_10k_fps():
    """Test system with 10k frames/s for 60s and monitor metric loss"""
    from metrics.metrics_collector import MetricsCollector
    from metrics.main_ingest import MainIngest
    import time

    # Calculate total frames for 60s at 10k fps
    target_fps = 10000
    duration_seconds = 60
    total_frames = target_fps * duration_seconds  # 600k frames

    buffer = deque(maxlen=2048)  # Larger buffer for high throughput
    metrics = MetricsHandler()

    # Create high-frequency stream
    stream = MockStream(burst=False, total_packets=total_frames, target_fps=target_fps)
    adapter = StreamAdapter(stream=stream, buffer=buffer, metrics=metrics)

    # Initialize metrics collection
    main_ingest = MainIngest()

    # Clear any existing metrics
    with main_ingest.lock:
        main_ingest.stream_adapter_metrics_processing_queue.clear()

    # Track metrics
    start_time = time.time()
    frames_processed = 0
    metrics_collected = 0

    try:
        # Start consuming stream in background
        consume_task = asyncio.create_task(adapter.consume_stream())

        # Monitor metrics collection for duration
        while time.time() - start_time < duration_seconds:
            # Simulate metrics being generated
            if hasattr(metrics, 'total_frames'):
                frames_processed = metrics.total_frames

            # Count metrics in queue
            with main_ingest.lock:
                metrics_collected = len(main_ingest.stream_adapter_metrics_processing_queue)

            await asyncio.sleep(1)  # Check every second

        # Cancel stream consumption
        consume_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        print(f"Stress test error: {e}")

    end_time = time.time()
    actual_duration = end_time - start_time

    # Calculate performance metrics
    actual_fps = frames_processed / actual_duration if actual_duration > 0 else 0

    # Metric loss calculation
    expected_metrics = frames_processed
    with main_ingest.lock:
        remaining_metrics = len(main_ingest.stream_adapter_metrics_processing_queue)

    # For this test, we expect some metrics to be processed during the run
    # So we calculate loss based on what should have been generated
    metric_loss_rate = 0
    if expected_metrics > 0:
        metric_loss_rate = max(0, (expected_metrics - remaining_metrics - metrics_collected) / expected_metrics * 100)

    print(f"Stress test results:")
    print(f"Duration: {actual_duration:.2f}s")
    print(f"Frames processed: {frames_processed}")
    print(f"Actual FPS: {actual_fps:.0f}")
    print(f"Metrics collected: {metrics_collected}")
    print(f"Metrics remaining: {remaining_metrics}")
    print(f"Metric loss rate: {metric_loss_rate:.2f}%")

    # Assertions for performance requirements
    assert actual_fps >= target_fps * 0.8, f"Actual FPS {actual_fps:.0f} is too low (target: {target_fps})"
    assert metric_loss_rate < 5.0, f"Metric loss rate {metric_loss_rate:.2f}% exceeds 5% threshold"
    assert metrics.buffer_fill_pct is not None, "Buffer metrics should be tracked"

@pytest.mark.asyncio
async def test_buffer_throttling_adjustment():
    """Test buffer and throttling adjustments under load"""
    from metrics.metrics_collector import MetricsCollector

    # Test with different buffer sizes
    buffer_sizes = [512, 1024, 2048]
    fps_target = 5000  # Moderate load
    duration = 10  # Shorter duration for CI

    for buffer_size in buffer_sizes:
        buffer = deque(maxlen=buffer_size)
        metrics = MetricsHandler()

        # Create stream
        total_packets = fps_target * duration
        stream = MockStream(burst=False, total_packets=total_packets, target_fps=fps_target)
        adapter = StreamAdapter(stream=stream, buffer=buffer, metrics=metrics)

        start_time = time.time()

        # Run for duration
        consume_task = asyncio.create_task(adapter.consume_stream())
        await asyncio.sleep(duration)
        consume_task.cancel()

        try:
            await consume_task
        except asyncio.CancelledError:
            pass

        end_time = time.time()
        actual_duration = end_time - start_time

        # Larger buffers should handle higher throughput better
        if hasattr(metrics, 'total_frames'):
            throughput = metrics.total_frames / actual_duration
            print(f"Buffer size {buffer_size}: {throughput:.0f} fps")

            # Basic assertion - should process at least 80% of target
            assert throughput >= fps_target * 0.8, f"Buffer {buffer_size} underperformed"
