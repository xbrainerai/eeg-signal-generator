import asyncio, json, math, os, random, time
from datetime import datetime, timezone
from typing import List

import numpy as np
import websockets
from websockets.server import WebSocketServerProtocol

DEFAULT_RATE   = int(os.getenv("RATE", 256))      # Hz
DEFAULT_CH     = int(os.getenv("CH", 8))          # channels
WAVEFORM       = os.getenv("WAVE", "sine")        # sine|noise|spike|mixed
PORT           = int(os.getenv("PORT", 8765))

class EEGGenerator:
    def __init__(self, rate:int, ch:int, wf:str):
        self.rate, self.ch, self.wf = rate, ch, wf
        self.dt = 1.0 / rate
        self.t  = 0.0
        self.seq= 0

    def _sine(self) -> np.ndarray:
        freq = 10  # 10 Hz alpha
        return 50e-6 * np.sin(2*math.pi*freq*self.t + np.arange(self.ch))

    def _noise(self) -> np.ndarray:
        return 20e-6 * np.random.randn(self.ch)

    def _spike(self) -> np.ndarray:
        base = self._noise()
        if random.random() < 0.002:                       # rare spike
            base[random.randint(0, self.ch-1)] += 300e-6  # 300 µV
        return base

    def sample(self) -> dict:
        if self.wf == "sine":
            sig = self._sine()
        elif self.wf == "noise":
            sig = self._noise()
        elif self.wf == "spike":
            sig = self._spike()
        else:  # mixed
            sig = self._sine() + self._noise() + self._spike()

        frame = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "seq": self.seq,
            "data": sig.tolist()
        }
        self.seq += 1
        self.t   += self.dt
        return frame

async def producer(ws: WebSocketServerProtocol, gen: EEGGenerator):
    try:
        while True:
            await ws.send(json.dumps(gen.sample()))
            await asyncio.sleep(gen.dt)
            # inject discontinuity 1×/min
            if random.random() < 1/(60*gen.rate):
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        pass

async def handler(ws: WebSocketServerProtocol):
    gen = EEGGenerator(DEFAULT_RATE, DEFAULT_CH, WAVEFORM)
    producer_task = asyncio.create_task(producer(ws, gen))
    try:
        await ws.wait_closed()
    finally:
        producer_task.cancel()

# ─── main runner ──────────────────────────────────────────────────────────────
async def main():
    # Start the WebSocket server inside an async-context-manager
    async with websockets.serve(handler, "", PORT):
        print(f"🌐 Mock EEG stream  •  {DEFAULT_CH}ch @ {DEFAULT_RATE} Hz  •  ws://localhost:{PORT}")
        await asyncio.Future()        # keep the server alive forever

if __name__ == "__main__":
    asyncio.run(main())
