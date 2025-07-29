import logging
from prometheus_client import Counter, Gauge, CollectorRegistry
from prometheus_client.core import CollectorRegistry

REGISTRY = CollectorRegistry()
METRICS = {}
LOGGER = logging.getLogger("validator_api")

def setup_metrics():
    global METRICS
    if METRICS:
        LOGGER.debug("setup_metrics(): Already initialized.")
        return

    METRICS.update({
        "timestamp_regressions_total": Counter(
            "timestamp_regressions_total", "Timestamp regression errors", registry=REGISTRY
        ),
        "timestamp_gaps_total": Counter(
            "timestamp_gaps_total", "Timestamp gaps detected", registry=REGISTRY
        ),
        "timestamp_jitter_total": Counter(
            "timestamp_jitter_total", "Timestamp jitter warnings", registry=REGISTRY
        ),
        "delta_ms_latest": Gauge(
            "delta_ms_latest", "Most recent delta (ms)", registry=REGISTRY
        ),
        "timestamp_warnings": Counter(
            "timestamp_validation_warnings_total", "Timestamp validation warnings detected", registry=REGISTRY
        ),
        "timestamp_errors": Counter(
            "timestamp_validation_errors_total", "Timestamp validation errors detected", registry=REGISTRY
        )
    })

    LOGGER.debug("setup_metrics(): Registered keys =", list(METRICS.keys()))
