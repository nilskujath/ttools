import abc
import threading
import uuid
import pandas as pd
from ttools.ontology.event_messages import (
    GLOBAL_STOP_EVENT,
    OrderEventMessage,
    MarketOrderEventMessage,
    LimitOrderEventMessage,
    StopOrderEventMessage,
    IncomingBarEventMessage,
    TradeEventMessage,
)
from ttools.ontology.enum_defs import DecisionType, TradeDirection, OrderType
from ttools.ontology.global_queues import (
    incoming_bar_event_message_queue,
    trade_event_message_queue,
)
from ttools.logging_config import logger


class StrategiesABC(abc.ABC):

    def __init__(self) -> None:
        self._instance_stop_event: threading.Event = threading.Event()

        self._pending_market_orders: dict[uuid.UUID, MarketOrderEventMessage] = {}
        self._pending_limit_orders: dict[uuid.UUID, LimitOrderEventMessage] = {}
        self._pending_stop_orders: dict[uuid.UUID, StopOrderEventMessage] = {}

    def submit_order(self, order: OrderEventMessage) -> None:
        if order.order_type == OrderType.MARKET:
            self._pending_market_orders[order.order_id] = order
            logger.info(f"Submitted market order {order.order_id}")
        elif order.order_type == OrderType.LIMIT:
            self._pending_limit_orders[order.order_id] = order
            logger.info(f"Submitted limit order {order.order_id}")
        elif order.order_type == OrderType.STOP:
            self._pending_stop_orders[order.order_id] = order
            logger.info(f"Submitted stop order {order.order_id}")
        else:
            logger.error(f"Unknown order type: {order.order_type}")

    def _fill_orders(self, new_bar_event_message: IncomingBarEventMessage):
        new_bar_event_message = new_bar_event_message
        for market_order in list(self._pending_market_orders.keys()):
            order_to_execute: MarketOrderEventMessage = self._pending_market_orders[
                market_order
            ]
            executed_order: TradeEventMessage = TradeEventMessage(
                ts_event=new_bar_event_message.ts_event,
                trade_id=uuid.uuid4(),
                assoc_order_id=order_to_execute.order_id,
                trade_direction=order_to_execute.trade_direction,
                quantity=order_to_execute.quantity,
                fill_price=new_bar_event_message.ohlcv.open,
                assoc_decision_type=order_to_execute.decision_type,
            )
            trade_event_message_queue.put(executed_order)
            logger.info(f"Filled order: {executed_order}")
            del self._pending_market_orders[market_order]

        for limit_order in list(self._pending_limit_orders.keys()):
            order_to_execute: LimitOrderEventMessage = self._pending_limit_orders[
                limit_order
            ]
            if (order_to_execute.trade_direction == TradeDirection.BUY) and (
                order_to_execute.limit_price >= new_bar_event_message.ohlcv.low
            ):
                executed_order: TradeEventMessage = TradeEventMessage(
                    ts_event=new_bar_event_message.ts_event,
                    trade_id=uuid.uuid4(),
                    assoc_order_id=order_to_execute.order_id,
                    trade_direction=order_to_execute.trade_direction,
                    quantity=order_to_execute.quantity,
                    fill_price=order_to_execute.limit_price,
                    assoc_decision_type=order_to_execute.decision_type,
                )
                trade_event_message_queue.put(executed_order)
                logger.info(f"Filled order: {executed_order}")
                del self._pending_limit_orders[limit_order]
            elif (order_to_execute.trade_direction == TradeDirection.SELL) and (
                order_to_execute.limit_price <= new_bar_event_message.ohlcv.high
            ):
                executed_order: TradeEventMessage = TradeEventMessage(
                    ts_event=new_bar_event_message.ts_event,
                    trade_id=uuid.uuid4(),
                    assoc_order_id=order_to_execute.order_id,
                    trade_direction=order_to_execute.trade_direction,
                    quantity=order_to_execute.quantity,
                    fill_price=order_to_execute.limit_price,
                    assoc_decision_type=order_to_execute.decision_type,
                )
                trade_event_message_queue.put(executed_order)
                logger.info(f"Filled order: {executed_order}")
                del self._pending_limit_orders[limit_order]

        for stop_order in list(self._pending_stop_orders.keys()):
            order_to_execute: StopOrderEventMessage = self._pending_stop_orders[
                stop_order
            ]
            if (order_to_execute.trade_direction == TradeDirection.BUY) and (
                new_bar_event_message.ohlcv.high >= order_to_execute.stop_price
            ):
                executed_order: TradeEventMessage = TradeEventMessage(
                    ts_event=new_bar_event_message.ts_event,
                    trade_id=uuid.uuid4(),
                    assoc_order_id=order_to_execute.order_id,
                    trade_direction=order_to_execute.trade_direction,
                    quantity=order_to_execute.quantity,
                    fill_price=max(
                        order_to_execute.stop_price, new_bar_event_message.ohlcv.open
                    ),
                    assoc_decision_type=order_to_execute.decision_type,
                )
                trade_event_message_queue.put(executed_order)
                logger.info(f"Filled order: {executed_order}")
                del self._pending_stop_orders[stop_order]
            elif (order_to_execute.trade_direction == TradeDirection.SELL) and (
                new_bar_event_message.ohlcv.low <= order_to_execute.stop_price
            ):
                executed_order: TradeEventMessage = TradeEventMessage(
                    ts_event=new_bar_event_message.ts_event,
                    trade_id=uuid.uuid4(),
                    assoc_order_id=order_to_execute.order_id,
                    trade_direction=order_to_execute.trade_direction,
                    quantity=order_to_execute.quantity,
                    fill_price=min(
                        order_to_execute.stop_price, new_bar_event_message.ohlcv.open
                    ),
                    assoc_decision_type=order_to_execute.decision_type,
                )
                trade_event_message_queue.put(executed_order)
                logger.info(f"Filled order: {executed_order}")
                del self._pending_stop_orders[stop_order]

    @abc.abstractmethod
    def on_bar(self, new_bar_event_message: IncomingBarEventMessage):
        pass

    def _run_strategy(self):
        while not (GLOBAL_STOP_EVENT.is_set() or self._instance_stop_event.is_set()):
            try:
                new_bar_event_message = incoming_bar_event_message_queue.get()
                logger.info(
                    f"Received new bar event message: {new_bar_event_message.ohlcv}"
                )

                self._fill_orders(new_bar_event_message)
                self.on_bar(new_bar_event_message)
            except Exception as e:
                logger.error(f"Error while receiving incoming bar event message: {e}")

    def run_strategy(self):
        self.strategy_thread = threading.Thread(
            target=self._run_strategy,
            name="StrategyThread",
        )
        self.strategy_thread.start()


class Strategy1(StrategiesABC):

    def __init__(self):
        super().__init__()

    def on_bar(self, new_bar_event_message: IncomingBarEventMessage):
        if new_bar_event_message.ohlcv.open < new_bar_event_message.ohlcv.close:
            self.submit_order(
                MarketOrderEventMessage(
                    ts_event=new_bar_event_message.ts_event,
                    order_id=uuid.uuid4(),
                    trade_direction=TradeDirection.SELL,
                    quantity=1,
                    decision_type=DecisionType.SHORT_ENTRY,
                )
            )
