from prometheus_client import Counter, Gauge, Summary, Histogram

# Total number of EEG packets rejected by validation pipeline
validation_failures = Counter(
    "validation_failures_total", "EEG packets rejected by validation"
)

# Buffer fill % (0 to 100)
stream_buffer_fill = Gauge(
    "stream_buffer_fill_percent", "Current EEG buffer fill percentage"
)

# Total packets dropped due to overflow
stream_dropped_packets = Counter(
    "stream_dropped_packets", "Packets dropped due to buffer overflow"
)

# Latency summary (Prometheus native summary with quantiles)
stream_latency_ms = Summary(
    "stream_latency_ms", "Latency (ms) between packet timestamp and ingestion"
)

# Custom 99th percentile latency (updated manually)
stream_latency_99p = Gauge(
    "stream_latency_99p", "Manually tracked 99th percentile latency (ms)"
)

# Count of successfully ingested packets
stream_total_ingested = Counter(
    "stream_total_ingested", "Total EEG packets successfully ingested"
)

# Jitter summary (difference between consecutive packet timestamps)
stream_jitter_ms = Summary(
    "stream_jitter_ms", "Jitter (ms) between consecutive EEG packet timestamps"
)

# Jitter histogram (for percentiles)
stream_jitter_hist_ms = Histogram(
    "stream_jitter_hist_ms",
    "Jitter (ms) between consecutive EEG packet timestamps (histogram)",
    buckets=(1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000)
)
