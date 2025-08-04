import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional
from collections import deque

from stream.stream_metrics import stream_dropped_packets, stream_total_ingested
from stream.disk_queue import DiskQueue
from protocol.types import SignalChunk


class BufferManagementHandler:
    """Handles buffer management operations as tasks for the execution orchestrator"""

    def __init__(self, buffer: deque, buffer_limit: int, disk_queue: Optional[DiskQueue] = None):
        self.buffer = buffer
        self.buffer_limit = buffer_limit
        self.disk_queue = disk_queue
        self.logger = logging.getLogger(__name__)

    async def handle_buffer_append(self, context: Dict[str, Any]) -> None:
            packet = context.get('packet')
            if packet is None:
                self.logger.error("No packet provided in context")
                return

            # Add the new packet to buffer
            self.buffer.append(packet)
            stream_total_ingested.inc()

            self.logger.info("✅ Buffer management completed successfully")

    async def handle_buffer_management(self, context: Dict[str, Any]) -> None:
        """Handle buffer management task"""
        try:
            # packet = context.get('packet')
            # if packet is None:
            #     self.logger.error("No packet provided in context")
            #     return

            # Check if buffer is full and make room
            while len(self.buffer) >= self.buffer_limit:
                self.logger.warning("⚠️ Dropped due to full buffer")
                oldest = self.buffer.popleft()
                stream_dropped_packets.inc()

                # Push to disk if disk queue is available
                if self.disk_queue:
                    await self._push_to_disk(oldest)

            # Add the new packet to buffer
            # self.buffer.append(packet)
            # stream_total_ingested.inc()

            # self.logger.info("✅ Buffer management completed successfully")

        except Exception as e:
            self.logger.error(f"Error in buffer management handler: {e}")
            raise

    async def _push_to_disk(self, pkt: SignalChunk) -> None:
        """Push a packet to disk"""
        try:
            if self.disk_queue is None:
                return
            self.disk_queue.push(pkt.get("timestamp", time.time()), json.dumps(pkt))
        except Exception as exc:
            self.logger.error(f"DiskQueue push failed: {exc}")
            raise
