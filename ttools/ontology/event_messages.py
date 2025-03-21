import dataclasses
import uuid

from ttools.ontology.enum_defs import Rtype, TradeDirection, OrderType, DecisionType
import threading
import pandas as pd
import collections


GLOBAL_STOP_EVENT = threading.Event()

OHLCV = collections.namedtuple("OHLCV", ["open", "high", "low", "close", "volume"])


@dataclasses.dataclass(frozen=True)
class IncomingBarEventMessage:
    ts_event: pd.Timestamp
    rtype: Rtype
    symbol: str
    ohlcv: OHLCV

    def __str__(self) -> str:
        ohlcv_str = (
            f"open={self.ohlcv.open}, high={self.ohlcv.high}, "
            f"low={self.ohlcv.low}, close={self.ohlcv.close}, volume={self.ohlcv.volume}"
        )
        return (
            f"IncomingBarEventMessage({self.ts_event}, {self.symbol}, {self.rtype}, "
            f"ohlcv=({ohlcv_str}))"
        )


@dataclasses.dataclass(frozen=True)
class ProcessedBarEventMessage:
    ts_event: pd.Timestamp
    rtype: Rtype
    symbol: str
    ohlcv: OHLCV
    indicator_values: dict
    # bar_performance_metrics: dict

    def __str__(self) -> str:
        ohlcv_str = (
            f"open={self.ohlcv.open}, high={self.ohlcv.high}, "
            f"low={self.ohlcv.low}, close={self.ohlcv.close}, volume={self.ohlcv.volume}"
        )
        indicators_str = ", ".join(
            f"{k}: {v}" for k, v in self.indicator_values.items()
        )
        return (
            f"ProcessedBarEventMessage({self.ts_event}, {self.symbol}, "
            f"ohlcv=({ohlcv_str}), indicators={indicators_str})"
        )


@dataclasses.dataclass(frozen=True)
class OrderEventMessage:
    ts_event: pd.Timestamp
    order_id: uuid.UUID
    trade_direction: TradeDirection
    quantity: int
    decision_type: DecisionType
    order_type: OrderType


@dataclasses.dataclass(frozen=True)
class MarketOrderEventMessage(OrderEventMessage):
    order_type: OrderType = dataclasses.field(default=OrderType.MARKET, init=False)


@dataclasses.dataclass(frozen=True)
class LimitOrderEventMessage(OrderEventMessage):
    limit_price: float
    order_type: OrderType = dataclasses.field(default=OrderType.LIMIT, init=False)


@dataclasses.dataclass(frozen=True)
class StopOrderEventMessage(OrderEventMessage):
    stop_price: float
    order_type: OrderType = dataclasses.field(default=OrderType.STOP, init=False)


@dataclasses.dataclass(frozen=True)
class TradeEventMessage:
    ts_event: pd.Timestamp
    trade_id: uuid.UUID
    assoc_order_id: uuid.UUID
    trade_direction: TradeDirection
    quantity: int
    fill_price: float
    assoc_decision_type: DecisionType
