# stream_metrics.py
from time import time
from threading import Lock
class MetricsHandler:
    def __init__(self):
        self.lock = Lock()
        self.reset()
    def reset(self):
        with self.lock:
            self.latency_list = []
            self.buffer_fill_pct = 0
            self.dropped_packets = 0
    def update_latency(self, latency_ms):
        with self.lock:
            self.latency_list.append(latency_ms)
            if len(self.latency_list) > 1000:
                self.latency_list.pop(0)
    def update_buffer_fill(self, fill_pct):
        with self.lock:
            self.buffer_fill_pct = fill_pct
    def increment_dropped_packets(self):
        with self.lock:
            self.dropped_packets += 1
    def prometheus_format(self):
        with self.lock:
            latency_99p = sorted(self.latency_list)[int(0.99 * len(self.latency_list))] if self.latency_list else 0
            output = [
                f'# HELP stream_latency_99p Milliseconds at 99th percentile',
                f'# TYPE stream_latency_99p gauge',
                f'stream_latency_99p {latency_99p}',
                '',
                f'# HELP stream_buffer_fill_percent Current buffer fill percent',
                f'# TYPE stream_buffer_fill_percent gauge',
                f'stream_buffer_fill_percent {self.buffer_fill_pct:.2f}',
                '',
                f'# HELP stream_dropped_packets Total dropped packets',
                f'# TYPE stream_dropped_packets counter',
                f'stream_dropped_packets {self.dropped_packets}'
            ]
            return '\n'.join(output)