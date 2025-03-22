from ttools.indicators import ABCIndicator
import numpy as np
import collections


class SimpleMovingAverage(ABCIndicator):
    def __init__(
        self, period: int, applied_on: str | None = None, max_history: int = 1000
    ):
        super().__init__(max_history)
        self.period = period
        self.applied_on = applied_on or "N/A"
        self.values = collections.deque([np.nan] * period, maxlen=period)

    @property
    def name(self) -> str:
        return f"SMA_{self.period}_{self.applied_on}"

    def _compute_indicator(self, value):
        self.values.append(value)
        if np.isnan(self.values[0]):
            return np.nan
        return np.mean(self.values)
