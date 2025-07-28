from typing import AsyncIterator, Self
from protocol.protocol_stream_interface import ProtocolStreamReaderProtocol
import websockets
import json
import logging
import asyncio
from protocol.types import SignalChunk

class MockEEGStreamReader(ProtocolStreamReaderProtocol):
    def __init__(self, uri: str):
        self.uri = uri
        self.ws = None

    def __aiter__(self) -> Self:
        return self

    async def connect(self):
        if websockets is None:
            raise RuntimeError("websockets package not installed")
        retry = 0
        while True:
            try:
                self.ws = await websockets.connect(self.uri, max_queue=None)
                break
            except Exception as exc:
                wait = min(2 ** retry, 30)
                logging.warning("WebSocket error (%s) – reconnecting in %ss", exc, wait)
                await asyncio.sleep(wait)
                retry += 1

    async def __anext__(self) -> SignalChunk:
        if self.ws is None:
            await self.connect()
        try:
            msg = await self.ws.recv() # type: ignore
            data = json.loads(msg)
            # Convert data to SignalChunk as needed
            chunk = SignalChunk(**data)
            return chunk
        except Exception as exc:
            await self.close()
            raise StopAsyncIteration from exc

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
            self.ws = None

    async def acknowledge_packet(self) -> None:
        if self.ws is not None:
            await self.ws.send("ACK")
