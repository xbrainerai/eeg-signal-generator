from datetime import datetime
from metrics.metric_output import MetricOutput
from metrics.metric import Metric


class MetricLoggerOutput(MetricOutput):
    def __init__(self):
        pass

    def output(self, metric: Metric):
        print(metric.to_string())
