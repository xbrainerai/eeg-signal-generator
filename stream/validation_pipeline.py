import json
import logging
from stream.validators import *
from stream.stream_metrics import validation_failures, stream_jitter_ms, stream_jitter_hist_ms

logger = logging.getLogger("validation")
logger.setLevel(logging.WARNING)

DROP_MALFORMED = True
QUARANTINE_FILE = "eeg_stream_adapter/quarantine_malformed.jsonl"

# Stateful timestamp holder (to be optionally reset externally)
_last_ts = None

def validate_frame(frame, frequency: float):
    global _last_ts

    try:
        if not has_required_fields(frame):
            raise ValueError("Missing required fields")

        if not is_channel_count_valid(frame):
            raise ValueError("Invalid channel count")

        if not is_value_range_valid(frame):
            raise ValueError("Out-of-range µV values")

        curr_ts = frame["timestamp"]
        if _last_ts is not None:
            jitter_ms = (curr_ts - _last_ts) * 1000
            stream_jitter_ms.observe(jitter_ms)
            stream_jitter_hist_ms.observe(jitter_ms)
            if not is_timestamp_monotonic(curr_ts, _last_ts, frequency):
                _last_ts = curr_ts
                raise ValueError("Timestamp jitter/skew")
        _last_ts = curr_ts

        return True

    except Exception as e:
        validation_failures.inc()
        logger.warning(f"[ValidationError] Type={type(e).__name__} Reason={str(e)} TS={frame.get('timestamp', 'N/A')}")
        if not DROP_MALFORMED:
            try:
                with open(QUARANTINE_FILE, "a") as f:
                    f.write(json.dumps(frame) + "\n")
            except Exception as write_err:
                logger.error(f"[QuarantineWriteError] {write_err}")
        return False
