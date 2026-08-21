"""
claude_response_metadata.py — Claude API response header metadata (compatibility shim)
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real implementation moved 2026-08-21:
  - MESSAGES_ENDPOINT, ResponseMetadata → domain/model_wrappers.py
  - _WHOAMI_MODEL, _call_with_headers, get_response_metadata
              → infrastructure/anthropic_api/model_wrappers_gateway.py
  - cmd_whoami → interfaces/cli/commands/wrapper_commands.py

Why this existed as a flat module: the Claude API release notes
(2026-08-11) added the `anthropic-workspace-id` response header to every
Messages API response, but resilience.urlopen_json() discards the
`http.client.HTTPResponse` entirely — so the header was unreachable from
any call site. This module's whoami path uses
resilience.urlopen_json_with_headers() (the header-preserving variant)
to report both `anthropic-workspace-id` and the older
`anthropic-organization-id`. See
infrastructure/anthropic_api/model_wrappers_gateway.py for the reference
implementation.

Note for tests: `_call_with_headers` and `urlopen_json_with_headers` now
resolve inside the gateway module — monkeypatch them there (module-level
patches against this shim no longer intercept anything).

New code should import from those locations directly rather than through
this shim.
"""

from domain.model_wrappers import MESSAGES_ENDPOINT, ResponseMetadata
from infrastructure.anthropic_api.model_wrappers_gateway import get_response_metadata
from interfaces.cli.commands.wrapper_commands import cmd_whoami

__all__ = [
    "MESSAGES_ENDPOINT",
    "ResponseMetadata",
    "get_response_metadata",
    "cmd_whoami",
]
