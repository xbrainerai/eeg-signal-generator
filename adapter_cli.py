from __future__ import annotations
import argparse
import asyncio
import logging
from collections import deque

from src.stream_adapter import StreamAdapter, ws_packet_stream
from src.stream_metrics import MetricsHandler
from src.disk_queue import DiskQueue

async def run_adapter(uri: str, use_disk: bool, log_file: str | None) -> None:
    logging.basicConfig(filename=log_file, level=logging.INFO) if log_file else logging.basicConfig(level=logging.INFO)
    buffer = deque(maxlen=512)
    metrics = MetricsHandler()
    dq = DiskQueue() if use_disk else None
    stream = ws_packet_stream(uri)
    adapter = StreamAdapter(stream=stream, buffer=buffer, metrics=metrics, disk_queue=dq)
    await adapter.consume_stream()

def main() -> None:
    parser = argparse.ArgumentParser(description="Run EEG Stream Adapter (CLI).")
    parser.add_argument("--uri", default="ws://localhost:8001/ws", help="WebSocket URI")
    parser.add_argument("--use-disk", action="store_true", help="Enable SQLite overflow queue")
    parser.add_argument("--log", metavar="FILE", help="Write logs to FILE instead of stdout")
    args = parser.parse_args()
    asyncio.run(run_adapter(args.uri, args.use_disk, args.log))

if __name__ == "__main__":  # pragma: no cover
    main()
