"""
infrastructure/anthropic_api/devtools_gateway.py — real HTTP calls for the
Dev-tool Integrations bounded context
AI Model Coder CLI v1.54.0 (Clean Architecture refactor, Phase D, Context #8)

Extracted from claude_git.py (`_call`), claude_github.py (`_call`), and
claude_chrome.py (`fetch_page`/`_fetch_retrying`, and the `Coder`-driven
decide step inside `cmd_browse`). Three call kinds live here rather than
in three separate files:

  - git_generate() / github_generate() — real `api.anthropic.com` calls,
    the same bucket as every other `*_gateway.py` in this package.
  - fetch_page() — a generic arbitrary-URL webpage fetch. It has no
    dedicated vendor/credential (unlike GitHub, which gets its own
    infrastructure/github_api/ package — see that module's docstring),
    so it stays here alongside the Anthropic calls and reuses the same
    shared retry/circuit-breaker transport code from http_client.py.
  - browse_decide() — wraps the pre-existing `Coder` class (coder.py,
    itself not yet part of this refactor's flat-file catalogue — see
    exec-planning.md §3) rather than calling `anthropic.Anthropic`
    directly, preserving claude_chrome.py's original behavior exactly.
"""

import urllib.error
import urllib.request

import anthropic

from domain.devtools import (
    BROWSE_SYSTEM_PROMPT,
    GIT_SYSTEM_PROMPT,
    extract_page_text,
)
from exceptions import APIError
from resilience import raise_for_http_error, retry
from utils import sampling_kwargs

# ── git ───────────────────────────────────────────────────────────────


def git_generate(api_key: str, model: str, user_prompt: str, max_tokens: int = 1024) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        **sampling_kwargs(model, temperature=0.3),
        system=GIT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return resp.content[0].text.strip()


# ── github ────────────────────────────────────────────────────────────


def github_generate(api_key: str, model: str, system: str, user: str, max_tokens: int = 3000) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        **sampling_kwargs(model, temperature=0.3),
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return resp.content[0].text.strip()


# ── browse ────────────────────────────────────────────────────────────


# No CircuitBreaker here deliberately: each step of a browsing session can
# navigate to a completely different, unrelated site — a shared breaker
# would trip on one dead page and start short-circuiting fetches to sites
# that are otherwise reachable.
@retry(max_attempts=2, base_delay=1.0, max_delay=5.0)
def _fetch_retrying(url: str, timeout: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (zcoder-browse)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    except (urllib.error.HTTPError, TimeoutError, ConnectionError, OSError) as e:
        # Translates to the AICoderError hierarchy so retry() above can tell
        # a transient failure from a permanent one; fetch_page()'s `except
        # Exception` below still catches whatever this raises either way.
        raise_for_http_error(e)


def fetch_page(url: str, timeout: float = 15) -> tuple[str | None, list[tuple[str, str]], str | None]:
    """Fetch a URL and return (text, links, error). Never raises."""
    try:
        raw = _fetch_retrying(url, timeout)
    except APIError as e:
        return None, [], f"HTTP {e.status_code} fetching {url}"
    except Exception as e:
        return None, [], f"{type(e).__name__} fetching {url}"

    try:
        text, links = extract_page_text(raw)
    except Exception as e:
        return None, [], f"parse error on {url}: {e}"
    return text, links, None


def make_coder(api_key: str, model: str, temperature: float = 0.0, max_tokens: int = 1024):
    from infrastructure.anthropic_api.core_gateway import Coder

    return Coder(api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)


def browse_decide(coder, prompt: str) -> str:
    return coder.generate(prompt, system=BROWSE_SYSTEM_PROMPT, history=[])
