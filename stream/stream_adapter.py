
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timedelta
from typing import AsyncIterator, Deque, Optional

try:
    import websockets
except ModuleNotFoundError:
    websockets = None

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

# ────────────── Logging Setup ──────────────
logging.basicConfig(
    filename="logs/stream_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

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

        self._last_warn = datetime.min.replace(tzinfo=timezone.utc)
        self._latency_history: list[float] = []
        self.metrics_collector = MetricsCollector()


    async def consume_stream(self) -> None:
        if self.stream is None:
            raise RuntimeError("StreamAdapter.consume_stream() called with stream=None")

        last_packet_ts = None
        async for packet in self.stream:
            print("📥 Received from WebSocket:", packet)
            # Jitter metric
            pkt_ts = float(packet.get("timestamp", 0))
            if last_packet_ts is not None:
                jitter_ms = (pkt_ts - last_packet_ts) * 1000.0
                stream_jitter_ms.observe(jitter_ms)
            last_packet_ts = pkt_ts
            self._process_packet(packet)
            buf_pct = len(self.buffer) / self.buffer_limit * 100.0
            self.metrics_collector.stage_buffer_fill(buf_pct)
            stream_buffer_fill.set(buf_pct)
            self.metrics_collector.output_current_metric()
            if self.throttle_hz and buf_pct > 90:
                await asyncio.sleep(1 / self.throttle_hz)

    def _process_packet(self, packet: SignalChunk) -> None:
        if self.throttle_hz is None:
            self._warn_drop("Rejected because throttle Hz is not set")
            return

        now = time.time()
        pkt_ts = float(packet.get("timestamp", now))
        latency_ms = (now - pkt_ts) * 1000.0
        stream_latency_ms.observe(latency_ms)
        self.metrics_collector.stage_end_to_end_latency(latency_ms)
        self._latency_history.append(latency_ms)
        if len(self._latency_history) > 1000:
            self._latency_history.pop(0)
        sorted_latency = sorted(self._latency_history)
        p99 = sorted_latency[int(0.99 * len(sorted_latency))] if sorted_latency else 0
        stream_latency_99p.set(p99)

        if not validate_frame(packet, self.throttle_hz, metrics_collector=self.metrics_collector):
            self._warn_drop("Rejected by validation pipeline")
            self.metrics_collector.inc_dropped_packet_count()
            self.metrics_collector.stage_anomoly_detection()
            return

        if len(self.buffer) >= self.buffer_limit:
            print("⚠️ Dropped due to full buffer")
            oldest = self.buffer.popleft()
            stream_dropped_packets.inc()
            if self.disk_queue:
                asyncio.create_task(self._push_to_disk(oldest))

        print("✅ Ingested successfully")
        self.buffer.append(packet)
        stream_total_ingested.inc()

    async def _push_to_disk(self, pkt: SignalChunk) -> None:
        try:
            if self.disk_queue is None:
                return
            self.disk_queue.push(pkt.get("timestamp", time.time()), json.dumps(pkt))
        except Exception as exc:
            logging.error("DiskQueue push failed: %s", exc)

    def _warn_drop(self, msg: str) -> None:
        now = datetime.now(timezone.utc)
        if now - self._last_warn > timedelta(seconds=5):
            logging.warning(msg)
            self._last_warn = now
