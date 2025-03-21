import enum


class Rtype(enum.Enum):
    OHLCV_1S = 32


class OrderType(enum.Enum):
    MARKET = enum.auto()
    LIMIT = enum.auto()
    STOP = enum.auto()


class TradeDirection(enum.Enum):
    BUY = enum.auto()
    SELL = enum.auto()


class DecisionType(enum.Enum):
    SHORT_ENTRY = enum.auto()
    SHORT_ADD = enum.auto()
    SHORT_FULL_COVER = enum.auto()
