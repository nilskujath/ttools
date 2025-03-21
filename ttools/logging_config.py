import logging
import logging.handlers
import queue

log_queue = queue.Queue(maxsize=10000)
queue_handler = logging.handlers.QueueHandler(log_queue)
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(queue_handler)
stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(threadName)s - %(message)s"
)
stream_handler.setFormatter(formatter)
listener = logging.handlers.QueueListener(log_queue, stream_handler)
listener.start()
logger = logging.getLogger(__name__)
