from ttools.indicators import ABCIndicator
import numpy as np
import collections


class BollingerUpperBand(ABCIndicator):
    def __init__(self, period: int, multiplier: float = 2.0, max_history: int = 1000):
        super().__init__(max_history)
        self.period = period
        self.multiplier = multiplier
        self.values = collections.deque(maxlen=period)

    @property
    def name(self) -> str:
        return (
            f"BollingerUpperBand (Period: {self.period}, Multiplier: {self.multiplier})"
        )

    def _compute_indicator(self, value):
        self.values.append(value)

        if len(self.values) < self.period:
            return np.nan

        sma = np.mean(self.values)
        std_dev = np.std(self.values, ddof=0)  # Population standard deviation

        return sma + (self.multiplier * std_dev)
