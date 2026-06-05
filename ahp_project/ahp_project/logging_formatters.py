"""
logging_formatters.py — Production-safe JSON log formatter with field redaction.

In production (DEBUG=False), all handlers use this formatter so logs are
structured and searchable in ELK, Loki, or Sentry.

Redacted fields: any key whose name matches a sensitive pattern is replaced
with '[REDACTED]' so secrets never appear in log aggregators.
"""

import json
import logging
import re
import traceback
from datetime import datetime, timezone

# Fields whose VALUES should never appear in logs.
_SENSITIVE_KEYS = frozenset({
    'password', 'token', 'access', 'refresh', 'signature',
    'secret', 'authorization', 'key_secret', 'webhook_secret',
    'razorpay_signature', 'razorpay_key_secret', 'credit_card',
    'cvv', 'card_number',
})

_SENSITIVE_RE = re.compile(
    r'(?i)\b(?:' + '|'.join(re.escape(k) for k in _SENSITIVE_KEYS) + r')\b'
)

# LogRecord attributes that belong to the logging machinery — excluded from
# extra fields so we don't double-emit them.
_STDLIB_ATTRS = frozenset({
    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
    'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
    'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
    'processName', 'process', 'message', 'taskName', 'asctime',
})


def _redact_value(key: str, value):
    """Return '[REDACTED]' if *key* looks like a sensitive field."""
    if _SENSITIVE_RE.search(key):
        return '[REDACTED]'
    return value


def _safe_serialize(value):
    """Make a value JSON-serializable without crashing."""
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log line.

    Structure:
        {
            "timestamp": "2024-01-15T10:30:00.000Z",
            "level": "INFO",
            "logger": "billing.services.billing_service",
            "message": "Payment verified: ...",
            "request_id": "a1b2c3...",   # injected by RequestIDFilter
            "user_id": 42,               # injected by RequestIDFilter
            "module": "billing_service",
            "function": "verify_payment",
            "line": 88,
            "exception": { ... }         # only on exc_info records
        }
    """

    def format(self, record: logging.LogRecord) -> str:
        # Build the timestamp in UTC ISO-8601.
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        log_dict: dict = {
            'timestamp': ts,
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Context injected by RequestIDFilter (always present when inside a request).
        if hasattr(record, 'request_id'):
            log_dict['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_dict['user_id'] = record.user_id

        # Exception details.
        if record.exc_info:
            log_dict['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'value': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': traceback.format_exception(*record.exc_info),
            }

        # Caller-supplied extra fields — redact sensitive keys.
        for key, value in record.__dict__.items():
            if key in _STDLIB_ATTRS or key.startswith('_'):
                continue
            log_dict[key] = _safe_serialize(_redact_value(key, value))

        return json.dumps(log_dict, default=str, ensure_ascii=False)
