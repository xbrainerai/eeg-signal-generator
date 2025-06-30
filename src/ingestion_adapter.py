import asyncio
import json
import os
import sys
from collections import deque
from datetime import datetime, timezone
from typing import Deque, List

import numpy as np
import websockets
from rich import print as rprint   # coloured diagnostics

WS_URL     = os.getenv("WS_URL", "ws://localhost:8765")
BUFFER_SEC = int(os.getenv("BUFFER_SEC", 5))   # seconds kept in ring
DIAG_EVERY = 1.0                              # seconds between diagnostics

# ────────── simple ring buffer (for latency stats only) ──────────
class RingBuffer:
    def __init__(self, sec: int, rate_hi: int, ch: int):
        self.max_len = sec * rate_hi
        self.data: Deque[np.ndarray] = deque(maxlen=self.max_len)

    def append(self, vec: List[float]): self.data.append(np.asarray(vec))

# ────────── main ingest coroutine ──────────
async def ingest() -> None:
    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=None) as ws:
                first_raw = await ws.recv()
                first_pkt = json.loads(first_raw)
                ch        = len(first_pkt["data"])
                ring      = RingBuffer(BUFFER_SEC, 1024, ch)
                last_seq  = first_pkt["seq"]

                rprint(f"[green]✓ Connected[/] {WS_URL} • channels={ch}", file=sys.stderr)

                # send first packet
                _out(first_pkt)
                ring.append(first_pkt["data"])

                async for raw in ws:
                    pkt = json.loads(raw)

                    # basic sequence check
                    if pkt["seq"] != last_seq + 1:
                        rprint(f"[yellow]⛔ Seq jump {last_seq}->{pkt['seq']}[/]", file=sys.stderr)

                    ring.append(pkt["data"])
                    last_seq = pkt["seq"]

                    _out(pkt)                         # write to stdout

                    # diagnostics every DIAG_EVERY sec
                    if last_seq % int(1 / DIAG_EVERY / (1 / 256)) == 0:
                        pct = 100 * len(ring.data) / ring.max_len
                        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
                        rprint(f"{now}  buffer={pct:3.0f}%  last_seq={last_seq}", file=sys.stderr)

        except Exception as exc:
            rprint(f"[red]Connection error:[/] {exc} • retrying in 1 s", file=sys.stderr)
            await asyncio.sleep(1)

# ────────── helper to write packet cleanly ──────────
def _out(pkt: dict) -> None:
    """Emit exactly one compact JSON line to stdout."""
    line = json.dumps(pkt, separators=(",", ":"))
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

# ────────── entrypoint ──────────
if __name__ == "__main__":
    asyncio.run(ingest())
