# JSON Logging Migration Guide

This guide explains how to migrate from flat text logging to structured JSON logging for better OpenSearch integration.

## Overview

The Parlant application now supports both console (human-readable) and JSON (machine-readable) logging formats. JSON logging provides structured data that is ideal for indexing, searching, and analyzing in OpenSearch.

## Key Benefits

- **Structured Fields**: Easy querying and filtering in OpenSearch
- **Consistent Timestamps**: Standard `@timestamp` field for time-based queries
- **Correlation IDs**: Track requests across distributed systems
- **Service Metadata**: Automatic service identification
- **Nested Objects**: Support for complex data structures
- **OpenSearch Integration**: Direct compatibility with FluentBit and OpenSearch

## Migration Steps

### 1. Update Logger Creation

**Before (Console Logging):**
```python
from parlant.core.loggers import StdoutLogger, LogLevel
from parlant.core.contextual_correlator import ContextualCorrelator

correlator = ContextualCorrelator()
logger = StdoutLogger(correlator, LogLevel.DEBUG)
```

**After (JSON Logging):**
```python
from parlant.core.loggers import LoggerFactory, LogLevel
from parlant.core.contextual_correlator import ContextualCorrelator

correlator = ContextualCorrelator()
logger = LoggerFactory.create_logger(
    correlator=correlator,
    log_level=LogLevel.DEBUG,
    output_format="json"  # Enable JSON format
)
```

### 2. Update Logging Calls

**Before (Simple Messages):**
```python
logger.info("User logged in")
logger.error("Database connection failed")
logger.trace("Processing request")
```

**After (Structured Logging):**
```python
logger.info("User logged in", user_id="12345", session_id="sess_abc")
logger.error("Database connection failed", retry_count=3, error_code="DB_TIMEOUT")
logger.trace("Processing request", request_id="req_123", endpoint="/api/users")
```

### 3. Environment Configuration

Set the logging format via environment variable:

```bash
# For JSON logging (recommended for production)
export LOG_OUTPUT_FORMAT=json

# For console logging (development)
export LOG_OUTPUT_FORMAT=console
```

### 4. File Logging Configuration

**Before:**
```python
from parlant.core.loggers import FileLogger
from pathlib import Path

logger = FileLogger(
    log_file_path=Path("/var/log/parlant.log"),
    correlator=correlator,
    log_level=LogLevel.DEBUG
)
```

**After:**
```python
from parlant.core.loggers import LoggerFactory
from pathlib import Path

logger = LoggerFactory.create_logger(
    correlator=correlator,
    log_level=LogLevel.DEBUG,
    output_format="json",
    log_file_path=Path("/var/log/parlant.log")
)
```

## Log Format Examples

### Console Format (Human-Readable)
```
2024-01-01T12:00:00.123Z [corr_abc123] [scope] INFO User logged in
```

### JSON Format (OpenSearch-Compatible)
```json
{
  "@timestamp": "2024-01-01T12:00:00.123Z",
  "timestamp": 1704067200.123,
  "level": "info",
  "log_level": "info",
  "service": "parlant",
  "service_type": "ai_agent_framework",
  "correlation_id": "corr_abc123",
  "scopes": "[scope]",
  "event": "User logged in",
  "user_id": "12345",
  "session_id": "sess_abc"
}
```

## OpenSearch Integration

### 1. FluentBit Configuration

Create a FluentBit configuration to parse JSON logs:

```ini
[SERVICE]
    Flush         1
    Log_Level     info
    Daemon        off
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
```

### 2. OpenSearch Index Template

Apply the index template for optimal field mapping:

```bash
curl -X PUT "opensearch-cluster:9200/_index_template/parlant-logs" \
  -H "Content-Type: application/json" \
  -d @opensearch_index_template.json
```

### 3. Example Queries

Once logs are indexed in OpenSearch, you can run powerful queries:

```json
// Find all errors
{
  "query": {
    "term": {
      "level": "error"
    }
  }
}

// Trace specific request
{
  "query": {
    "term": {
      "trace_id": "req_abc123"
    }
  }
}

// Azure API performance analysis
{
  "query": {
    "bool": {
      "must": [
        {"term": {"event_type": "azure_openai_response"}},
        {"range": {"duration_seconds": {"gte": 5.0}}}
      ]
    }
  }
}

// Rate limit warnings
{
  "query": {
    "bool": {
      "must": [
        {"wildcard": {"event": "*rate*"}},
        {"term": {"level": "warning"}}
      ]
    }
  }
}
```

## Best Practices

### 1. Structured Field Naming

Use consistent, descriptive field names:
- `user_id` instead of `uid`
- `request_id` instead of `req_id`
- `duration_seconds` instead of `duration`

### 2. Field Types

Choose appropriate field types for OpenSearch:
- `keyword` for exact matches (IDs, status codes)
- `text` for full-text search (messages, prompts)
- `integer` for counts and metrics
- `float` for durations and measurements
- `object` for nested data structures

### 3. Sensitive Data

Avoid logging sensitive information:
```python
# ❌ Don't log passwords or tokens
logger.info("User authenticated", password=user_password)

# ✅ Log non-sensitive identifiers
logger.info("User authenticated", user_id=user.id, session_id=session.id)
```

### 4. Performance Considerations

- Use appropriate log levels to control verbosity
- Consider log volume impact on OpenSearch cluster
- Implement log rotation for file-based logging
- Monitor OpenSearch index size and performance

## Testing the Migration

### 1. Run the Example Script

```bash
python json_logging_example.py
```

This will demonstrate both console and JSON logging formats.

### 2. Verify JSON Output

Check that logs are properly formatted as JSON:

```bash
tail -f /var/log/parlant.log | jq .
```

### 3. Test OpenSearch Integration

1. Start FluentBit with the provided configuration
2. Generate some application logs
3. Verify logs appear in OpenSearch
4. Run test queries to validate field mappings

## Troubleshooting

### Common Issues

1. **Malformed JSON**: Ensure all log calls use proper structured fields
2. **Missing Fields**: Check that required fields are included in log calls
3. **FluentBit Parsing**: Verify FluentBit can parse the JSON format
4. **OpenSearch Mapping**: Ensure index template is applied correctly

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
logger = LoggerFactory.create_logger(
    correlator=correlator,
    log_level=LogLevel.TRACE,  # Most verbose
    output_format="json"
)
```

## Rollback Plan

If issues arise, you can quickly rollback to console logging:

```python
# Change output format back to console
logger = LoggerFactory.create_logger(
    correlator=correlator,
    log_level=LogLevel.DEBUG,
    output_format="console"  # Back to human-readable
)
```

Or set the environment variable:
```bash
export LOG_OUTPUT_FORMAT=console
```

## Conclusion

The migration to JSON logging provides significant benefits for observability and analysis. The structured format enables powerful querying capabilities in OpenSearch while maintaining backward compatibility with console logging for development environments.

For questions or issues during migration, refer to the example scripts and test the configuration thoroughly before deploying to production.
