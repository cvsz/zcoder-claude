"""
claude_observability.py — Observability (compatibility shim)
AI Model Coder CLI v1.53.1 (Clean Architecture refactor, Phase D, Context #7)

This module used to contain the full implementation (144 lines: structured
request logging, the `observe` auto-instrumentation decorator, a latency
histogram + report, AI-powered error-trend analysis, and 4 cmd_* CLI entry
points). It has been split into:

  domain/observability.py                             — histogram() (was
                                                          _histogram()),
                                                          build_latency_report()
                                                          (pure aggregation
                                                          half of the old
                                                          latency_report()),
                                                          build_request_record()
                                                          (pure record-shaping
                                                          half of the old
                                                          record_request())
  infrastructure/local_storage/observability_store.py — OBS_DIR, OBS_LOG_FILE
                                                          (was LOG_FILE),
                                                          log_observability_request()
                                                          (was _log()),
                                                          read_observability_logs()
                                                          (was _read_logs()),
                                                          clear_observability_log()
  infrastructure/anthropic_api/observability_gateway.py — analyze_errors()
                                                          (the real HTTP-call
                                                          half of the old
                                                          error_analysis(),
                                                          minus its print())
  application/observability_service.py                 — use-case layer
  interfaces/cli/commands/observability_commands.py     — print(), the 4
                                                          cmd_* entry points

record_request() and the observe() decorator were programmatic
instrumentation helpers, not CLI entry points (no cmd_* prefix, never
wired to a flag) — they compose the pure domain record-builder with the
infra log-append function directly here rather than living in
application/observability_service.py, since that layer's Definition of
Done requires every function there to be reachable from an
interfaces/cli/commands/* function, which these never were even in the
original. latency_report() and error_analysis() DID print() directly in
the original (cmd_obs_latency/cmd_obs_errors were thin one-line
passthroughs to them) — aliased below to the new cmd_obs_latency/
cmd_obs_errors, which reproduce that exact printed output now that the
print() half has moved to interfaces/ per this refactor's Definition of
Done.

This file re-exports every name the old module used to export, so
existing imports (`from claude_observability import cmd_obs_latency`,
etc., used by main.py) keep working unmodified. See exec-planning.md §5
(migration playbook).
"""

from functools import wraps
import time
from typing import Callable, List, Optional

from domain.observability import histogram as _histogram
from infrastructure.local_storage.observability_store import (
    OBS_DIR, OBS_LOG_FILE as LOG_FILE,
    log_observability_request as _log,
    read_observability_logs as _read_logs,
)
from interfaces.cli.commands.observability_commands import (
    cmd_obs_latency, cmd_obs_errors, cmd_obs_clear, cmd_obs_tail,
)

# error_analysis/latency_report used to print() directly (cmd_obs_errors/
# cmd_obs_latency were one-line passthroughs to them) — now that the
# print() half lives in interfaces/, these old names are aliased straight
# to the new cmd_* functions, which are behaviorally identical.
error_analysis = cmd_obs_errors
latency_report = cmd_obs_latency


def record_request(model: str, prompt: str, response: str,
                   latency_ms: int, in_tokens: int, out_tokens: int,
                   error: Optional[str] = None, tags: Optional[List[str]] = None):
    from domain.observability import build_request_record
    _log(build_request_record(model, prompt, response, latency_ms,
                              in_tokens, out_tokens, error=error, tags=tags))


def observe(model: str = "unknown", tags: Optional[List[str]] = None):
    """Decorator: wrap any function that (a) takes prompt as first arg and
    (b) returns a string response, logging latency + token estimate."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            prompt = args[0] if args else kwargs.get("prompt", "")
            t0 = time.time()
            error = None
            result = ""
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception as e:
                error = str(e); raise
            finally:
                ms = int((time.time() - t0) * 1000)
                est_in  = max(1, len(str(prompt)) // 4)
                est_out = max(1, len(str(result)) // 4)
                record_request(model, str(prompt), str(result), ms,
                               est_in, est_out, error=error, tags=tags)
        return wrapper
    return decorator


__all__ = [
    "OBS_DIR", "LOG_FILE", "_log", "_read_logs", "_histogram",
    "record_request", "observe", "latency_report", "error_analysis",
    "cmd_obs_latency", "cmd_obs_errors", "cmd_obs_clear", "cmd_obs_tail",
]
