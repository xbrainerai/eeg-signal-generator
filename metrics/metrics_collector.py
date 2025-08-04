from datetime import datetime
import json
import asyncio
from time import time
from metrics.metric import Metric
from metrics.metric_output import MetricOutput
from metrics.metric_logger_output import MetricLoggerOutput
from metrics.logger_file import MetricLoggerFile
from metrics.main_ingest import MainIngest

class MetricsCollector:

    def __init__(self):
        self.main_ingest = MainIngest()
        # self.outputs: list[MetricOutput] = [MetricLoggerOutput(), MetricLoggerFile()]
        log_config = json.load(open('metrics/logger_config.json'))
        self.outputs: list[MetricOutput] = []
        if log_config['log_to_console']:
            self.outputs.append(MetricLoggerOutput())
        if log_config['log_file_configuration']:
            self.outputs.append(MetricLoggerFile(log_config['log_file_configuration']['log_file_name'], log_config['log_file_configuration']['log_file_max_size'], log_config['log_file_configuration']['log_file_max_count']))
        self._running = True

    def stop(self):
        """Stop the metrics collector"""
        self._running = False

    async def collect_metrics(self):
        while self._running:
            try:
                metric = await self.main_ingest.process_and_next_metric()
                for output in self.outputs:
                    output.output(metric)
            except asyncio.CancelledError:
                print("Metrics collector cancelled")
                break
            except Exception as e:
                print(f"Error collecting metrics: {e}")
                await asyncio.sleep(1)
