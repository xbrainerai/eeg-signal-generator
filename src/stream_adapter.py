# stream_adapter.py
import asyncio
import logging
import os
import time
import json
from collections import deque
from stream_metrics import MetricsHandler
from disk_queue import DiskQueue
# Setup logging to file
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    filename='logs/stream_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
class StreamAdapter:
    def __init__(self, stream, buffer=None, metrics=None, disk_queue=None, buffer_limit=512):
        self.stream = stream
        self.buffer = buffer if buffer is not None else deque(maxlen=buffer_limit)
        self.buffer_limit = buffer_limit
        self.metrics = metrics if metrics is not None else MetricsHandler()
        self.disk_queue = disk_queue  # Optional fallback
    async def consume_stream(self):
        async for packet in self.stream:
            now = time.time()
            latency = (now - packet.get("timestamp", now)) * 1000  # ms
            # Metrics
            self.metrics.update_latency(latency)
            if "signal" not in packet or not isinstance(packet["signal"], list):
                logging.warning("Malformed packet dropped: missing or invalid 'data'")
                self.metrics.increment_dropped_packets()
                continue
            if len(self.buffer) >= self.buffer_limit:
                logging.warning("RAM buffer full. Packet dropped or queued to disk.")
                self.metrics.increment_dropped_packets()
                if self.disk_queue:
                    self.disk_queue.push(packet["timestamp"], str(packet))
                continue
            self.buffer.append(packet)
            fill_pct = (len(self.buffer) / self.buffer_limit) * 100
            self.metrics.update_buffer_fill(fill_pct)
            logging.debug(f"Latency: {latency:.2f} ms | Buffer: {fill_pct:.2f}%")
    def replay_from_disk(self, batch_size=10):
        if self.disk_queue:
            records = self.disk_queue.pop(limit=batch_size)
            for payload in records:
                # Assume packet is stringified dict — parse or eval as needed
                try:
                    packet = json.loads(payload)
                    self.buffer.append(packet)
                    logging.info("Replayed packet from disk queue.")
                except Exception as e:
                    logging.error(f"Failed to parse disk payload: {e}")
