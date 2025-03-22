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
    ProcessedBarEventMessage,
    TradeEventMessage,
)
from ttools.ontology.enum_defs import DecisionType, TradeDirection, OrderType
from ttools.ontology.global_queues import (
    incoming_bar_event_message_queue,
    process_bar_event_message_queue,
    trade_event_message_queue,
)
from ttools.logging_config import logger
from ttools.indicators import SimpleMovingAverage


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

    def _run_strategy(self) -> None:
        while not (GLOBAL_STOP_EVENT.is_set() or self._instance_stop_event.is_set()):
            try:
                new_bar_event_message = (
                    incoming_bar_event_message_queue.get()
                )  # blocking call
                if not isinstance(new_bar_event_message, IncomingBarEventMessage):
                    logger.error("Received non-bar event message from the queue.")
                    continue
                logger.debug(f"Received {new_bar_event_message}")
                self._fill_orders(new_bar_event_message)
                self.on_bar(new_bar_event_message)
            except Exception as e:
                logger.error(f"Error processing bar event message: {e}")

    def run_strategy(self):
        self.strategy_thread = threading.Thread(
            target=self._run_strategy,
            name="StrategyThread",
        )
        self.strategy_thread.start()


class Strategy1(StrategiesABC):

    def __init__(self):
        super().__init__()
        # Step 1: Define indicators that are used in strategy:
        self.sma_fast = SimpleMovingAverage(10, "close")
        self.sma_slow = SimpleMovingAverage(100, "close")

    def on_bar(self, new_bar_event_message: IncomingBarEventMessage):
        # Step 2: At each new bar, update indicators
        self.sma_fast.update(new_bar_event_message.ohlcv.close)
        self.sma_slow.update(new_bar_event_message.ohlcv.close)

        indicator_values: dict[str, float] = {
            f"{self.sma_fast.name}": self.sma_fast[0],
            f"{self.sma_slow.name}": self.sma_slow[0],
        }

        processed_bar_event_message: ProcessedBarEventMessage = (
            ProcessedBarEventMessage(
                ts_event=new_bar_event_message.ts_event,
                rtype=new_bar_event_message.rtype,
                symbol=new_bar_event_message.symbol,
                ohlcv=new_bar_event_message.ohlcv,
                indicator_values=indicator_values,
                # bar_performance_metrics=
            )
        )

        process_bar_event_message_queue.put(processed_bar_event_message)
        logger.info(f"Enqueued {processed_bar_event_message}")

        # Step 3: Define the trading logic
        if self.sma_slow[0] < self.sma_fast[0] < new_bar_event_message.ohlcv.high:
            self.submit_order(
                MarketOrderEventMessage(
                    ts_event=new_bar_event_message.ts_event,
                    order_id=uuid.uuid4(),
                    trade_direction=TradeDirection.SELL,
                    quantity=1,
                    decision_type=DecisionType.SHORT_ENTRY,
                )
            )

    # To work on next time:
    # Fix up the logging everywhere
    # Make the trades queue
    # Make indicators fixed so that plotting can be done automatically. and update is also automatic.
