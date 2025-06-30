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

from .stream_metrics import MetricsHandler
from .disk_queue import DiskQueue

logging.basicConfig(
    filename="logs/stream_debug.log",
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

async def ws_packet_stream(uri: str) -> AsyncIterator[dict]:
    """Yield JSON packets from a WebSocket URI with auto-reconnect."""
    if websockets is None:
        raise RuntimeError("websockets package not installed")
    retry = 0
    while True:
        try:
            async with websockets.connect(uri, max_queue=None) as ws:
                retry = 0
                async for msg in ws:
                    yield json.loads(msg)
        except Exception as exc:  # noqa: BLE001
            wait = min(2 ** retry, 30)
            logging.warning("WebSocket error (%s) – reconnecting in %ss", exc, wait)
            await asyncio.sleep(wait)
            retry += 1

class StreamAdapter:
    """High-rate EEG packet ingester with overflow protection."""

    def __init__(
        self,
        stream: Optional[AsyncIterator[dict]] = None,
        *,
        buffer: Optional[Deque[dict]] = None,
        buffer_limit: int = 2_048,            
        metrics: Optional[MetricsHandler] = None,
        disk_queue: Optional[DiskQueue] = None,
        throttle_hz: Optional[int] = None,    
    ) -> None:
        self.stream = stream
        self.buffer: Deque[dict] = buffer or deque(maxlen=buffer_limit)
        self.buffer_limit = buffer_limit
        self.metrics = metrics or MetricsHandler()
        self.disk_queue = disk_queue
        self.throttle_hz = throttle_hz

        self._last_warn = datetime.min        
        self._last_ts: float | None = None

    async def consume_stream(self) -> None:
        if self.stream is None:
            raise RuntimeError("StreamAdapter.consume_stream() called with stream=None")

        async for packet in self.stream:
            self._process_packet(packet)

            # Optional self-throttle
            if self.throttle_hz and self.metrics.buffer_fill_pct > 90:
                await asyncio.sleep(1 / self.throttle_hz)

    def _process_packet(self, packet: dict) -> None:
        now = time.time()
        pkt_ts = float(packet.get("timestamp", now))
        latency_ms = (now - pkt_ts) * 1_000.0
        self.metrics.update_latency(latency_ms)

        # Quick validation
        data = packet.get("data")
        if not isinstance(data, list):
            self._warn_drop("Malformed packet (no data list)")
            return

        # Simple continuity check
        if self._last_ts and pkt_ts < self._last_ts:
            self._warn_drop("Out-of-order packet detected")
            return
        self._last_ts = pkt_ts

        # If full: pop oldest, count as drop, optionally spill to disk
        if len(self.buffer) >= self.buffer_limit:
            oldest = self.buffer.popleft()
            self.metrics.increment_dropped_packets()
            if self.disk_queue:
                asyncio.create_task(self._push_to_disk(oldest))

        # Append new packet (never blocks producer)
        self.buffer.append(packet)
        self.metrics.update_buffer_fill(len(self.buffer) / self.buffer_limit * 100.0)

        logging.debug(
            "latency=%.2f ms  buffer=%d/%d (%.1f %%)",
            latency_ms,
            len(self.buffer),
            self.buffer_limit,
            self.metrics.buffer_fill_pct,
        )

    async def _push_to_disk(self, pkt: dict) -> None:
        """Non-blocking SQLite overflow push."""
        try:
            self.disk_queue.push(pkt.get("timestamp", time.time()), json.dumps(pkt))
        except Exception as exc:  # noqa: BLE001
            logging.error("DiskQueue push failed: %s", exc)

    def _warn_drop(self, msg: str) -> None:
        if datetime.utcnow() - self._last_warn > timedelta(seconds=5):
            logging.warning(msg)
            self._last_warn = datetime.utcnow()
        self.metrics.increment_dropped_packets()
