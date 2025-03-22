import abc
import collections
import numpy as np
from ttools.logging_config import logger


class ABCIndicator(abc.ABC):
    def __init__(self, max_history: int = 6) -> None:
        self._max_history = max_history
        self._history = collections.deque([np.nan] * max_history, maxlen=max_history)
        self._current = np.nan

    @property
    @abc.abstractmethod
    def name(self) -> str:
        pass

    @abc.abstractmethod
    def _compute_indicator(self, *args, **kwargs):
        """
        Computes the indicator based on either a single value or multiple values
        (dictionary). This method must be implemented by subclasses.
        """
        pass

    def update(self, value):
        """
        Updates the indicator with either a single value or multiple values
        (dictionary) by calling self._compute_indicator(), which must be implemented
        by subclasses of ABCIndicator.
        """
        if isinstance(value, (float, int)):
            if np.isnan(value):
                return
            new_value = self._compute_indicator(value)
        elif isinstance(value, dict):
            new_value = self._compute_indicator(**value)
        else:
            logger.error(f"Unexpected type for value: {type(value)} | Value: {value}")
            return

        self._history.append(self._current)
        self._current = new_value

    def __getitem__(self, index: int):
        if index == 0:
            return self._current
        elif index < 0:
            try:
                return self._history[index]
            except IndexError:
                logger.warning(f"Requested history index {index} is out of bounds.")
                return np.nan
        else:
            raise IndexError(
                f"Only index 0 (current value) and negative indices (historical "
                f"values) are supported."
            )
