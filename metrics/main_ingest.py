# Class for ingesting metrics from the main application
from asyncio import Lock
import asyncio
import threading
import time
from typing import List
from metrics.metric import Metric


class MainIngest:
    _instance = None
    stream_adapter_metrics_processing_queue: List[Metric]
    lock: threading.Lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MainIngest, cls).__new__(cls)
            cls._instance.stream_adapter_metrics_processing_queue = []
        return cls._instance

    def add_to_stream_adapter_metrics_processing_queue(self, metric: Metric) -> None:
        with self.lock:
            self.stream_adapter_metrics_processing_queue.append(metric)

    async def process_and_next_metric(self) -> Metric:
        while True:
            with self.lock:
                if len(self.stream_adapter_metrics_processing_queue) > 0:
                    return self.stream_adapter_metrics_processing_queue.pop(0)
            await asyncio.sleep(0.01)

    def has_next_metric_to_process(self):
        return len(self.stream_adapter_metrics_processing_queue) > 0
