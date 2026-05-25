"""Logger factory and configuration utilities.

Provides helpers to create and configure loggers with Rich console
output, rotating file handlers, and overrides for noisy third-party
loggers.
"""

import logging
from logging import Handler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field, computed_field
from rich.logging import RichHandler

from lib_oriv_telemetry._internal.paths import ensure_path_exists
from lib_oriv_telemetry.enums import EnvironmentEnum


class LoggerOverrides(BaseModel):
    """Model controlling console logging and third-party overrides."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    console_log: bool = Field(
        default=True,
        description="Enable or disable Rich console output for all loggers.",
    )
    propagate: bool = Field(
        default=False, description="Allow logs to bubble up to parent loggers."
    )
    formatter: Optional[logging.Formatter] = Field(
        None, description="Optional logging formatter for customizing log output."
    )
    override_loggers: Set[str] = Field(
        default_factory=set, description="Names of external loggers to reconfigure."
    )
    noisy_loggers: Set[str] = Field(
        default_factory=lambda: {
            "uvicorn",
            "uvicorn.error",
            "uvicorn.access",
            "mkdocs",
            "mkdocs.plugins",
            "dspy",
            "dspy.core",
            "dspy.telemetry",
        },
        description="Set of known noisy third-party loggers to override or silence.",
    )
    apply_handlers: bool = Field(
        default=True,
        description="If True, apply main logger handlers to sub-loggers.",
    )

    @computed_field
    @property
    def combined_loggers(self) -> Set[str]:
        """Return the union of noisy loggers and user-specified overrides."""
        return self.noisy_loggers.union(self.override_loggers)


def setup_logger(
    logger: logging.Logger,
    level: int = logging.INFO,
    formatter: Optional[logging.Formatter] = None,
    log_file_path: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    rich_tracebacks: bool = True,
    console_log: bool = True,
    propagate: bool = False,
    handlers: Optional[List[Handler]] = None,
) -> None:
    """Configure a logger with console (Rich) and optional rotating file handlers.

    Args:
        logger: Logger instance to configure.
        level: Logging level (default: INFO).
        formatter: Optional formatter for file output.
        log_file_path: Directory or file path for log output.
        max_bytes: Maximum size per log file before rotation.
        backup_count: Number of old log files to keep.
        rich_tracebacks: Enable Rich tracebacks in console logs.
        console_log: Whether to log to console using RichHandler.
        propagate: Whether log records bubble up to parent loggers.
        handlers: Additional handlers to attach to the logger.
    """
    logger.handlers.clear()
    logging.getLogger().addHandler(logging.NullHandler())

    handlers = handlers or []

    if console_log:
        console_handler = RichHandler(
            rich_tracebacks=rich_tracebacks,
            show_path=False,
            markup=True,
            show_time=True,
            show_level=True,
        )
        console_handler.setLevel(level)
        if formatter:
            console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file_path:
        file_path = Path(log_file_path)
        if file_path.suffix == "":
            file_path = file_path / f"{logger.name}.log"

        ensure_path_exists(file_path, is_file=True)

        file_handler = RotatingFileHandler(
            filename=file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)

        if formatter:
            file_handler.setFormatter(formatter)
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s %(message)s",
                "%Y-%m-%d %H:%M:%S",
            )
            file_handler.setFormatter(file_formatter)

        logger.addHandler(file_handler)

    logger.setLevel(level)
    logger.propagate = propagate

    existing_handler_types = {type(h) for h in logger.handlers}
    for handler in handlers:
        if type(handler) not in existing_handler_types:
            logger.addHandler(handler)


def create_logger(
    name: str = "lib_oriv_logger",
    formatter: Optional[logging.Formatter] = None,
    level: Optional[int] = None,
    environment: EnvironmentEnum = EnvironmentEnum.PRODUCTION,
    overrides: Optional[LoggerOverrides] = None,
    log_file_path: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
    console_log: bool = True,
    reuse_existing: bool = True,
    handlers: Optional[List[Handler]] = None,
) -> logging.Logger:
    """Create and configure a project-wide logger with optional file logging."""
    logger = logging.getLogger(name)
    if reuse_existing and logger.handlers:
        return logger

    overrides = overrides or LoggerOverrides(formatter=None)
    handlers = handlers or []

    if level is None:
        level = (
            logging.DEBUG if environment == EnvironmentEnum.SANDBOX else logging.INFO
        )

    setup_logger(
        logger=logger,
        level=level,
        formatter=formatter,
        log_file_path=log_file_path,
        max_bytes=max_bytes,
        backup_count=backup_count,
        console_log=console_log,
        propagate=False,
        handlers=handlers,
    )

    for logger_name in overrides.combined_loggers:
        sub_logger = logging.getLogger(logger_name)
        setup_logger(
            logger=sub_logger,
            level=level,
            formatter=overrides.formatter,
            log_file_path=log_file_path,
            max_bytes=max_bytes,
            backup_count=backup_count,
            console_log=overrides.console_log,
            propagate=overrides.propagate,
            handlers=handlers if overrides.apply_handlers else [],
        )

    return logger


def ensure_logger(
    logger: logging.Logger | None = None,
    name: str | None = None,
) -> logging.Logger:
    """Return the given logger or create a silent one with a NullHandler."""
    if logger is not None:
        return logger

    new_logger = logging.getLogger(name or __name__)
    new_logger.handlers.clear()
    new_logger.addHandler(logging.NullHandler())
    return new_logger
