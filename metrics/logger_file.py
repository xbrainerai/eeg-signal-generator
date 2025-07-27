import logging
from datetime import datetime
from metrics.metric import Metric
from metrics.metric_output import MetricOutput
from logging.handlers import RotatingFileHandler

class MetricLoggerFile(MetricOutput):
    def __init__(self):
        #logging.basicConfig(filename='metrics.log', level=logging.INFO)
        self.root_logger = logging.getLogger('Rotating Log')
        self.root_logger.setLevel(logging.INFO)
        handler = RotatingFileHandler('test_metric.log', maxBytes=10000000, backupCount=7)
        self.root_logger.addHandler(handler)

    def output(self, metric: Metric):
        if metric.ts is None or metric.buf is None or metric.lat is None or metric.drop is None or metric.anomaly is None:
            raise ValueError("Metric is missing required fields for output")

        try:
            self.root_logger.info(metric.to_string())
        except Exception as e:
            print(f"Error logging metric: {e}")
