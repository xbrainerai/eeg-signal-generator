# validators.py
EXPECTED_CHANNELS = 8
VALID_RANGE = (-100.0, 100.0)
REQUIRED_FIELDS = ["timestamp", "values"]

def has_required_fields(frame: dict) -> bool:
    return isinstance(frame, dict) and all(field in frame for field in REQUIRED_FIELDS)

def is_channel_count_valid(frame: dict) -> bool:
    values = frame.get("values", [])
    return isinstance(values, list) and len(values) == EXPECTED_CHANNELS

def is_value_range_valid(frame: dict) -> bool:
    values = frame.get("values", [])
    if not isinstance(values, list):
        return False
    return all(
        isinstance(val, (int, float)) and VALID_RANGE[0] <= val <= VALID_RANGE[1]
        for val in values
    )

def is_timestamp_monotonic(curr_ts: float, prev_ts: float, frequency: float) -> bool:
    if not isinstance(curr_ts, (int, float)) or not isinstance(prev_ts, (int, float)):
        return False
    expected_interval_ms = 1000 / frequency
    delta_ms = (curr_ts - prev_ts) * 1000
    return abs(delta_ms - expected_interval_ms) < (0.1 * expected_interval_ms)
