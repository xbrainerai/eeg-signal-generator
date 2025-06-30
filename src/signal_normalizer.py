import json
import sys
from collections import deque
from datetime import datetime
from typing import Deque, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field
from rich import print  # rich for coloured debug

CHANNEL_LAYOUT: list[str] = [f"ch{i:02d}" for i in range(16)]  # fixed 16-ch layout

class SignalFrame(BaseModel):
    ts_start: str
    ts_end: str
    frame_seq: int
    rate: int
    channels: list[str] = Field(..., min_items=1)
    data: list[list[float]]           # (samples × channels) in µV

def dc_offset(window: np.ndarray) -> np.ndarray:
    """Remove DC offset per channel."""
    return window - np.mean(window, axis=0)

def process_window(
    win: np.ndarray,
    rate: int,
    seq: int,
    t0: str,
    t1: str
) -> str:
    """Convert window to µV, build SignalFrame JSON."""
    win_uV = win * 1e6
    win_dc = dc_offset(win_uV)
    frame = SignalFrame(
        ts_start=t0,
        ts_end=t1,
        frame_seq=seq,
        rate=rate,
        channels=CHANNEL_LAYOUT[: win_dc.shape[1]],
        data=win_dc.tolist(),
    )
    return frame.model_dump_json()

def main() -> None:
    buf: Deque[Tuple[str, np.ndarray]] = deque()
    rate: Optional[int] = None
    seq = 0
    prev_ts: Optional[datetime] = None

    for line in sys.stdin:
        # DEBUG: show first 60 chars of each incoming line
        print(f"[cyan]📥 Received line[/] {line[:60]}...", file=sys.stderr)

        try:
            pkt = json.loads(line)
            data = np.asarray(pkt["data"])
            curr_ts = datetime.fromisoformat(pkt["ts"])

            # Estimate sampling rate from first two packets
            if rate is None and prev_ts:
                delta = (curr_ts - prev_ts).total_seconds()
                rate = int(1 / delta) if delta > 0 else 256
                print(f"[green]✓ Detected sampling rate: {rate} Hz[/]", file=sys.stderr)

            prev_ts = curr_ts
            buf.append((pkt["ts"], data))

            # DEBUG: show buffer fill level
            if rate:
                need = int(0.25 * rate)
                print(f"[magenta]🧪 Buffered {len(buf)}/{need} samples[/]", file=sys.stderr)

            # Emit 250 ms windows
            if rate and len(buf) >= int(0.25 * rate):
                times, samples = zip(*list(buf))
                t0, t1 = times[0], times[-1]
                win = np.vstack(samples)
                print(process_window(win, rate, seq, t0, t1))  # actual payload → stdout
                buf.clear()
                seq += 1

        except Exception as exc:
            print(f"[red]❌ Error: {exc}[/]", file=sys.stderr)

if __name__ == "__main__":
    main()
