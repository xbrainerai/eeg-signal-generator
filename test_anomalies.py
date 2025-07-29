import requests
import time

def test_anomalies():
    base_url = "http://localhost:8080"

    # Reset the validator first
    print("🔄 Resetting validator...")
    requests.post(f"{base_url}/reset")

    # Test 1: Timestamp regression
    print("\n📉 Testing timestamp regression...")
    frames = [
        {"timestamp": 1000, "channel_id": "eeg1", "sequence_id": 0},
        {"timestamp": 900, "channel_id": "eeg1", "sequence_id": 1},  # Regression!
    ]

    for frame in frames:
        # You'd normally send this to the validator
        print(f"Frame: {frame}")
        time.sleep(0.1)

    # Test 2: Gap detection
    print("\n⏰ Testing gap detection...")
    frames = [
        {"timestamp": 1000, "channel_id": "eeg1", "sequence_id": 0},
        {"timestamp": 1010, "channel_id": "eeg1", "sequence_id": 1},  # 10ms gap > 5ms threshold
    ]

    for frame in frames:
        print(f"Frame: {frame}")
        time.sleep(0.1)

    # Check metrics
    print("\n📊 Current metrics:")
    response = requests.get(f"{base_url}/metrics")
    print(response.text)

if __name__ == "__main__":
    test_anomalies()
