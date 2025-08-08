#!/usr/bin/env python3
"""
24-hour log sample generator for metric logging system.
Simulates continuous operation to test log rotation and stability.
"""

import asyncio
import time
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
import json
import random

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from metrics.metrics_collector import MetricsCollector
from metrics.main_ingest import MainIngest
from metrics.metric import Metric


class LogSampleGenerator:
    """Generates realistic metric samples for 24-hour testing"""

    def __init__(self):
        self.running = True
        self.metrics_generated = 0
        self.start_time = time.time()
        self.main_ingest = MainIngest()

        # Realistic metric patterns
        self.base_buffer_pct = 45.0
        self.base_latency_ms = 0.25
        self.anomaly_rate = 0.02  # 2% anomaly rate

    def generate_realistic_metric(self, stream_id: int = 1) -> Metric:
        """Generate a realistic metric with natural variations"""
        metric = Metric()

        # Basic info
        metric.stream_id = stream_id
        metric.ts = datetime.now()
        metric.total = self.metrics_generated

        # Buffer percentage with realistic fluctuations
        # Simulate buffer filling and emptying cycles
        cycle_time = time.time() % 60  # 60-second cycles
        buffer_variation = 20 * (0.5 + 0.5 * (cycle_time / 60))
        metric.buf = max(0, min(100, self.base_buffer_pct + buffer_variation + random.gauss(0, 5)))

        # Latency with occasional spikes
        if random.random() < 0.05:  # 5% chance of latency spike
            metric.lat = self.base_latency_ms + random.uniform(2, 10)
        else:
            metric.lat = max(0, self.base_latency_ms + random.gauss(0, 0.1))

        # Dropped packets (accumulates over time)
        if random.random() < 0.001:  # 0.1% packet drop rate
            self.dropped_packet_count = getattr(self, 'dropped_packet_count', 0) + 1
        metric.drop = getattr(self, 'dropped_packet_count', 0)

        # Anomalies (high latency, buffer overflow, validation failures)
        metric.anomaly = (
            metric.lat > 0.5 or  # High latency anomaly
            metric.buf > 95 or   # Buffer overflow anomaly
            random.random() < self.anomaly_rate  # Random anomalies
        )

        return metric

    async def generate_continuous_metrics(self, target_fps: int = 256):
        """Generate metrics continuously at target frequency"""
        interval = 1.0 / target_fps

        print(f"🚀 Starting 24-hour metric generation at {target_fps} FPS")
        print(f"Target interval: {interval*1000:.2f}ms per metric")

        next_metric_time = time.time()

        while self.running:
            current_time = time.time()

            if current_time >= next_metric_time:
                # Generate and queue metric
                metric = self.generate_realistic_metric()
                self.main_ingest.add_to_stream_adapter_metrics_processing_queue(metric)

                self.metrics_generated += 1
                next_metric_time += interval

                # Progress reporting
                if self.metrics_generated % 10000 == 0:
                    elapsed_hours = (current_time - self.start_time) / 3600
                    rate = self.metrics_generated / (current_time - self.start_time)
                    print(f"📊 Generated {self.metrics_generated:,} metrics in {elapsed_hours:.2f}h (rate: {rate:.1f}/s)")

            # Small sleep to prevent busy waiting
            await asyncio.sleep(max(0.001, next_metric_time - current_time))

    def stop(self):
        """Stop the generator"""
        self.running = False


class MonitoringReporter:
    """Reports system health during 24-hour test"""

    def __init__(self):
        self.start_time = time.time()
        self.log_file_sizes = {}

    async def monitor_system_health(self, interval_minutes: int = 30):
        """Monitor system health and report periodically"""
        while True:
            await asyncio.sleep(interval_minutes * 60)

            if not hasattr(self, 'generator') or not self.generator.running:
                break

            self.report_health()

    def report_health(self):
        """Generate health report"""
        current_time = time.time()
        elapsed_hours = (current_time - self.start_time) / 3600

        print(f"\n🏥 HEALTH REPORT - {elapsed_hours:.2f} hours elapsed")
        print(f"{'='*50}")

        # Check log files
        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("adapter_metrics.log*"))
            print(f"📁 Log files: {len(log_files)}")

            total_size = 0
            for log_file in log_files:
                size = log_file.stat().st_size if log_file.exists() else 0
                total_size += size
                print(f"   {log_file.name}: {size:,} bytes")

            print(f"📏 Total log size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")

        # Memory usage (basic)
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
            print(f"💾 Memory usage: {memory_mb:.1f} MB")
            print(f"🖥️  CPU usage: {cpu_percent:.1f}%")
        except ImportError:
            print("💾 Memory monitoring requires psutil package")

        # Queue status
        if hasattr(self, 'generator'):
            print(f"📈 Metrics generated: {self.generator.metrics_generated:,}")
            rate = self.generator.metrics_generated / (current_time - self.start_time)
            print(f"📊 Generation rate: {rate:.1f} metrics/second")

        print(f"{'='*50}\n")


async def run_24_hour_test():
    """Run the complete 24-hour test"""
    print("🕐 Starting 24-Hour Metric Logging Test")
    print("This will generate realistic metrics continuously for 24 hours")
    print("Press Ctrl+C to stop early\n")

    # Initialize components
    generator = LogSampleGenerator()
    reporter = MonitoringReporter()
    reporter.generator = generator

    # Start metrics collector
    metrics_collector = MetricsCollector()

    # Set up signal handler for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        generator.stop()
        metrics_collector.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Start all tasks
        tasks = [
            asyncio.create_task(generator.generate_continuous_metrics()),
            asyncio.create_task(metrics_collector.collect_metrics()),
            asyncio.create_task(reporter.monitor_system_health())
        ]

        # Calculate 24-hour end time
        end_time = time.time() + (24 * 60 * 60)

        print(f"⏰ Test will run until {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}")

        # Wait for completion or 24 hours
        while time.time() < end_time and generator.running:
            await asyncio.sleep(10)

        print("✅ 24-hour test completed successfully!")

    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
    finally:
        # Cleanup
        generator.stop()
        metrics_collector.stop()

        # Cancel tasks
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Final report
        elapsed = time.time() - generator.start_time
        print(f"\n📊 FINAL SUMMARY:")
        print(f"Test duration: {elapsed/3600:.2f} hours")
        print(f"Metrics generated: {generator.metrics_generated:,}")
        print(f"Average rate: {generator.metrics_generated/elapsed:.1f} metrics/second")

        # Check log files one final time
        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("adapter_metrics.log*"))
            print(f"Final log files: {len(log_files)}")

            if log_files:
                print("📁 Log file summary:")
                for log_file in sorted(log_files):
                    size = log_file.stat().st_size if log_file.exists() else 0
                    print(f"   {log_file.name}: {size:,} bytes")


if __name__ == "__main__":
    # Check if this is meant to be a short test
    if len(sys.argv) > 1 and sys.argv[1] == "--short":
        print("🚀 Running 5-minute test instead of 24 hours...")

        async def short_test():
            generator = LogSampleGenerator()
            metrics_collector = MetricsCollector()

            tasks = [
                asyncio.create_task(generator.generate_continuous_metrics()),
                asyncio.create_task(metrics_collector.collect_metrics())
            ]

            # Run for 5 minutes
            await asyncio.sleep(300)

            generator.stop()
            metrics_collector.stop()

            for task in tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            print(f"✅ Short test completed. Generated {generator.metrics_generated} metrics")

        asyncio.run(short_test())
    else:
        asyncio.run(run_24_hour_test())
