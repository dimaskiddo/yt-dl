"""Loguru logging setup with stdlib logging interception."""

from __future__ import annotations

import logging
import sys
import warnings
from typing import TYPE_CHECKING

from loguru import logger

from src.core.constants import WORKSPACE_LOGS

if TYPE_CHECKING:
    from loguru import Record as LoguruRecord

    from src.core.config import LoggingConfig


class InterceptHandler(logging.Handler):
    """Intercept standard logging messages and route them to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _pad_source(record: LoguruRecord) -> None:
    """Pad source location to 65 chars for aligned block display."""
    source = f"{record['name']}:{record['function']}:{record['line']}"
    record["extra"]["source_padded"] = source.ljust(65)


def _configure_library_loggers() -> None:
    """Route stdlib logging to loguru and silence noisy third-party loggers."""
    logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO, force=True)

    for name in ("urllib3", "httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.ERROR)

    gradio_logger = logging.getLogger("gradio")
    gradio_logger.handlers.clear()
    gradio_logger.propagate = True
    gradio_logger.setLevel(logging.WARNING)


def _configure_warnings() -> None:
    """Route stdlib warnings into loguru."""

    def _showwarning(
        message: Warning | str,
        category: type[Warning],
        _filename: str,
        _lineno: int,
        _file: object = None,
        _line: str | None = None,
    ) -> None:
        """Route stdlib warnings through loguru."""
        logger.warning(f"{category.__name__}: {message}")

    warnings.showwarning = _showwarning


def _configure_console_sink(level: str) -> None:
    """Add loguru console sink with source-location formatting.

    Args:
        level: Minimum log level for console output.
    """
    fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[source_padded]}</cyan> | "
        "<level>{message}</level>"
    )
    logger.add(sys.stderr, format=fmt, level=level)


def _configure_file_sink(config: LoggingConfig) -> None:
    """Add loguru file sink with rotation and retention.

    Args:
        config: Logging configuration with file path, rotation, retention.
    """
    log_path = WORKSPACE_LOGS / config.log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = (
        "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[source_padded]} | {message}"
    )
    logger.add(
        str(log_path),
        format=fmt,
        level=config.level,
        rotation=config.rotation,
        retention=config.retention,
        encoding="utf-8",
    )


def setup_logger(config: LoggingConfig) -> None:
    """Configure loguru sinks from config with source-location formatting.

    Args:
        config: Logging configuration with level, file path, rotation, retention.
    """
    logger.remove()
    _configure_library_loggers()
    _configure_warnings()
    logger.configure(patcher=_pad_source)
    _configure_console_sink(config.level)
    _configure_file_sink(config)
