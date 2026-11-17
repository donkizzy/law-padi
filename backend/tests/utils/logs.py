import logging
from collections.abc import Iterator
from contextlib import contextmanager

from app.core.logs import ContextFilter


class _Collector(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        # Filters run as each record is emitted, while its context is bound.
        self.addFilter(ContextFilter())

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextmanager
def captured_logs(name: str = "") -> Iterator[list[logging.LogRecord]]:
    """Collect records under `name` with request, run and task ids applied."""
    logger = logging.getLogger(name)
    collector = _Collector()
    level = logger.level
    logger.addHandler(collector)
    logger.setLevel(logging.DEBUG)
    try:
        yield collector.records
    finally:
        logger.removeHandler(collector)
        logger.setLevel(level)
