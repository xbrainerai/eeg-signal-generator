
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections import deque
from datetime import datetime, timedelta
from typing import AsyncIterator, Deque, Optional

try:
    import websockets
except ModuleNotFoundError:
    websockets = None

from metrics.metric import Metric
from protocol.types import SignalChunk
from stream.stream_metrics import (
    stream_latency_ms,
    stream_latency_99p,
    stream_buffer_fill,
    stream_dropped_packets,
    stream_total_ingested
)
from stream.disk_queue import DiskQueue
from stream.validation_pipeline import validate_frame
from protocol.protocol_stream_interface import ProtocolStreamReaderProtocol
from datetime import datetime, timezone, timedelta
from stream.stream_metrics import stream_jitter_ms
from metrics.metrics_collector import MetricsCollector
from metrics.main_ingest import MainIngest

# ────────────── Configuration ──────────────
def load_stream_config():
    """Load stream configuration from JSON file"""
    stream_config_path = 'stream/stream_config.json'
    with open(stream_config_path) as f:
        return json.load(f)

# Load configuration and set up logger
stream_config = load_stream_config()
_verbose_enabled = stream_config.get('verbose', True)

# ────────────── Logging Setup ──────────────
# Only configure basic logging if no handlers are already configured
if not logging.getLogger().handlers:
    logging.basicConfig(
        filename="logs/stream_debug.log",
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

# Create logger for stream adapter
logger = logging.getLogger('stream_adapter')
if _verbose_enabled:
    logger.setLevel(logging.INFO)
    # Add console handler for verbose output
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')  # Simple format for console
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
else:
    logger.setLevel(logging.WARNING)

# ────────────── Adapter Class ──────────────
class StreamAdapter:
    def __init__(
        self,
        stream: Optional[ProtocolStreamReaderProtocol] = None,
        *,
        buffer: Optional[Deque[SignalChunk]] = None,
        buffer_limit: int = 2048,
        disk_queue: Optional[DiskQueue] = None,
        throttle_hz: Optional[int] = None,
    ) -> None:
        self.stream = stream
        self.buffer: Deque[SignalChunk] = buffer or deque(maxlen=buffer_limit)
        self.buffer_limit = buffer_limit
        self.disk_queue = disk_queue
        self.throttle_hz = throttle_hz
        self.main_ingest = MainIngest()
        self._last_warn = datetime.min.replace(tzinfo=timezone.utc)
        self._latency_history: list[float] = []
        self.dropped_packet_count = 0
        self.total_packets_received = 0

        if stream_config['buffer_period']:
            self.buffer_period = stream_config['buffer_period']

    # Iterates through the stream and processes the packets.
    async def consume_stream(self) -> None:
        if self.stream is None:
            raise RuntimeError("StreamAdapter.consume_stream() called with stream=None")

        last_packet_ts = None
        buffer_metric_last_posted_ts = time.time()
        async for packet in self.stream:
            self.total_packets_received += 1
            logger.info("📥 Received from WebSocket: %s", packet)

            # Create metric for this packet
            metric = Metric()
            metric.drop = self.dropped_packet_count
            metric.ts = datetime.now()
            metric.total = self.total_packets_received

            # Collect latency metric
            now = time.time()
            pkt_ts = float(packet.get("timestamp", 0))
            metric.lat = (now - pkt_ts) * 1000.0

            # Send jitter to observability tools.
            if last_packet_ts is not None:
                jitter_ms = (pkt_ts - last_packet_ts) * 1000.0
                stream_jitter_ms.observe(jitter_ms)

            last_packet_ts = pkt_ts

            # Post latency metrics to observability tools.
            stream_latency_ms.observe(metric.lat)
            self._latency_history.append(metric.lat)
            if len(self._latency_history) > 1000:
                self._latency_history.pop(0)
            sorted_latency = sorted(self._latency_history)
            p99 = sorted_latency[int(0.99 * len(sorted_latency))] if sorted_latency else 0
            stream_latency_99p.set(p99)

            # Process packet and potentially modify metric
            self._process_packet(packet, metric, now)

            # Collect buffer fill metric.
            buf_pct = len(self.buffer) / self.buffer_limit * 100.0
            if self.buffer_period is not None and now - buffer_metric_last_posted_ts > self.buffer_period:
                metric.buf = buf_pct
                buffer_metric_last_posted_ts = time.time()

            # Add metric to processing queue
            self.main_ingest.add_to_stream_adapter_metrics_processing_queue(metric)

            # Throttle if buffer is full
            if self.throttle_hz and buf_pct > 90:
                await asyncio.sleep(1 / self.throttle_hz)

            # Send acknowledgement to packet source to indicate that it's ready for the next packet
            await self.stream.acknowledge_packet()

    # Processes a received packet and potentially modifies the metric
    def _process_packet(self, packet: SignalChunk, metric: Metric, now: float) -> None:
        if self.throttle_hz is None:
            self._warn_drop("Rejected because throttle Hz is not set")
            return

        # Checks that the received packet is valid
        if not validate_frame(packet, self.throttle_hz):
            self._warn_drop("Rejected by validation pipeline")
            self.dropped_packet_count += 1
            metric.drop = self.dropped_packet_count
            metric.anomaly = True
            return

        # Make room in the boffer, save the popped item to disk
        if len(self.buffer) >= self.buffer_limit:
            logger.warning("⚠️ Dropped due to full buffer")
            oldest = self.buffer.popleft()
            stream_dropped_packets.inc()
            if self.disk_queue:
                asyncio.create_task(self._push_to_disk(oldest))

        logger.info("✅ Ingested successfully")
        self.buffer.append(packet)

        stream_total_ingested.inc()

    # Pushes a packet to disk
    async def _push_to_disk(self, pkt: SignalChunk) -> None:
        try:
            if self.disk_queue is None:
                return
            self.disk_queue.push(pkt.get("timestamp", time.time()), json.dumps(pkt))
        except Exception as exc:
            logging.error("DiskQueue push failed: %s", exc)

    # Warns the user that a packet was dropped
    def _warn_drop(self, msg: str) -> None:
        now = datetime.now(timezone.utc)
        if now - self._last_warn > timedelta(seconds=5):
            logging.warning(msg)
            self._last_warn = now
