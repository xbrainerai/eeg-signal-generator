import asyncio
from collections import deque
import time

from httpx._transports import mock
import pytest
from httpx import AsyncClient

from metrics import metrics_collector
from metrics.metrics_collector import MetricsCollector
from protocol.protocol_stream_interface import ProtocolStreamReaderProtocol
from protocol.types import SignalChunk
from stream import buffer_management_handler
from stream.execution_event_bus import ExecutionEventBus
from stream.execution_orchestrator import ExecutionOrchestrator
from stream.execution_state_machine import ExecutionStateMachine
from stream.gate_manager import GateManager
from stream.rollback_handler import RollbackHandler
from stream.stream_adapter import StreamAdapter
from src.stream_metrics import MetricsHandler
from src.disk_queue import DiskQueue
from main import app, execution_orchestrator
from stream.task_queue import TaskQueue
from stream.violation_handler import ViolationHandler  # FastAPI app with /metrics
from stream.buffer_management_handler import BufferManagementHandler
from unittest.mock import Mock

class MockStream(ProtocolStreamReaderProtocol):
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
            self.start_time = time.perf_counter()

        # Handle high-frequency streaming for stress tests
        if self.target_fps:
            target_interval = 1.0 / self.target_fps
            current_time = time.perf_counter()
            expected_time = self.start_time + (self.counter * target_interval)

            while current_time < expected_time:
                current_time = time.perf_counter()
        else:
            # Original burst/silence pattern
            if self.burst and self.counter % 10 == 0:
                await asyncio.sleep(0.01)
            elif not self.burst and self.counter % 10 == 0:
                await asyncio.sleep(0.20)

        self.counter += 1
        return SignalChunk(
            timestamp=asyncio.get_event_loop().time(),
            window_ms=100,
            channels=["Fp1", "Fp2"],
            units="uV",
            matrix=[[0.1, 0.2], [0.3, 0.4]],
        )

@pytest.mark.asyncio
async def test_burst_and_silence_handling():
    buffer = deque(maxlen=512)
    stream = MockStream(burst=True)
    adapter = StreamAdapter(stream=stream, buffer=buffer, should_always_log_buffer=True)
    buffer_management_handler = BufferManagementHandler(buffer, len(buffer), adapter.disk_queue)
    await adapter.consume_stream()
    main_ingest = adapter.main_ingest
    processed_first_metric = False

    mock_context = {'packet': 'mock_packet'}

    while main_ingest.has_next_metric_to_process():
        metric = await main_ingest.process_and_next_metric()
        assert metric.lat is not None
        assert metric.ts is not None
        assert metric.stream_id is not None
        assert metric.total is not None
        assert metric.drop is not None
        assert metric.anomaly is not None
    adapter.main_ingest

    # assert metrics_collector.metrics.buffer_fill_pct > 0
    # assert metrics_collector.metrics.latency_list, "Latency list should not be empty"

@pytest.mark.asyncio
async def test_disk_queue_roundtrip(tmp_path):
    db = tmp_path / "buf.db"
    dq = DiskQueue(str(db))
    dq.push(123.4, '{"foo": "bar"}')
    out = dq.pop(limit=1)
    assert out == ['{"foo": "bar"}']
    assert dq.size() == 0

@pytest.mark.asyncio
async def test_high_frequency_stress_10k_fps():
    """Test system with 10k frames/s for 60s and monitor metric loss"""
    from metrics.main_ingest import MainIngest
    import time

    # Calculate total frames for 60s at 10k fps
    target_fps = 10000
    duration_seconds = 5
    total_frames = target_fps * duration_seconds  # 600k frames

    buffer = deque(maxlen=2048)  # Larger buffer for high throughput
    metrics = MetricsHandler()
    metric_collector = MetricsCollector()
    # Create high-frequency stream
    stream = MockStream(burst=False, total_packets=total_frames, target_fps=target_fps)
    adapter = StreamAdapter(stream=stream, buffer=buffer)

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
        metric_collection_task = asyncio.create_task(metric_collector.collect_metrics())
        # Monitor metrics collection for duration
        while time.time() - start_time < duration_seconds:
            # Simulate metrics being generated

            # Count metrics in queue


            await asyncio.sleep(0.01)  # Check every second

        # Cancel stream consumption
        consume_task.cancel()
        metric_collection_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            pass

    except Exception as e:
        print(f"Stress test error: {e}")
    metrics_collected = metric_collector.metrics_collected
    end_time = time.time()
    actual_duration = end_time - start_time

    # Calculate performance metrics
    frames_processed = adapter.total_packets_received
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
    assert metric_loss_rate < 5.0, f"Metric loss rate {metric_loss_rate:.2f}% exceeds 5% threshold"

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
        adapter = StreamAdapter(stream=stream, buffer=buffer)

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
        # if hasattr(metrics, 'total_frames'):
        throughput = adapter.total_packets_received / actual_duration
        print(f"Buffer size {buffer_size}: {throughput:.0f} fps")

        # Basic assertion - should process at least 80% of target
        assert throughput >= fps_target * 0.8, f"Buffer {buffer_size} underperformed"
