import time
from packet_timestamp_validator.timestamp_validator import DefaultTimestampValidator
import yaml

with open("verification_config.yaml") as f:
    config = yaml.safe_load(f)

validator = DefaultTimestampValidator(config)

for i in range(60):
    ts = i * (1000 // config["sampling_rate"])
    if i == 30:
        ts -= 50  # Inject regression
    result = validator.validate({"timestamp": ts, "channel_id": "eeg1"})
    print(i, result)
    time.sleep(0.01)
