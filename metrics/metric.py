from datetime import datetime
from typing import List

class Metric:
    ts: datetime | None = None
    total: int = 0
    buf: float | None = None
    lat: float | None = None
    drop: int = 0
    anomaly: bool = False

    def to_string(self) -> str:
        delim = " | "
        metrics = []

        if self.ts is not None:
            ts_str = self.ts.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + "Z" if self.ts is not None else "None"
            metrics.append(f"ts={ts_str}")

        if self.total is not None:
            metrics.append(f"total={self.total}")

        if self.buf is not None:
            metrics.append(f"buf={self.buf}")

        if self.lat is not None:
            metrics.append(f"lat={self.lat}")

        if self.drop is not None:
            metrics.append(f"drop={self.drop}")

        if self.anomaly is not None:
            metrics.append(f"anomaly={self.anomaly}")


        return delim.join(metrics)
