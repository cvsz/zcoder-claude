"""
claude_response_metadata.py — Claude API response header metadata
AI Model Coder CLI v1.40.0

Why this module exists: the Claude API release notes (2026-08-11) added the
`anthropic-workspace-id` response header to every Messages API response —
the `wrkspc_`-prefixed ID of the workspace the request's API key or access
token resolved to, including the organization's Default Workspace. See
platform.claude.com/docs/en/manage-claude/workspaces#identify-the-workspace-
behind-an-api-response.

This was a genuine, systemic gap when found (2026-08-14 release-gate audit):
every Messages API call in this codebase goes through
`resilience.urlopen_json()`, which parses the JSON body and discards the
`http.client.HTTPResponse` entirely — so the header was unreachable from
any call site, not just missing from one. Rather than retrofit ~30 call
sites (high regression risk for a header most callers don't need), this
module adds a single, narrow, purpose-built path: a minimal `--whoami`
Messages API call (1 max_token, cheapest current model) that uses
`resilience.urlopen_json_with_headers()` — the new header-preserving
variant added alongside this module — and reports both
`anthropic-workspace-id` and the older `anthropic-organization-id`
(present since 2025-02-10, and equally unexposed before this).

Any other module wanting these headers should adopt
`urlopen_json_with_headers()` at its own call site the same way; this
module is the reference implementation and the CLI-facing tool for one-off
lookups, not the only sanctioned caller.

CLI flags:
  --whoami            Make a minimal Messages API call and print the
                       workspace and organization IDs it resolved to
"""

import json
import urllib.request
from typing import Optional

from resilience import CircuitBreaker, retry, urlopen_json_with_headers
from exceptions import AICoderError

MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"
# Cheapest current-tier model with no special sampling/thinking gating —
# this call exists purely to read response headers, so cost matters more
# than capability. See claude_models.MODEL_CATALOG.
_WHOAMI_MODEL = "claude-haiku-4-5-20251001"

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class ResponseMetadata:
    """Parsed subset of response headers this module cares about.
    `raw` keeps the full header dict for callers who want more."""

    def __init__(self, workspace_id: Optional[str], organization_id: Optional[str], raw: dict):
        self.workspace_id = workspace_id
        self.organization_id = organization_id
        self.raw = raw


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _call_with_headers(api_key: str) -> tuple:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": _WHOAMI_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    req = urllib.request.Request(
        MESSAGES_ENDPOINT, data=json.dumps(payload).encode(),
        headers=headers, method="POST",
    )
    return urlopen_json_with_headers(req, timeout=60)


def get_response_metadata(api_key: str) -> ResponseMetadata:
    """Make the minimal whoami call and return the parsed metadata.
    Raises AICoderError on failure (bad key, network error, etc.) — same
    exception type every other claude_*.py client raises, so callers can
    catch it uniformly."""
    _body, response_headers = _call_with_headers(api_key)
    # Header names arrive case-normalized inconsistently across urllib
    # versions/platforms; check both cases explicitly rather than assuming.
    workspace_id = response_headers.get("anthropic-workspace-id") or \
        response_headers.get("Anthropic-Workspace-Id")
    organization_id = response_headers.get("anthropic-organization-id") or \
        response_headers.get("Anthropic-Organization-Id")
    return ResponseMetadata(workspace_id, organization_id, response_headers)


def cmd_whoami(api_key: str):
    try:
        meta = get_response_metadata(api_key)
    except AICoderError as e:
        print(f"[ERROR] {e.message}")
        return None
    print("\n\033[94mResponse metadata\033[0m (from a minimal Messages API call)")
    print(f"  Workspace ID:     {meta.workspace_id or '(none returned)'}")
    print(f"  Organization ID:  {meta.organization_id or '(none returned)'}")
    if not meta.workspace_id:
        print("\033[90m  No anthropic-workspace-id header — this key/token may predate the "
             "2026-08-11 rollout, or you're hitting a non-Claude-API endpoint.\033[0m")
    print()
    return meta
