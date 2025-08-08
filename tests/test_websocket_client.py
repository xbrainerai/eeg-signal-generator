#!/usr/bin/env python3
"""
WebSocket client test for metrics logging lag validation.
Tests that WebSocket metrics are delivered with <200ms lag for 95% of messages.
"""

import asyncio
import json
import time
import statistics
from typing import List
import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK


class MetricsWebSocketClient:
    """WebSocket client for testing metric logging performance"""

    def __init__(self, uri: str = "ws://localhost:8766"):
        self.uri = uri
        self.received_metrics: List[dict] = []
        self.latencies: List[float] = []
        self.connected = False

    async def connect_and_monitor(self, duration_seconds: int = 60):
        """Connect to WebSocket and monitor metrics for specified duration"""
        try:
            async with websockets.connect(self.uri) as websocket:
                self.connected = True
                print(f"✅ Connected to {self.uri}")

                start_time = time.time()

                while time.time() - start_time < duration_seconds:
                    try:
                        # Wait for message with timeout
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        receive_time = time.time()

                        # Parse metric
                        try:
                            metric_data = json.loads(message)
                            self.received_metrics.append(metric_data)

                            # Calculate latency if timestamp is available
                            if metric_data.get('timestamp'):
                                # Parse timestamp
                                ts_str = metric_data['timestamp']
                                if ts_str.endswith('Z'):
                                    ts_str = ts_str[:-1]

                                try:
                                    metric_time = time.mktime(time.strptime(ts_str.split('.')[0], '%Y-%m-%dT%H:%M:%S'))
                                    if '.' in ts_str:
                                        # Add microseconds
                                        microseconds = float('0.' + ts_str.split('.')[1])
                                        metric_time += microseconds

                                    latency_ms = (receive_time - metric_time) * 1000
                                    if latency_ms >= 0 and latency_ms < 10000:  # Reasonable bounds
                                        self.latencies.append(latency_ms)

                                except (ValueError, OverflowError):
                                    pass  # Skip invalid timestamps

                            print(f"📊 Received metric: buffer={metric_data.get('buffer', 'N/A')}, "
                                  f"latency={metric_data.get('latency', 'N/A')}, "
                                  f"dropped={metric_data.get('dropped', 'N/A')}, "
                                  f"anomaly={metric_data.get('anomaly', 'N/A')}")

                        except json.JSONDecodeError:
                            print(f"⚠️  Invalid JSON received: {message}")

                    except asyncio.TimeoutError:
                        # No message received in timeout period
                        continue

                print(f"✅ Monitoring completed. Received {len(self.received_metrics)} metrics")

        except (ConnectionClosedError, ConnectionClosedOK) as e:
            print(f"❌ WebSocket connection closed: {e}")
        except Exception as e:
            print(f"❌ Error connecting to WebSocket: {e}")
        finally:
            self.connected = False

    def analyze_performance(self) -> dict:
        """Analyze the performance metrics"""
        total_metrics = len(self.received_metrics)

        if not self.latencies:
            return {
                'total_metrics': total_metrics,
                'latency_analysis': 'No valid latencies measured',
                'lag_sla_met': False
            }

        # Calculate latency statistics
        latencies_sorted = sorted(self.latencies)
        p95_latency = latencies_sorted[int(0.95 * len(latencies_sorted))] if latencies_sorted else 0
        p99_latency = latencies_sorted[int(0.99 * len(latencies_sorted))] if latencies_sorted else 0
        avg_latency = statistics.mean(self.latencies)
        max_latency = max(self.latencies)
        min_latency = min(self.latencies)

        # Check SLA compliance (95% of messages < 200ms)
        lag_sla_met = p95_latency < 200.0

        return {
            'total_metrics': total_metrics,
            'latency_analysis': {
                'count': len(self.latencies),
                'average_ms': round(avg_latency, 2),
                'min_ms': round(min_latency, 2),
                'max_ms': round(max_latency, 2),
                'p95_ms': round(p95_latency, 2),
                'p99_ms': round(p99_latency, 2)
            },
            'lag_sla_met': lag_sla_met,
            'sla_requirement': '95% of messages < 200ms'
        }


async def test_websocket_lag_performance():
    """Test WebSocket lag performance"""
    print("🔗 Testing WebSocket metric logging lag performance...")

    client = MetricsWebSocketClient()

    # Monitor for 30 seconds to get a good sample
    await client.connect_and_monitor(duration_seconds=30)

    # Analyze performance
    performance = client.analyze_performance()

    print("\n📈 Performance Analysis:")
    print(f"Total metrics received: {performance['total_metrics']}")

    if isinstance(performance['latency_analysis'], dict):
        latency = performance['latency_analysis']
        print(f"Latency metrics analyzed: {latency['count']}")
        print(f"Average latency: {latency['average_ms']}ms")
        print(f"Min latency: {latency['min_ms']}ms")
        print(f"Max latency: {latency['max_ms']}ms")
        print(f"95th percentile: {latency['p95_ms']}ms")
        print(f"99th percentile: {latency['p99_ms']}ms")

        sla_status = "✅ PASSED" if performance['lag_sla_met'] else "❌ FAILED"
        print(f"\nSLA Compliance ({performance['sla_requirement']}): {sla_status}")

        if not performance['lag_sla_met']:
            print(f"⚠️  95th percentile latency ({latency['p95_ms']}ms) exceeds 200ms threshold")

    else:
        print(f"Latency analysis: {performance['latency_analysis']}")

    return performance['lag_sla_met']


async def test_websocket_connection_basic():
    """Basic test to verify WebSocket server is running"""
    print("🔗 Testing basic WebSocket connection...")

    try:
        async with websockets.connect("ws://localhost:8766") as websocket:
            print("✅ Successfully connected to WebSocket server")

            # Wait for a few messages
            message_count = 0
            try:
                for _ in range(5):
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    message_count += 1
                    print(f"📥 Received message {message_count}")

                    # Try to parse as JSON
                    try:
                        data = json.loads(message)
                        print(f"   📊 Metric keys: {list(data.keys())}")
                    except json.JSONDecodeError:
                        print(f"   📄 Raw message: {message[:100]}...")

            except asyncio.TimeoutError:
                print(f"⏱️  Timeout waiting for messages (received {message_count})")

            print(f"✅ Basic connection test completed. Received {message_count} messages")
            return True

    except Exception as e:
        print(f"❌ Failed to connect to WebSocket server: {e}")
        print("💡 Make sure the metrics collector is running with WebSocket enabled")
        return False


if __name__ == "__main__":
    async def main():
        print("🧪 WebSocket Metrics Client Test\n")

        # Test basic connection first
        basic_ok = await test_websocket_connection_basic()

        if basic_ok:
            print("\n" + "="*50)
            # Test performance if basic connection works
            lag_ok = await test_websocket_lag_performance()

            print("\n🏁 Test Summary:")
            print(f"Basic connection: {'✅ PASSED' if basic_ok else '❌ FAILED'}")
            print(f"Lag performance: {'✅ PASSED' if lag_ok else '❌ FAILED'}")
        else:
            print("\n❌ Skipping performance test due to connection failure")

    asyncio.run(main())
