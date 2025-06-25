import argparse
import asyncio
import logging
import json
from collections import deque

from stream_adapter import StreamAdapter
from stream_metrics import MetricsHandler
from disk_queue import DiskQueue


class WebSocketStream:
    def __init__(self, uri):
        self.uri = uri

    async def __aiter__(self):
        import websockets
        async with websockets.connect(self.uri) as ws:
            async for message in ws:
                try:
                    yield json.loads(message)
                except json.JSONDecodeError:
                    logging.warning("Invalid JSON received")


async def run_adapter(args):
    if args.log:
        logging.basicConfig(filename=args.log, level=logging.INFO)
    else:
        logging.basicConfig(level=logging.INFO)

    buffer = deque(maxlen=512)
    metrics = MetricsHandler()
    disk_queue = DiskQueue() if args.use_disk else None

    stream = WebSocketStream(args.uri)

    adapter = StreamAdapter(
        stream=stream,
        buffer=buffer,
        metrics=metrics,
        disk_queue=disk_queue
    )
    await adapter.consume_stream()


def cli():
    parser = argparse.ArgumentParser(description="Run EEG Stream Adapter")
    parser.add_argument("--uri", type=str, default="ws://localhost:8001/ws", help="WebSocket URI")
    parser.add_argument("--use_disk", action="store_true", help="Enable disk fallback buffer")
    parser.add_argument("--log", type=str, default=None, help="Optional log file path")
    args = parser.parse_args()
    asyncio.run(run_adapter(args))


if __name__ == "__main__":
    cli()
