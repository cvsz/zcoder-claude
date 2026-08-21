"""
resilience.py — COMPATIBILITY SHIM (Clean Architecture refactor, 2026-08-14)

Real content moved to infrastructure/anthropic_api/http_client.py — retries,
backoff, and circuit breaking are a transport/infrastructure concern, not
domain logic, so they belong under infrastructure/ alongside the API
gateway modules that use them.

This shim re-exports every public name so the ~30 existing
`from resilience import ...` call sites across the codebase keep working
unmodified during the migration (Strangler Fig pattern). New code should
import from infrastructure.anthropic_api.http_client directly.
"""

from infrastructure.anthropic_api.http_client import (
    CircuitBreaker,
    raise_for_http_error,
    retry,
    urlopen_json,
    urlopen_json_with_headers,
    urlopen_text,
)

__all__ = [
    "raise_for_http_error",
    "urlopen_json",
    "urlopen_json_with_headers",
    "urlopen_text",
    "CircuitBreaker",
    "retry",
]
