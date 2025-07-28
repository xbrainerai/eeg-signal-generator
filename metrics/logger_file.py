import logging
from datetime import datetime
from metrics.metric import Metric
from metrics.metric_output import MetricOutput
from logging.handlers import RotatingFileHandler

class MetricLoggerFile(MetricOutput):
    def __init__(self, log_file_name: str, log_file_max_size: int, log_file_max_count: int):
        if log_file_name is None or log_file_max_size is None or log_file_max_count is None:
            raise ValueError("log_file_name, log_file_max_size, and log_file_max_count must be provided")

        # Use a unique logger name to avoid conflicts
        self.logger = logging.getLogger(f'MetricLoggerFile_{id(self)}')
        self.logger.setLevel(logging.INFO)

        # Disable propagation to prevent duplicate logging
        self.logger.propagate = False

        # Clear any existing handlers to avoid duplicates
        self.logger.handlers.clear()

        handler = RotatingFileHandler(log_file_name, maxBytes=log_file_max_size, backupCount=log_file_max_count)
        self.logger.addHandler(handler)

    def output(self, metric: Metric):
        self.logger.info(metric.to_string())
