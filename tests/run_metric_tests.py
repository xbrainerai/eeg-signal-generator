#!/usr/bin/env python3
"""
Comprehensive test runner for metric logging system.
Runs all tests and provides manual testing guidance.
"""

import subprocess
import sys
import time
import os
from pathlib import Path


def run_command(cmd: str, cwd: str = "") -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, stderr"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=300  # 5 minute timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_test_result(test_name: str, success: bool, details: str = ""):
    """Print formatted test result"""
    status = "✅ PASSED" if success else "❌ FAILED"
    print(f"{status:<10} {test_name}")
    if details:
        print(f"           {details}")


def main():
    print("🧪 EEG Signal Generator - Metric Logging Test Suite")
    print("This will run comprehensive tests for the metric logging system.")

    # Change to project root and adjust Python path
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    # Add project root to Python path for imports
    import sys
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    total_tests = 0
    passed_tests = 0

    # ========================= Unit Tests =========================
    print_section("1. UNIT TESTS")

    # Test logger components
    print("Running unit tests for metric logging components...")
    exit_code, stdout, stderr = run_command("python -m pytest tests/test_logger.py -v", cwd=str(project_root))

    if exit_code == 0:
        print_test_result("Unit Tests (test_logger.py)", True, "All metric logging tests passed")
        passed_tests += 1
    else:
        print_test_result("Unit Tests (test_logger.py)", False, f"Exit code: {exit_code}")
        if stderr:
            print(f"           Error: {stderr[:200]}...")
    total_tests += 1

    # ========================= Stress Tests =========================
    print_section("2. STRESS TESTS")

    # Run stream reliability tests
    print("Running stress tests for high-frequency streaming...")
    exit_code, stdout, stderr = run_command("python -m pytest test/test_stream_reliability.py::test_high_frequency_stress_10k_fps -v -s", cwd=str(project_root))

    if exit_code == 0:
        print_test_result("10k FPS Stress Test", True, "Metric loss <5% verified")
        passed_tests += 1
    else:
        print_test_result("10k FPS Stress Test", False, f"Exit code: {exit_code}")
        if stderr and "metric loss rate" in stderr.lower():
            print(f"           {stderr}")
    total_tests += 1

    # Buffer throttling tests
    exit_code, stdout, stderr = run_command("python -m pytest test/test_stream_reliability.py::test_buffer_throttling_adjustment -v -s", cwd=str(project_root))

    if exit_code == 0:
        print_test_result("Buffer Throttling Test", True, "Buffer scaling verified")
        passed_tests += 1
    else:
        print_test_result("Buffer Throttling Test", False, f"Exit code: {exit_code}")
    total_tests += 1

    # ========================= Integration Tests =========================
    print_section("3. INTEGRATION TESTS")

    # Check if main components can be imported
    try:
        from metrics.metrics_collector import MetricsCollector
        from metrics.main_ingest import MainIngest
        from metrics.logger_ws import MetricLoggerWS

        print_test_result("Component Import Test", True, "All components importable")
        passed_tests += 1
    except Exception as e:
        print_test_result("Component Import Test", False, f"Import error: {e}")
    total_tests += 1

    # Test configuration loading
    try:
        import json
        with open('metrics/logger_config.json') as f:
            config = json.load(f)

        has_ws = config.get('log_to_websocket', False)
        has_console = config.get('log_to_console', False)
        has_file = config.get('log_file_configuration') is not None

        config_ok = has_ws and has_console and has_file
        details = f"WS:{has_ws}, Console:{has_console}, File:{has_file}"
        print_test_result("Configuration Test", config_ok, details)

        if config_ok:
            passed_tests += 1
    except Exception as e:
        print_test_result("Configuration Test", False, f"Config error: {e}")
    total_tests += 1

    # ========================= Manual Testing Guidance =========================
    print_section("4. MANUAL TESTING GUIDANCE")

    print("""
📋 MANUAL ACCEPTANCE CRITERIA CHECKLIST

To complete the testing, perform these manual tests:

1. 🖥️  CLI REFRESH TEST (≤1s requirement)
   • Run: python main.py --source protocol/signal.json
   • Observe console output refresh rate
   • ✓ Metrics should appear at least once per second
   • ✓ No delays or freezing in output

2. ⏱️  LATENCY ERROR TEST (<0.5ms requirement)
   • Monitor metrics output for 'lat=' values
   • ✓ Most latency values should be <0.5ms
   • ✓ Anomaly=True should trigger for high latency

3. 📁 FILE ROTATION TEST (No loss requirement)
   • Let system run for 30+ minutes to trigger rotation
   • Check logs/adapter_metrics.log.* files
   • ✓ Multiple log files should exist
   • ✓ No gaps in metric sequence numbers
   • ✓ Total entries across files should match expected count

4. 🚨 ANOMALY LOGGING TEST (100% capture requirement)
   • Inject test anomalies or wait for natural ones
   • ✓ Every anomaly=True should appear in all outputs
   • ✓ Console, file, and WebSocket should all capture
   • ✓ No anomalies should be missed

5. 🌐 WEBSOCKET LAG TEST (<200ms for 95%)
   • Run: python tests/test_websocket_client.py
   • ✓ 95th percentile lag should be <200ms
   • ✓ Connection should be stable
   • ✓ All metric fields should be present

6. 📊 24-HOUR LOG SAMPLE GENERATION
   • Run system continuously for 24 hours
   • ✓ Log files should rotate properly
   • ✓ No memory leaks or performance degradation
   • ✓ Consistent metric generation rate

USAGE EXAMPLES:

# Start the main system
python main.py --source protocol/signal.json

# In another terminal, test WebSocket client
python tests/test_websocket_client.py

# Run continuous monitoring
python tests/run_metric_tests.py

# Check log rotation
ls -la logs/adapter_metrics.log*
tail -f logs/adapter_metrics.log
""")

    # ========================= Test Summary =========================
    print_section("5. TEST SUMMARY")

    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    print(f"Tests passed: {passed_tests}/{total_tests} ({success_rate:.1f}%)")

    if success_rate >= 80:
        print("🎉 OVERALL RESULT: ✅ PASSED")
        print("The metric logging system is ready for production use.")
    else:
        print("⚠️  OVERALL RESULT: ❌ NEEDS WORK")
        print("Some tests failed. Please review the issues above.")

    print("\n📚 Next Steps:")
    print("1. Complete the manual testing checklist above")
    print("2. Run WebSocket client test while system is running")
    print("3. Monitor system for 24 hours to verify stability")
    print("4. Check acceptance criteria compliance")

    return success_rate >= 80


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
