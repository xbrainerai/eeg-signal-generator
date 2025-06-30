from time import time
from threading import Lock

class MetricsHandler:
    def __init__(self) -> None:
        self.lock = Lock()
        self.reset()


    def reset(self) -> None:
        with self.lock:
            self.latency_list: list[float] = []
            self.buffer_fill_pct: float = 0.0
            self.dropped_packets: int = 0

    def update_latency(self, latency_ms: float) -> None:
        with self.lock:
            self.latency_list.append(latency_ms)
            if len(self.latency_list) > 1_000:
                self.latency_list.pop(0)

    def update_buffer_fill(self, pct: float) -> None:
        with self.lock:
            self.buffer_fill_pct = pct

    def increment_dropped_packets(self, n: int = 1) -> None:
        with self.lock:
            self.dropped_packets += n

    def prometheus_format(self) -> str:
        with self.lock:
            p99 = (
                sorted(self.latency_list)[int(0.99 * len(self.latency_list))]
                if self.latency_list
                else 0.0
            )
            return "\n".join(
                [
                    "# HELP stream_latency_99p Milliseconds at 99th percentile",
                    "# TYPE stream_latency_99p gauge",
                    f"stream_latency_99p {p99:.2f}",
                    "",
                    "# HELP stream_buffer_fill_percent Current buffer fill percent",
                    "# TYPE stream_buffer_fill_percent gauge",
                    f"stream_buffer_fill_percent {self.buffer_fill_pct:.2f}",
                    "",
                    "# HELP stream_dropped_packets Total dropped packets",
                    "# TYPE stream_dropped_packets counter",
                    f"stream_dropped_packets {self.dropped_packets}",
                ]
            )
