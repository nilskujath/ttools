from ttools.datafeeds.abc_datafeeds import DatafeedsABC
import pandas as pd
from ttools.ontology.event_messages import (
    GLOBAL_STOP_EVENT,
    IncomingBarEventMessage,
    OHLCV,
)
from ttools.ontology.enum_defs import Rtype
from ttools.ontology.global_queues import incoming_bar_event_message_queue
from ttools.logging_config import logger
import threading


class CSVDatafeed(DatafeedsABC):

    def __init__(self, path_to_csv_file: str):
        super().__init__()
        self.path_to_csv_file = path_to_csv_file
        self.data_iterator = pd.read_csv(
            self.path_to_csv_file,
            usecols=[
                "ts_event",
                "rtype",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "symbol",
            ],
            dtype={
                "ts_event": int,
                "rtype": int,
                "open": int,
                "high": int,
                "low": int,
                "close": int,
                "volume": int,
                "symbol": str,
            },
            iterator=True,
            chunksize=1,
        )

    def _get_next_bar_event_message(self) -> IncomingBarEventMessage | None:
        if GLOBAL_STOP_EVENT.is_set() or self._instance_stop_event.is_set():
            return None
        try:
            csv_row = next(self.data_iterator).iloc[0]
            return IncomingBarEventMessage(
                symbol=csv_row["symbol"],
                rtype=Rtype(int(csv_row["rtype"])),
                ts_event=pd.to_datetime(int(csv_row["ts_event"]), unit="ns"),
                ohlcv=OHLCV(
                    csv_row["open"] / 1e9,
                    csv_row["high"] / 1e9,
                    csv_row["low"] / 1e9,
                    csv_row["close"] / 1e9,
                    int(csv_row["volume"]),
                ),
            )
        except StopIteration:
            logger.info("End of CSV replay data reached")
            return None
        except Exception as e:
            logger.error(f"Error reading next bar: {e}", exc_info=False)
            return None

    def connect(self):
        self.enqueue_incoming_bar_event_messages_thread = threading.Thread(
            target=self._enqueue_incoming_bar_event_messages,
            name="CSVDatafeed",
        )
        self.enqueue_incoming_bar_event_messages_thread.start()

    def _enqueue_incoming_bar_event_messages(self):
        while not (GLOBAL_STOP_EVENT.is_set() or self._instance_stop_event.is_set()):
            try:
                incoming_bar_event_message = self._get_next_bar_event_message()
                if incoming_bar_event_message is None:
                    break
                incoming_bar_event_message_queue.put(incoming_bar_event_message)
                logger.debug(
                    f"Enqueued "
                    f"{incoming_bar_event_message} | Queue size: "
                    f"{incoming_bar_event_message_queue.qsize()}"
                )
            except Exception as e:
                logger.error(f"Error enqueuing bar event: {e}", exc_info=False)
        if GLOBAL_STOP_EVENT.is_set():
            logger.info(f"GLOBAL_STOP_EVENT detected.")
            self._instance_stop_event.set()

    def disconnect(self):
        self._instance_stop_event.set()
        if (
            self.enqueue_incoming_bar_event_messages_thread
            and self.enqueue_incoming_bar_event_messages_thread.is_alive()
        ):
            thread_name = self.enqueue_incoming_bar_event_messages_thread.name
            logger.debug(f"Stopping {thread_name}...")
            self.enqueue_incoming_bar_event_messages_thread.join()
            logger.debug(f"{thread_name} stopped.")
