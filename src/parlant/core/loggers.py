# Copyright 2025 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations
from abc import ABC, abstractmethod
import asyncio
from contextlib import ExitStack, contextmanager
import contextvars
from enum import Enum, auto
import json
import logging
from pathlib import Path
import structlog
import time
import traceback
from typing import Any, Iterator, Sequence
from typing_extensions import override

from parlant.core.common import generate_id
from parlant.core.contextual_correlator import ContextualCorrelator


class JSONRenderer:
    """Custom JSON renderer for OpenSearch compatibility."""

    def __call__(self, logger: Any, name: str, event_dict: dict[str, Any]) -> str:
        """Render log event as JSON string for OpenSearch."""

        # Ensure timestamp is present
        if "timestamp" not in event_dict:
            event_dict["timestamp"] = time.time()

        # Add service information
        event_dict["service"] = "parlant"
        event_dict["service_type"] = "ai_agent_framework"

        # Ensure log level is present
        if "level" not in event_dict:
            event_dict["level"] = "trace"

        # Add OpenSearch-specific fields
        event_dict["@timestamp"] = event_dict.get("timestamp")
        event_dict["log_level"] = event_dict.get("level")

        # Clean up any None values
        cleaned_dict = {k: v for k, v in event_dict.items() if v is not None}

        return json.dumps(cleaned_dict, default=str, ensure_ascii=False)


class LogLevel(Enum):
    """Enumeration of log levels with comparison and conversion methods."""

    TRACE = auto()
    """Trace level for detailed debugging information."""

    DEBUG = auto()
    """Debug level for general debugging information."""

    INFO = auto()
    """Info level for general informational messages."""

    WARNING = auto()
    """Warning level for potential issues that do not require immediate attention."""

    ERROR = auto()
    """Error level for errors that do not stop the program."""

    CRITICAL = auto()
    """Critical level for severe errors that may cause the program to stop."""

    def __lt__(self, other: LogLevel) -> bool:
        return self.to_int() < other.to_int()

    def __le__(self, other: LogLevel) -> bool:
        return self.to_int() <= other.to_int()

    def __gt__(self, other: LogLevel) -> bool:
        return self.to_int() > other.to_int()

    def __ge__(self, other: LogLevel) -> bool:
        return self.to_int() >= other.to_int()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LogLevel):
            return NotImplemented
        return self.to_int() == other.to_int()

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, LogLevel):
            return NotImplemented
        return self.to_int() != other.to_int()

    def __hash__(self) -> int:
        return super().__hash__()

    def to_logging_level(self) -> int:
        """Convert the log level to a logging module level."""

        return {
            LogLevel.TRACE: logging.DEBUG,
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.CRITICAL: logging.CRITICAL,
        }[self]

    def to_int(self) -> int:
        """Convert the log level to an integer for comparison."""

        return {
            LogLevel.TRACE: 0,
            LogLevel.DEBUG: 1,
            LogLevel.INFO: 2,
            LogLevel.WARNING: 3,
            LogLevel.ERROR: 4,
            LogLevel.CRITICAL: 5,
        }[self]


class Logger(ABC):
    """An abstract base class for logging operations."""

    @abstractmethod
    def set_level(self, log_level: LogLevel) -> None:
        """Set the logging level for the logger."""
        ...

    @abstractmethod
    def trace(self, message: str, **kwargs: Any) -> None:
        """Log a message at the TRACE level with optional structured fields."""
        ...

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a message at the DEBUG level with optional structured fields."""
        ...

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """Log a message at the INFO level with optional structured fields."""
        ...

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log a message at the WARNING level with optional structured fields."""
        ...

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """Log a message at the ERROR level with optional structured fields."""
        ...

    @abstractmethod
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log a message at the CRITICAL level with optional structured fields."""
        ...

    @abstractmethod
    @contextmanager
    def scope(self, scope_id: str) -> Iterator[None]:
        """Create a new logging scope."""
        ...

    @abstractmethod
    @contextmanager
    def operation(
        self,
        name: str,
        props: dict[str, Any] = {},
        level: LogLevel = LogLevel.DEBUG,
        create_scope: bool = True,
    ) -> Iterator[None]:
        """Create a new timed logging operation with a name and properties."""
        ...


class CorrelationalLogger(Logger):
    """A logger that supports correlation IDs for structured logging."""

    def __init__(
        self,
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
        logger_id: str | None = None,
        output_format: str = "console",
    ) -> None:
        self._correlator = correlator
        self.raw_logger = logging.getLogger(logger_id or "parlant")
        self.raw_logger.setLevel(log_level.to_logging_level())
        self.log_level = log_level
        self.output_format = output_format

        # Choose renderer based on output format
        if output_format == "json":
            renderer = JSONRenderer()
        else:
            renderer = structlog.dev.ConsoleRenderer(colors=True)

        # Wrap it with structlog configuration
        self._logger = structlog.wrap_logger(
            self.raw_logger,
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.filter_by_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                renderer,
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
        )

        # Scope support using contextvars
        self._instance_id = generate_id()

        self._scopes = contextvars.ContextVar[str](
            f"logger_{self._instance_id}_scopes",
            default="",
        )

    @override
    def set_level(self, log_level: LogLevel) -> None:
        self.raw_logger.setLevel(log_level.to_logging_level())
        self.log_level = log_level

    @override
    def trace(self, message: str, **kwargs: Any) -> None:
        if self.log_level != LogLevel.TRACE:
            return

        if self.output_format == "json":
            self._logger.debug(
                message,
                correlation_id=self._correlator.correlation_id,
                scopes=self._get_scopes(),
                **kwargs,
            )
        else:
            self._logger.debug(
                f"TRACE {self._add_correlation_id_and_scopes(message)}",
            )

    @override
    def debug(self, message: str, **kwargs: Any) -> None:
        if self.output_format == "json":
            self._logger.debug(
                message,
                correlation_id=self._correlator.correlation_id,
                scopes=self._get_scopes(),
                **kwargs,
            )
        else:
            self._logger.debug(self._add_correlation_id_and_scopes(message))

    @override
    def info(self, message: str, **kwargs: Any) -> None:
        if self.output_format == "json":
            self._logger.info(
                message,
                correlation_id=self._correlator.correlation_id,
                scopes=self._get_scopes(),
                **kwargs,
            )
        else:
            self._logger.info(self._add_correlation_id_and_scopes(message))

    @override
    def warning(self, message: str, **kwargs: Any) -> None:
        if self.output_format == "json":
            self._logger.warning(
                message,
                correlation_id=self._correlator.correlation_id,
                scopes=self._get_scopes(),
                **kwargs,
            )
        else:
            self._logger.warning(self._add_correlation_id_and_scopes(message))

    @override
    def error(self, message: str, **kwargs: Any) -> None:
        if self.output_format == "json":
            self._logger.error(
                message,
                correlation_id=self._correlator.correlation_id,
                scopes=self._get_scopes(),
                **kwargs,
            )
        else:
            self._logger.error(self._add_correlation_id_and_scopes(message))

    @override
    def critical(self, message: str, **kwargs: Any) -> None:
        if self.output_format == "json":
            self._logger.critical(
                message,
                correlation_id=self._correlator.correlation_id,
                scopes=self._get_scopes(),
                **kwargs,
            )
        else:
            self._logger.critical(self._add_correlation_id_and_scopes(message))

    @override
    @contextmanager
    def scope(self, scope_id: str) -> Iterator[None]:
        current_scopes = self._scopes.get()

        if current_scopes:
            new_scopes = current_scopes + f"[{scope_id}]"
        else:
            new_scopes = f"[{scope_id}]"

        reset_token = self._scopes.set(new_scopes)

        yield

        self._scopes.reset(reset_token)

    @override
    @contextmanager
    def operation(
        self,
        name: str,
        props: dict[str, Any] = {},
        level: LogLevel = LogLevel.DEBUG,
        create_scope: bool = True,
    ) -> Iterator[None]:
        log_func = {
            LogLevel.TRACE: self.trace,
            LogLevel.DEBUG: self.debug,
            LogLevel.INFO: self.info,
            LogLevel.WARNING: self.warning,
            LogLevel.ERROR: self.error,
            LogLevel.CRITICAL: self.critical,
        }[level]

        t_start = time.time()
        try:
            if props:
                self.trace(f"{name} [{props}] started")
            else:
                self.trace(f"{name} started")

            if create_scope:
                with self.scope(name):
                    yield
            else:
                yield

            t_end = time.time()

            if props:
                log_func(f"{name} [{props}] finished in {t_end - t_start}s")
            else:
                log_func(f"{name} finished in {round(t_end - t_start, 3)} seconds")
        except asyncio.CancelledError:
            self.warning(f"{name} cancelled after {round(time.time() - t_start, 3)} seconds")
            raise
        except Exception as exc:
            self.error(f"{name} failed")
            self.error(" ".join(traceback.format_exception(exc)))
            raise
        except BaseException as exc:
            self.error(f"{name} failed with critical error")
            self.critical(" ".join(traceback.format_exception(exc)))
            raise

    @property
    def current_scope(self) -> str:
        return self._get_scopes()

    def _add_correlation_id_and_scopes(self, message: str) -> str:
        return f"[{self._correlator.correlation_id}]{self.current_scope} {message}"

    def _get_scopes(self) -> str:
        if scopes := self._scopes.get():
            return scopes
        return ""


class StdoutLogger(CorrelationalLogger):
    """A logger that outputs to standard output."""

    def __init__(
        self,
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
        logger_id: str | None = None,
        output_format: str = "console",
    ) -> None:
        super().__init__(correlator, log_level, logger_id, output_format)
        self.raw_logger.addHandler(logging.StreamHandler())


class FileLogger(CorrelationalLogger):
    """A logger that outputs to a file."""

    def __init__(
        self,
        log_file_path: Path,
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
        logger_id: str | None = None,
        output_format: str = "console",
    ) -> None:
        super().__init__(correlator, log_level, logger_id, output_format)

        handlers: list[logging.Handler] = [
            logging.FileHandler(log_file_path),
            logging.StreamHandler(),
        ]

        for handler in handlers:
            self.raw_logger.addHandler(handler)


class CompositeLogger(Logger):
    """A logger that combines multiple loggers into one."""

    def __init__(self, loggers: Sequence[Logger]) -> None:
        self._loggers = list(loggers)

    def append(self, logger: Logger) -> None:
        self._loggers.append(logger)

    @override
    def set_level(self, log_level: LogLevel) -> None:
        for logger in self._loggers:
            logger.set_level(log_level)

    @override
    def trace(self, message: str, **kwargs: Any) -> None:
        for logger in self._loggers:
            logger.trace(message, **kwargs)

    @override
    def debug(self, message: str, **kwargs: Any) -> None:
        for logger in self._loggers:
            logger.debug(message, **kwargs)

    @override
    def info(self, message: str, **kwargs: Any) -> None:
        for logger in self._loggers:
            logger.info(message, **kwargs)

    @override
    def warning(self, message: str, **kwargs: Any) -> None:
        for logger in self._loggers:
            logger.warning(message, **kwargs)

    @override
    def error(self, message: str, **kwargs: Any) -> None:
        for logger in self._loggers:
            logger.error(message, **kwargs)

    @override
    def critical(self, message: str, **kwargs: Any) -> None:
        for logger in self._loggers:
            logger.critical(message, **kwargs)

    @override
    @contextmanager
    def scope(self, scope_id: str) -> Iterator[None]:
        with ExitStack() as stack:
            for context in [logger.scope(scope_id) for logger in self._loggers]:
                stack.enter_context(context)
            yield

    @override
    @contextmanager
    def operation(
        self,
        name: str,
        props: dict[str, Any] = {},
        level: LogLevel = LogLevel.DEBUG,
        create_scope: bool = True,
    ) -> Iterator[None]:
        with ExitStack() as stack:
            for context in [
                logger.operation(name, props, level, create_scope=create_scope)
                for logger in self._loggers
            ]:
                stack.enter_context(context)
            yield


class LoggerFactory:
    """Factory class for creating loggers with different output formats."""

    @staticmethod
    def create_logger(
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
        output_format: str = "console",
        logger_id: str | None = None,
        log_file_path: Path | None = None,
    ) -> Logger:
        """
        Create a logger with the specified configuration.

        Args:
            correlator: The contextual correlator for correlation IDs
            log_level: The logging level
            output_format: Either "console" or "json"
            logger_id: Optional logger ID
            log_file_path: Optional file path for file logging

        Returns:
            A configured logger instance
        """
        if log_file_path:
            return FileLogger(
                log_file_path=log_file_path,
                correlator=correlator,
                log_level=log_level,
                logger_id=logger_id,
                output_format=output_format,
            )
        else:
            return StdoutLogger(
                correlator=correlator,
                log_level=log_level,
                logger_id=logger_id,
                output_format=output_format,
            )

    @staticmethod
    def create_composite_logger(
        correlator: ContextualCorrelator,
        log_level: LogLevel = LogLevel.DEBUG,
        output_format: str = "console",
        logger_id: str | None = None,
        log_file_path: Path | None = None,
    ) -> CompositeLogger:
        """
        Create a composite logger that outputs to both console and file.

        Args:
            correlator: The contextual correlator for correlation IDs
            log_level: The logging level
            output_format: Either "console" or "json"
            logger_id: Optional logger ID
            log_file_path: File path for file logging

        Returns:
            A composite logger instance
        """
        loggers = [
            StdoutLogger(
                correlator=correlator,
                log_level=log_level,
                logger_id=logger_id,
                output_format=output_format,
            )
        ]

        if log_file_path:
            loggers.append(
                FileLogger(
                    log_file_path=log_file_path,
                    correlator=correlator,
                    log_level=log_level,
                    logger_id=logger_id,
                    output_format=output_format,
                )
            )

        return CompositeLogger(loggers)
