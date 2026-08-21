"""
infrastructure/github_api/github_gateway.py — GitHub REST API adapter
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

Extracted 2026-08-20 from claude_github.py. In its own
infrastructure/github_api/ package rather than infrastructure/anthropic_api/
— same reasoning as infrastructure/voyage_api/embeddings_gateway.py's
docstring: GitHub is a genuinely different vendor, needs its own
GITHUB_TOKEN/GH_TOKEN, separate from ANTHROPIC_API_KEY, and keeping it in
its own subpackage means a future GitHub outage/rate-limit is never
mistaken for an Anthropic API outage. The shared retry/circuit-breaker
primitives are still reused from infrastructure/anthropic_api/http_client.py
since those are generic HTTP-transport code, not Anthropic-specific (see
that module's own docstring, and resilience.py's shim docstring: "New
code should import from infrastructure.anthropic_api.http_client
directly").
"""

import os
import urllib.request

from exceptions import AICoderError
from infrastructure.anthropic_api.http_client import (
    CircuitBreaker,
    retry,
    urlopen_json,
    urlopen_text,
)

GITHUB_API = "https://api.github.com"
# Shared across all GitHub call sites (issues, PRs, commits, diffs) — they're
# all the same downstream dependency, so repeated GitHub outages/rate-limiting
# should trip one breaker rather than one per call site.
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


def resolve_token(explicit: str | None) -> str:
    token = explicit or os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise ValueError(
            "GitHub token not found. Pass --gh-token or set GITHUB_TOKEN env var. "
            "Create one at https://github.com/settings/tokens (needs 'repo' scope)."
        )
    return token


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def get(path: str, token: str):
    url = f"{GITHUB_API}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-coder-cli/1.9.1",
        },
    )
    try:
        return urlopen_json(req, timeout=20)
    except AICoderError as e:
        raise RuntimeError(f"GitHub API error: {e.message}") from e


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def fetch_diff(diff_url: str, token: str, max_chars: int) -> str:
    """Fetch a PR diff. Was previously inlined (and unretried/unhandled) at
    both of review_pr()'s and generate_pr_description()'s call sites."""
    req = urllib.request.Request(
        diff_url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.diff",
        },
    )
    try:
        return urlopen_text(req, timeout=30)[:max_chars]
    except AICoderError as e:
        raise RuntimeError(f"GitHub diff fetch error: {e.message}") from e
