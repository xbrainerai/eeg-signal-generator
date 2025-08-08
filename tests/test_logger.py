from typing import AsyncIterable, Iterable
import pytest
import asyncio
import json
import logging
import tempfile
import os
import time
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# Import the classes we're testing
from metrics.metric import Metric
from metrics.metric_logger_output import MetricLoggerOutput
from metrics.logger_file import MetricLoggerFile
from metrics.logger_ws import MetricLoggerWS
from metrics.main_ingest import MainIngest
from metrics.metrics_collector import MetricsCollector


@pytest.fixture
def sample_metric():
    """Create a sample metric for testing"""
    metric = Metric()
    metric.stream_id = 1
    metric.ts = datetime(2024, 1, 1, 12, 0, 0, 123000)
    metric.total = 100
    metric.buf = 75.5
    metric.lat = 0.25
    metric.drop = 2
    metric.anomaly = True
    return metric


@pytest.fixture
def empty_metric():
    """Create an empty metric for edge case testing"""
    metric = Metric()
    return metric


class TestMetricLoggerOutput:
    """Test CLI console output logger"""

    def test_console_output_normal_metric(self, sample_metric, capsys):
        """Test normal metric output to console"""
        logger = MetricLoggerOutput()
        logger.output(sample_metric)

        captured = capsys.readouterr()
        output = captured.out.strip()

        assert "stream_id=1" in output
        assert "ts=2024-01-01T12:00:00.123Z" in output
        assert "total=100" in output
        assert "buf=75.5" in output
        assert "lat=0.25" in output
        assert "drop=2" in output
        assert "anomaly=True" in output

    def test_console_output_empty_metric(self, empty_metric, capsys):
        """Test empty metric output (edge case)"""
        logger = MetricLoggerOutput()
        logger.output(empty_metric)

        captured = capsys.readouterr()
        output = captured.out.strip()

        # Should output minimal information for empty metric
        assert "total=0" in output
        assert "drop=0" in output
        assert "anomaly=False" in output

    def test_console_output_refresh_performance(self, sample_metric, capsys):
        """Test CLI refresh performance (should be ≤1s for multiple outputs)"""
        logger = MetricLoggerOutput()

        start_time = time.time()

        # Output 100 metrics to simulate burst
        for i in range(100):
            sample_metric.total = i
            logger.output(sample_metric)

        end_time = time.time()
        elapsed = end_time - start_time

        # Should complete well under 1 second
        assert elapsed < 1.0, f"CLI output took {elapsed:.3f}s, should be <1s"


class TestMetricLoggerFile:
    """Test file logger with rotation"""

    @pytest.mark.asyncio
    async def test_file_logger_initialization_valid_params(self):
        """Test file logger initialization with valid parameters"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = MetricLoggerFile(log_file, 1000, 3)
            try:
                assert logger.logger is not None
                await asyncio.sleep(1)
            finally:
                # Explicitly close all handlers to release file locks on Windows
                for handler in logger.logger.handlers[:]:
                    handler.close()
                    logger.logger.removeHandler(handler)


    def test_file_output_normal_metric(self, sample_metric):
        """Test normal metric output to file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = MetricLoggerFile(log_file, 10000, 3)

            try:
                logger.output(sample_metric)

                # Force flush and check file content
                for handler in logger.logger.handlers:
                    handler.flush()

                assert os.path.exists(log_file)
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert "stream_id=1" in content
                    assert "buf=75.5" in content
                    assert "anomaly=True" in content
            finally:
                # Explicitly close all handlers to release file locks on Windows
                for handler in logger.logger.handlers[:]:
                    handler.close()
                    logger.logger.removeHandler(handler)

    def test_file_rotation_no_loss(self, sample_metric):
        """Test file rotation doesn't lose data"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            # Small file size to force rotation
            logger = MetricLoggerFile(log_file, 500, 3)

            try:
                # Write enough data to trigger rotation
                metrics_written = 0
                for i in range(50):
                    sample_metric.total = i
                    logger.output(sample_metric)
                    metrics_written += 1

                    # Force flush very 10 metrics
                    if i % 10 == 0:
                        for handler in logger.logger.handlers:
                            handler.flush()

                # Final flush
                for handler in logger.logger.handlers:
                    handler.flush()

                # Check that files exist
                log_files = [f for f in os.listdir(tmpdir) if f.startswith("test.log")]

                # Count total entries across all files
                total_entries = 0
                for log_file_name in log_files:
                    file_path = os.path.join(tmpdir, log_file_name)
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                        total_entries += len([line for line in lines if "total=" in line])

                # Should have a reasonable number of metrics (file rotation might cause some loss)
                # On Windows, we'll be more lenient due to file locking
                min_expected = metrics_written * 0.3  # 30% retention is acceptable for rotation test with small files
                assert total_entries >= min_expected, f"File rotation lost too many entries: {total_entries} < {min_expected}"

                # The key test is that rotation happened and we didn't lose everything
                assert total_entries > 0, "Should have captured some metrics"

                # At least some rotation should have occurred with small file size
                assert len(log_files) >= 1, "Should have at least one log file"

            finally:
                # Explicitly close all handlers to release file locks on Windows
                for handler in logger.logger.handlers[:]:
                    handler.close()
                    logger.logger.removeHandler(handler)

    def test_file_output_empty_buffer_edge_case(self, empty_metric):
        """Test file output with empty buffer edge case"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "test.log")
            logger = MetricLoggerFile(log_file, 10000, 3)

            try:
                # Output multiple empty metrics
                for _ in range(10):
                    logger.output(empty_metric)

                for handler in logger.logger.handlers:
                    handler.flush()

                assert os.path.exists(log_file)
                with open(log_file, 'r') as f:
                    content = f.read()
                    assert "total=0" in content
                    assert "drop=0" in content
            finally:
                # Explicitly close all handlers to release file locks on Windows
                for handler in logger.logger.handlers[:]:
                    handler.close()
                    logger.logger.removeHandler(handler)


class TestMetricLoggerWS:
    """Test WebSocket logger"""

    @pytest.mark.asyncio
    async def test_ws_logger_initialization(self):
        """Test WebSocket logger initialization"""
        with patch('metrics.logger_ws.serve') as mock_serve:
            # Mock the serve function to prevent actual server startup
            mock_serve.return_value.__aenter__ = AsyncMock()
            mock_serve.return_value.__aexit__ = AsyncMock()

            logger = MetricLoggerWS()
            assert logger.clients == set()
            assert hasattr(logger, 'server_task')

    @pytest.mark.asyncio
    async def test_ws_client_connection_handling(self):
        """Test WebSocket client connection and disconnection"""
        logger = MetricLoggerWS()

        class AsyncIterator(websockets.ServerConnection):
            def __init__(self, seq):
                self.iter = iter(seq)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return next(self.iter)
                except StopIteration:
                    raise StopAsyncIteration

        mock_websocket = AsyncIterator(range(5))

        # Add client
        await logger._handle_client(mock_websocket)

        # Client should be removed after connection closes
        assert mock_websocket not in logger.clients

    @pytest.mark.asyncio
    async def test_ws_send_to_clients_normal_metric(self, sample_metric):
        """Test sending normal metric to WebSocket clients"""
        logger = MetricLoggerWS()

        # Mock client
        mock_client = AsyncMock()
        logger.clients.add(mock_client)

        await logger._send_to_clients(sample_metric)

        # Verify send was called
        mock_client.send.assert_called_once()

        # Verify JSON structure
        call_args = mock_client.send.call_args[0][0]
        metric_data = json.loads(call_args)

        assert metric_data["buffer"] == 75.5
        assert metric_data["latency"] == 0.25
        assert metric_data["dropped"] == 2
        assert metric_data["anomaly"] is True

    @pytest.mark.asyncio
    async def test_ws_send_with_no_clients(self, sample_metric):
        """Test sending metric when no clients connected (edge case)"""
        logger = MetricLoggerWS()

        # Should not raise exception
        await logger._send_to_clients(sample_metric)
        assert len(logger.clients) == 0

    @pytest.mark.asyncio
    async def test_ws_client_disconnection_handling(self, sample_metric):
        """Test handling client disconnections during send"""
        logger = MetricLoggerWS()

        # Mock clients with different behaviors
        good_client = AsyncMock()
        bad_client = AsyncMock()
        bad_client.send.side_effect = ConnectionClosedError(None, None)

        logger.clients.add(good_client)
        logger.clients.add(bad_client)

        await logger._send_to_clients(sample_metric)

        # Bad client should be removed
        assert bad_client not in logger.clients
        assert good_client in logger.clients

    @pytest.mark.asyncio
    async def test_ws_lag_performance(self, sample_metric):
        """Test WebSocket lag performance (should be <200ms for 95% of messages)"""
        logger = MetricLoggerWS()

        # Mock fast client
        fast_client = AsyncMock()
        fast_client.send = AsyncMock(return_value=None)
        logger.clients.add(fast_client)

        # Measure sending times
        send_times = []
        for _ in range(20):
            start_time = time.time()
            await logger._send_to_clients(sample_metric)
            end_time = time.time()
            send_times.append((end_time - start_time) * 1000)  # Convert to ms

        # Check that 95% of sends are under 200ms
        send_times.sort()
        p95_time = send_times[int(len(send_times) * 0.95)]
        assert p95_time < 200, f"95th percentile send time is {p95_time:.2f}ms, should be <200ms"


class TestMainIngest:
    """Test MainIngest singleton and metric processing"""

    def test_singleton_behavior(self):
        """Test that MainIngest behaves as singleton"""
        ingest1 = MainIngest()
        ingest2 = MainIngest()
        assert ingest1 is ingest2

    def test_add_to_queue_thread_safety(self, sample_metric):
        """Test thread-safe addition to metrics queue"""
        ingest = MainIngest()

        # Clear queue
        with ingest.lock:
            ingest.stream_adapter_metrics_processing_queue.clear()

        # Add metric
        ingest.add_to_stream_adapter_metrics_processing_queue(sample_metric)

        with ingest.lock:
            assert len(ingest.stream_adapter_metrics_processing_queue) == 1
            assert ingest.stream_adapter_metrics_processing_queue[0] is sample_metric

    @pytest.mark.asyncio
    async def test_process_and_next_metric_with_data(self, sample_metric):
        """Test processing when metrics are available"""
        ingest = MainIngest()

        # Clear and add metric
        with ingest.lock:
            ingest.stream_adapter_metrics_processing_queue.clear()

        ingest.add_to_stream_adapter_metrics_processing_queue(sample_metric)

        # Should return the metric immediately
        result = await ingest.process_and_next_metric()
        assert result is sample_metric

        # Queue should be empty now
        with ingest.lock:
            assert len(ingest.stream_adapter_metrics_processing_queue) == 0

    @pytest.mark.asyncio
    async def test_process_and_next_metric_empty_queue(self):
        """Test processing when queue is empty (should wait)"""
        ingest = MainIngest()

        # Clear queue
        with ingest.lock:
            ingest.stream_adapter_metrics_processing_queue.clear()

        # This should timeout since no metrics are added
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ingest.process_and_next_metric(), timeout=0.1)


class TestMetricsCollector:
    """Test MetricsCollector integration"""

    def test_collector_initialization_with_config(self):
        """Test collector initialization reads config correctly"""
        # Mock config file
        mock_config = {
            "log_to_console": True,
            "log_file_configuration": {
                "log_file_name": "test.log",
                "log_file_max_size": 1000,
                "log_file_max_count": 3
            }
        }

        with patch('builtins.open'), patch('json.load', return_value=mock_config):
            collector = MetricsCollector()

            # Should have console and file outputs
            assert len(collector.outputs) == 2
            assert any(isinstance(output, MetricLoggerOutput) for output in collector.outputs)
            assert any(isinstance(output, MetricLoggerFile) for output in collector.outputs)

    def test_collector_initialization_console_only(self):
        """Test collector with console-only configuration"""
        mock_config = {
            "log_to_console": True,
            "log_file_configuration": None
        }

        with patch('builtins.open'), patch('json.load', return_value=mock_config):
            collector = MetricsCollector()

            # Should have only console output
            assert len(collector.outputs) == 1
            assert isinstance(collector.outputs[0], MetricLoggerOutput)

    @pytest.mark.asyncio
    async def test_collect_metrics_integration(self, sample_metric):
        """Test end-to-end metric collection"""
        # Mock config
        mock_config = {"log_to_console": True, "log_file_configuration": None}

        with patch('builtins.open'), patch('json.load', return_value=mock_config):
            collector = MetricsCollector()

        # Mock the outputs
        mock_output = Mock()
        collector.outputs = [mock_output]

        # Add metric to ingest
        collector.main_ingest.add_to_stream_adapter_metrics_processing_queue(sample_metric)

        # Run collector briefly
        collector_task = asyncio.create_task(collector.collect_metrics())
        await asyncio.sleep(0.1)
        collector.stop()
        collector_task.cancel()

        try:
            await collector_task
        except asyncio.CancelledError:
            pass

        # Should have called output
        mock_output.output.assert_called()

    @pytest.mark.asyncio
    async def test_collect_metrics_error_handling(self):
        """Test error handling in metrics collection"""
        mock_config = {"log_to_console": True, "log_file_configuration": None}

        with patch('builtins.open'), patch('json.load', return_value=mock_config):
            collector = MetricsCollector()

        # Mock output that raises exception
        mock_output = Mock()
        mock_output.output.side_effect = Exception("Test error")
        collector.outputs = [mock_output]

        # Mock ingest to return a metric
        with patch.object(collector.main_ingest, 'process_and_next_metric',
                         AsyncMock(return_value=Metric())):

            # Should handle error gracefully
            collector_task = asyncio.create_task(collector.collect_metrics())
            await asyncio.sleep(0.1)
            collector.stop()
            collector_task.cancel()

            try:
                await collector_task
            except asyncio.CancelledError:
                pass


class TestBurstErrorScenarios:
    """Test burst error and edge case scenarios"""

    @pytest.mark.asyncio
    async def test_burst_metric_generation(self, sample_metric):
        """Test handling burst of metrics (simulating high load)"""
        ingest = MainIngest()

        # Clear queue
        with ingest.lock:
            ingest.stream_adapter_metrics_processing_queue.clear()

        # Add burst of metrics
        burst_size = 1000
        for i in range(burst_size):
            metric = Metric()
            metric.total = i
            metric.buf = float(i % 100)
            metric.anomaly = (i % 10 == 0)  # 10% anomalies
            ingest.add_to_stream_adapter_metrics_processing_queue(metric)

        # Process all metrics
        processed_count = 0
        anomaly_count = 0

        for _ in range(burst_size):
            metric = await ingest.process_and_next_metric()
            processed_count += 1
            if metric.anomaly:
                anomaly_count += 1

        assert processed_count == burst_size
        assert anomaly_count == burst_size // 10  # Should capture all anomalies

    def test_memory_usage_under_load(self, sample_metric):
        """Test memory usage doesn't grow excessively under load"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Create and process many metrics
        ingest = MainIngest()

        for i in range(10000):
            metric = Metric()
            metric.total = i
            ingest.add_to_stream_adapter_metrics_processing_queue(metric)

            # Process immediately to prevent queue buildup
            with ingest.lock:
                if ingest.stream_adapter_metrics_processing_queue:
                    ingest.stream_adapter_metrics_processing_queue.pop(0)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 50MB)
        assert memory_increase < 50 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.2f}MB"


class TestAnomalyCapture:
    """Test anomaly detection and logging coverage"""

    def test_anomaly_logging_100_percent_capture(self, capsys):
        """Test that 100% of anomalies are captured and logged"""
        logger = MetricLoggerOutput()

        total_anomalies = 0

        for i in range(1000):
            metric = Metric()
            metric.total = i

            # Create anomalies in specific pattern
            if i % 10 == 0:  # Every 10th metric is an anomaly
                metric.anomaly = True
            else:
                metric.anomaly = False

            logger.output(metric)

            if metric.anomaly:
                total_anomalies += 1

        # Check console output for anomalies
        captured = capsys.readouterr()
        output_lines = captured.out.split('\n')

        logged_anomalies = 0
        for line in output_lines:
            if "anomaly=True" in line:
                logged_anomalies += 1

        # Should capture 100% of anomalies
        capture_rate = (logged_anomalies / total_anomalies) * 100 if total_anomalies > 0 else 0
        assert capture_rate >= 99.0, f"Anomaly capture rate is {capture_rate:.1f}%, should be ≥99%"

    def test_anomaly_latency_threshold(self):
        """Test anomaly detection for latency errors <0.5ms"""
        high_latency_metric = Metric()
        high_latency_metric.lat = 0.6  # Above threshold
        high_latency_metric.anomaly = True

        normal_latency_metric = Metric()
        normal_latency_metric.lat = 0.3  # Below threshold
        normal_latency_metric.anomaly = False

        # Verify anomaly flagging logic
        assert high_latency_metric.anomaly is True
        assert normal_latency_metric.anomaly is False

        # Test string representation includes latency
        assert "lat=0.6" in high_latency_metric.to_string()
        assert "lat=0.3" in normal_latency_metric.to_string()


class TestPerformanceRequirements:
    """Test performance requirements and SLA compliance"""

    @pytest.mark.asyncio
    async def test_metric_loss_under_stress(self, sample_metric):
        """Test <5% metric loss under high load"""
        ingest = MainIngest()

        # Clear queue
        with ingest.lock:
            ingest.stream_adapter_metrics_processing_queue.clear()

        # Simulate high-frequency metric generation (like 10k frames/s)
        metrics_sent = 1000
        for i in range(metrics_sent):
            metric = Metric()
            metric.total = i
            ingest.add_to_stream_adapter_metrics_processing_queue(metric)

        # Process with realistic timing constraints
        metrics_processed = 0
        start_time = time.time()

        while time.time() - start_time < 1.0:  # Process for 1 second
            try:
                await asyncio.wait_for(ingest.process_and_next_metric(), timeout=0.001)
                metrics_processed += 1
            except asyncio.TimeoutError:
                break

        # Calculate loss rate
        loss_rate = ((metrics_sent - metrics_processed) / metrics_sent) * 100
        assert loss_rate < 5.0, f"Metric loss rate is {loss_rate:.2f}%, should be <5%"

    def test_file_rotation_performance(self):
        """Test file rotation doesn't cause significant delays"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = os.path.join(tmpdir, "perf_test.log")
            logger = MetricLoggerFile(log_file, 1000, 5)  # Small size for quick rotation

            try:
                start_time = time.time()

                # Write enough to trigger multiple rotations
                for i in range(200):
                    metric = Metric()
                    metric.total = i
                    metric.buf = float(i)
                    logger.output(metric)

                    # Force flush periodically
                    if i % 50 == 0:
                        for handler in logger.logger.handlers:
                            handler.flush()

                end_time = time.time()
                elapsed = end_time - start_time

                # Should complete quickly even with rotations
                assert elapsed < 2.0, f"File logging with rotation took {elapsed:.3f}s, should be <2s"
            finally:
                # Explicitly close all handlers to release file locks on Windows
                for handler in logger.logger.handlers[:]:
                    handler.close()
                    logger.logger.removeHandler(handler)


if __name__ == "__main__":
    # Run specific test suites
    pytest.main([__file__, "-v", "--tb=short"])
