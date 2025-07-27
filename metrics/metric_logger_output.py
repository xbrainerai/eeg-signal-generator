from datetime import datetime
from metrics.metric_output import MetricOutput
from metrics.metric import Metric


class MetricLoggerOutput(MetricOutput):
    def __init__(self):
        pass

    def output(self, metric: Metric):
        if metric.ts is None or metric.buf is None or metric.lat is None or metric.drop is None or metric.anomaly is None:
            raise ValueError("Metric is missing required fields")

        print(metric.to_string())
