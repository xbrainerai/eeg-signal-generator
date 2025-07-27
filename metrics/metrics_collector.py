from datetime import datetime
from time import time
from metrics.metric import Metric
from metrics.metric_output import MetricOutput
from metrics.metric_logger_output import MetricLoggerOutput
from metrics.logger_file import MetricLoggerFile


class MetricsCollector:

    def __init__(self):
        self.current_metric: Metric = Metric()
        self.dropped_packet_count: int = 0
        self.outputs: list[MetricOutput] = [MetricLoggerOutput(), MetricLoggerFile()]
        # self.outputs: list[MetricOutput] = [MetricLoggerOutput()]
        # self.outputs = [MetricLoggerFile()]

    def stage_buffer_fill(self, buffer_fill_pct: float):
        self.current_metric.buf = buffer_fill_pct

    def stage_end_to_end_latency(self, frame_timestamp_ms: float):
        if self.current_metric is None:
            raise RuntimeError("MetricsCollector.stage_end_to_end_latency() called without a current metric")

        self.current_metric.lat = frame_timestamp_ms


    def inc_dropped_packet_count(self):
        if self.current_metric is None:
            raise RuntimeError("MetricsCollector.stage_inc_dropped_packet_count_inc() called without a current metric")

        self.dropped_packet_count += 1

    def stage_anomoly_detection(self):
        if self.current_metric is None:
            raise RuntimeError("MetricsCollector.stage_anomoly_detection() called without a current metric")

        self.current_metric.anomaly = True

    def get_current_metric(self) -> Metric:
        current_metric = self.current_metric
        self.current_metric = Metric()

        return current_metric

    def output_current_metric(self):
        if self.current_metric.buf is None or self.current_metric.lat is None or self.current_metric.drop is None or self.current_metric.anomaly is None:
            raise RuntimeError("Current metric is not fully defined")

        self.current_metric.ts = datetime.now()
        self.current_metric.drop = self.dropped_packet_count

        for output in self.outputs:
            output.output(self.current_metric)

        self.current_metric = Metric()
