from abc import ABC, abstractmethod
import asyncio
import logging
from .validation_result import ValidationResult, ValidationStatus
from .metrics.metrics_definitions import METRICS
from .anomaly_bus import publish_anomaly

class TimestampValidator(ABC):
    @abstractmethod
    def validate(self, frame) -> ValidationResult:
        pass

class DefaultTimestampValidator(TimestampValidator):
    def __init__(self, config, metrics=None):
        self.prev_ts = None
        self.prev_seq = None
        self.warn_count = 0
        self.reset_count = 0
        self.metrics = metrics or {}
        self.dt_exp = 1000.0 / config.get("sampling_rate", 500)
        self.jitter_thresh = config.get("jitter_percent", 1) / 100.0 * self.dt_exp
        self.gap_thresh = config.get("gap_tolerance_ms",  5)
        self.warn_threshold = config.get("warn_threshold", 3)
        self.sync_reset_frames = config.get("sync_reset_frames", 5)
        self.logger = logging.getLogger("validator_api")
        self.logger.debug(f"Validator received metrics keys: {list(self.metrics.keys())}")

    def validate(self, frame):
        ts = frame["timestamp"]
        cid = frame.get("channel_id", "unknown")
        seq = frame.get("sequence_id", None)

        status = ValidationStatus.VALID
        reason = None
        delta = 0

        # Skip validation on the first frame
        if self.prev_ts is not None:
            delta = ts - self.prev_ts

            # Timestamp regression
            if delta < 0:
                status, reason = ValidationStatus.ERROR, "REGRESSION"

            # Sequence checks
            elif seq is not None and self.prev_seq is not None:
                if seq < self.prev_seq:
                    status, reason = ValidationStatus.ERROR, "REGRESSION"
                elif seq > self.prev_seq + 1:
                    status, reason = ValidationStatus.ERROR, "GAP"

            # Gap in timestamps
            elif delta > self.gap_thresh:
                status, reason = ValidationStatus.WARN, "GAP"

            # Jitter check
            elif abs(delta - self.dt_exp) > self.jitter_thresh:
                status, reason = ValidationStatus.WARN, "JITTER"
                if abs(delta - self.dt_exp) > 5:
                    self.logger.warning(f"Δt jitter exceeds 5ms → delta={delta:.2f} ms")

            # Escalation logic
            if status == ValidationStatus.WARN:
                self.warn_count += 1
                self._update_metrics("timestamp_warnings")
                if self.warn_count >= self.warn_threshold:
                    status = ValidationStatus.ERROR
                self._update_metrics("timestamp_warnings")
            elif status == ValidationStatus.ERROR:
                self.reset_count += 1
                self._update_metrics("timestamp_errors")
                if self.reset_count >= self.sync_reset_frames:
                    self.warn_count = 0
                    self.reset_count = 0
            else:
                self.warn_count = 0
                self.reset_count = 0

        # Update last values
        if status != ValidationStatus.ERROR:
            self.prev_ts = ts
            if seq is not None:
                self.prev_seq = seq

        # Update Prometheus metrics
        if self.metrics is not None:
            if reason == "REGRESSION":
                self._update_metrics("timestamp_regressions_total")
            elif reason == "GAP":
                self._update_metrics("timestamp_gaps_total")
            elif reason == "JITTER":
                self._update_metrics("timestamp_jitter_total")

            if "delta_ms_latest" in self.metrics:
                self.metrics["delta_ms_latest"].set(delta)

        # Emit anomaly event
        if status != ValidationStatus.VALID:
            event = {
                "type": "timestamp",
                "severity": reason,
                "channel_id": cid,
                "ts_curr": ts,
                "ts_prev": self.prev_ts,
                "delta": delta,
            }
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(publish_anomaly(event))
            except RuntimeError:
                self.logger.warning("No event loop — using asyncio.run for anomaly")
                asyncio.run(publish_anomaly(event))
            except Exception as e:
                self.logger.error(f"Failed to emit anomaly: {e}")

        self.logger.debug(f"reason={reason}, delta={delta}, keys={list(self.metrics.keys())}")
        return ValidationResult(status=status, reason=reason or "", delta_ms=delta)

    def _update_metrics(self, metric_key):
        if self.metrics is not None and metric_key in self.metrics:
            self.metrics[metric_key].inc()
