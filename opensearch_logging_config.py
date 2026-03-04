#!/usr/bin/env python3
"""
Configuration for structured logging compatible with OpenSearch and FluentBit.
This module provides a logger configuration that outputs JSON logs suitable for OpenSearch indexing.
"""

import logging
import structlog
import json
from contextlib import contextmanager
from typing import Any, Dict
from parlant.core.loggers import Logger, LogLevel


class OpenSearchJSONRenderer:
    """Custom JSON renderer for OpenSearch compatibility."""

    def __call__(self, logger: Any, name: str, event_dict: Dict[str, Any]) -> str:
        """Render log event as JSON string for OpenSearch."""

        # Ensure timestamp is present
        if "timestamp" not in event_dict:
            import time

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


class OpenSearchLogger(Logger):
    """Logger configured for OpenSearch with FluentBit."""

    def __init__(
        self,
        correlator,
        log_level: LogLevel = LogLevel.DEBUG,
        logger_id: str | None = None,
    ) -> None:
        self._correlator = correlator
        self.raw_logger = logging.getLogger(logger_id or "parlant")
        self.raw_logger.setLevel(log_level.to_logging_level())
        self.log_level = log_level

        # Configure structlog for OpenSearch
        self._logger = structlog.wrap_logger(
            self.raw_logger,
            processors=[
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_log_level,
                structlog.stdlib.filter_by_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                OpenSearchJSONRenderer(),  # Use our custom JSON renderer
            ],
            wrapper_class=structlog.make_filtering_bound_logger(0),
        )

        # Scope support using contextvars
        from parlant.core.common import generate_id
        import contextvars

        self._instance_id = generate_id()
        self._scopes = contextvars.ContextVar[str](
            f"logger_{self._instance_id}_scopes",
            default="",
        )

    def set_level(self, log_level: LogLevel) -> None:
        self.raw_logger.setLevel(log_level.to_logging_level())
        self.log_level = log_level

    def trace(self, message: str, **kwargs) -> None:
        if self.log_level != LogLevel.TRACE:
            return
        self._logger.debug(
            message,
            correlation_id=self._correlator.correlation_id,
            scopes=self._get_scopes(),
            **kwargs,
        )

    def debug(self, message: str, **kwargs) -> None:
        self._logger.debug(
            message,
            correlation_id=self._correlator.correlation_id,
            scopes=self._get_scopes(),
            **kwargs,
        )

    def info(self, message: str, **kwargs) -> None:
        self._logger.info(
            message,
            correlation_id=self._correlator.correlation_id,
            scopes=self._get_scopes(),
            **kwargs,
        )

    def warning(self, message: str, **kwargs) -> None:
        self._logger.warning(
            message,
            correlation_id=self._correlator.correlation_id,
            scopes=self._get_scopes(),
            **kwargs,
        )

    def error(self, message: str, **kwargs) -> None:
        self._logger.error(
            message,
            correlation_id=self._correlator.correlation_id,
            scopes=self._get_scopes(),
            **kwargs,
        )

    def critical(self, message: str, **kwargs) -> None:
        self._logger.critical(
            message,
            correlation_id=self._correlator.correlation_id,
            scopes=self._get_scopes(),
            **kwargs,
        )

    def _get_scopes(self) -> str:
        if scopes := self._scopes.get():
            return scopes
        return ""

    # Implement the remaining abstract methods...
    @contextmanager
    def scope(self, scope_id: str):
        current_scopes = self._scopes.get()
        if current_scopes:
            new_scopes = current_scopes + f"[{scope_id}]"
        else:
            new_scopes = f"[{scope_id}]"
        reset_token = self._scopes.set(new_scopes)
        yield
        self._scopes.reset(reset_token)

    @contextmanager
    def operation(
        self,
        name: str,
        props: dict[str, Any] = {},
        level: LogLevel = LogLevel.DEBUG,
        create_scope: bool = True,
    ):
        # Implementation similar to CorrelationalLogger
        import time
        import asyncio
        import traceback

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


# Example FluentBit configuration for OpenSearch
FLUENTBIT_CONFIG = """
[SERVICE]
    Flush         1
    Log_Level     info
    Daemon        off
    Parsers_File  parsers.conf
    HTTP_Server   On
    HTTP_Listen   0.0.0.0
    HTTP_Port     2020

[INPUT]
    Name              tail
    Path              /var/log/parlant/*.log
    Parser            json
    Tag               parlant.*
    Refresh_Interval  5
    Mem_Buf_Limit     50MB
    Skip_Long_Lines   On

[FILTER]
    Name                modify
    Match               parlant.*
    Add                 service_name parlant
    Add                 environment production

[OUTPUT]
    Name                opensearch
    Match               parlant.*
    Host                opensearch-cluster.example.com
    Port                9200
    Index               parlant-logs
    Type                _doc
    Logstash_Format     On
    Logstash_Prefix     parlant
    Logstash_DateFormat %Y.%m.%d
    Retry_Limit         6
    Suppress_Type_Name  On
    Include_Tag_Key     On
    Tag_Key             tag
"""

# Example OpenSearch index template
OPENSEARCH_INDEX_TEMPLATE = {
    "index_patterns": ["parlant-logs-*"],
    "template": {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 1,
            "index.refresh_interval": "5s",
        },
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "timestamp": {"type": "float"},
                "level": {"type": "keyword"},
                "log_level": {"type": "keyword"},
                "event_type": {"type": "keyword"},
                "service": {"type": "keyword"},
                "service_type": {"type": "keyword"},
                "trace_id": {"type": "keyword"},
                "span_id": {"type": "keyword"},
                "request_id": {"type": "keyword"},
                "correlation_id": {"type": "keyword"},
                "model": {"type": "keyword"},
                "schema": {"type": "keyword"},
                "prompt_length": {"type": "integer"},
                "prompt": {"type": "text", "analyzer": "standard"},
                "duration_seconds": {"type": "float"},
                "usage": {
                    "properties": {
                        "prompt_tokens": {"type": "integer"},
                        "completion_tokens": {"type": "integer"},
                        "total_tokens": {"type": "integer"},
                        "cached_tokens": {"type": "integer"},
                    }
                },
                "response_content": {"type": "object"},
                "raw_response_content": {"type": "text"},
                "scopes": {"type": "keyword"},
            }
        },
    },
}
