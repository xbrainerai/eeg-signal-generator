from datetime import datetime
from typing import List

class Metric:
    ts: datetime | None = None
    buf: float | None = None
    lat: float | None = None
    drop: int = 0
    anomaly: bool = False

    def to_string(self) -> str:
        delim = " | "
        ts_str = self.ts.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z" if self.ts is not None else "None"

        return delim.join([
            ts_str,
            f"buf={self.buf}",
            f"lat={self.lat}",
            f"drop={self.drop}",
            f"anomaly={self.anomaly}"
        ])
