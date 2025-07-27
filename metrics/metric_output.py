from abc import ABC, abstractmethod
from metrics.metric import Metric


class MetricOutput(ABC):
    def __init__(self):
        pass

    @abstractmethod
    def output(self, metric: Metric):
        pass
