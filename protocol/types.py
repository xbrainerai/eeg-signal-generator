from typing import TypedDict, List

class SignalChunk(TypedDict):
    timestamp: float              # Unix epoch time
    window_ms: int                # Size of signal window in ms
    channels: List[str]          # Channel labels (e.g., Fp1, Fp2)
    units: str                   # Measurement units (e.g., 'uV')
    matrix: List[List[float]]    # 2D signal array [channels][samples]
