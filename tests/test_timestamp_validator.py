import pytest
from src.packet_timestamp_validator.timestamp_validator import DefaultTimestampValidator, ValidationStatus

@pytest.fixture
def config():
    return {
        "sampling_rate": 256,  # dt_expected = ~3.91 ms
        "gap_tolerance_ms": 20,
        "jitter_percent": 20,  # 20% of 3.91 ≈ 0.78ms
        "warn_threshold": 3,
        "sync_reset_frames": 5,
    }

def test_regression(config):
    validator = DefaultTimestampValidator(config)
    validator.validate({"timestamp": 1000})
    result = validator.validate({"timestamp": 900})
    assert result.status == ValidationStatus.ERROR
    assert result.reason == "REGRESSION"

def test_gap(config):
    validator = DefaultTimestampValidator(config)
    validator.validate({"timestamp": 1000})
    result = validator.validate({"timestamp": 1030})  # 30ms > 20ms gap threshold
    assert result.status == ValidationStatus.WARN
    assert result.reason == "GAP"

def test_jitter(config):
    validator = DefaultTimestampValidator(config)
    validator.validate({"timestamp": 1000})
    dt_expected = 1000.0 / config["sampling_rate"]  # ~3.91ms
    jitter_amt = dt_expected + (config["jitter_percent"] / 100.0 * dt_expected) + 1
    result = validator.validate({"timestamp": 1000 + int(jitter_amt)})
    assert result.status == ValidationStatus.WARN
    assert result.reason == "JITTER"

def test_valid_cadence(config):
    validator = DefaultTimestampValidator(config)
    ts = 1000
    dt = round(1000.0 / config["sampling_rate"])
    for _ in range(10):
        result = validator.validate({"timestamp": ts})
        ts += dt
        assert result.status == ValidationStatus.VALID
