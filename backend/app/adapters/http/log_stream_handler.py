"""Python logging.Handler that publishes records to the SSE log stream bus.

Attached to the root logger at startup so all loggers feed into it.
"""

from __future__ import annotations

import datetime
import logging

from .log_stream_bus import log_stream_bus


class LogStreamHandler(logging.Handler):
    """Forwards log records to all connected SSE /api/logs/stream clients."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if record.exc_info and not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                msg = f"{msg}\n{record.exc_text}"
            log_stream_bus.publish({
                "ts": datetime.datetime.fromtimestamp(
                    record.created, tz=datetime.timezone.utc
                ).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "levelno": record.levelno,
                "name": record.name,
                "msg": msg,
            })
        except Exception:
            self.handleError(record)
