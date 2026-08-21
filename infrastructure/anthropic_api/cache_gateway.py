"""
# mypy: ignore-errors
infrastructure/anthropic_api/cache_gateway.py — Prompt Caching gateway
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Real HTTP calls to api.anthropic.com's Messages API with cache_control
breakpoints — zero print(). Extracted 2026-08-18 from claude_cache.py's
CachingCoder class.

The original had one print()-emitting method, print_cache_stats() —
called only by this module's own 3 cmd_* functions, never externally
(confirmed via a repo-wide grep before removing it). Rather than
carrying it forward with a comment excusing the violation (the mistake
caught and corrected in claude_batch.py's migration earlier this
session), it's gone: cache_stats() — the pure, dict-returning half of
the original method — stays here; the print formatting moved to
interfaces/cli/commands/cache_commands.py's _print_cache_stats(), which
every module doing this same split (PptxSession/ExcelSession/
CodeSession, none of which ever had a print()-emitting method to begin
with) was already following.
"""

import json
import urllib.error
import urllib.request

from domain.cache import (
    MID_SYSTEM_SUPPORTED_MODELS,
    add_cache_breakpoint,
    build_mid_system_message,
    make_cache_control,
    validate_system_message_placement,
)
from exceptions import AICoderError
from resilience import CircuitBreaker, retry, urlopen_json

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)


class CachingCoder:
    """Claude client with explicit prompt-caching support."""

    ENDPOINT = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str = "claude-sonnet-5", max_tokens: int = 4096, ttl: str = "5m"):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.ttl = ttl  # "5m" or "1h"
        self._last_usage: dict = {}
        self._last_message_id: str | None = None
        self._last_cache_miss_reason: str | None = None

    def _post(self, payload: dict, diagnose: bool = False) -> dict:
        body = json.dumps(payload).encode()
        betas = ["prompt-caching-2024-07-31"]
        if diagnose:
            # Cache diagnostics (public beta). Per platform.claude.com/docs
            # (checked 2026-07-02): pass diagnostics.previous_message_id on
            # the request and the API reports cache_miss_reason explaining
            # where the prompt cache prefix diverged from that previous
            # turn. Was entirely missing — no way to see *why* a cache miss
            # happened, only that usage showed 0 cache_read_input_tokens.
            betas.append("cache-diagnosis-2026-04-07")
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": ",".join(betas),
        }
        req = urllib.request.Request(self.ENDPOINT, data=body, headers=headers, method="POST")
        try:
            return self._call(req)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, req: urllib.request.Request) -> dict:
        return urlopen_json(req, timeout=120)

    # ── Single cached call ─────────────────────────────────────────────────

    def generate_cached(
        self,
        prompt: str,
        system: str | None = None,
        cached_docs: list = None,
        history: list = None,
        diagnose: bool = False,
        mid_system: str | None = None,
    ) -> str:
        """
        Call Claude with cache breakpoints on system + docs.
        cached_docs: list of large document strings to cache.
        diagnose=True asks the API to explain a cache miss against the
        previous call this instance made (self._last_message_id) — see
        cache_miss_reason on cache_stats() afterward. Only meaningful
        from the second call in a sequence onward; the first call has
        no previous_message_id to compare against.
        mid_system: if given, appends a mid-conversation system message
        (build_mid_system_message()) to `history` before the new user
        turn — updates Claude's instructions without touching the
        top-level `system` field, so it doesn't invalidate the cached
        prefix. Fable 5, Mythos 5, Opus 4.8 only (MID_SYSTEM_SUPPORTED_MODELS);
        raises
        ValueError on an unsupported model, and
        SystemMessagePlacementError if the resulting `messages` array
        would violate the documented placement rules (e.g. mid_system
        given with no prior history to follow).
        """
        messages = list(history or [])

        if mid_system:
            if self.model not in MID_SYSTEM_SUPPORTED_MODELS:
                raise ValueError(
                    f"Mid-conversation system messages require one of "
                    f"{sorted(MID_SYSTEM_SUPPORTED_MODELS)}; got {self.model!r}. "
                    "Use the top-level `system` field (--cache-system) instead."
                )
            messages.append(build_mid_system_message(mid_system))
            validate_system_message_placement(messages)

        # Build user content
        user_blocks = []
        for doc in cached_docs or []:
            user_blocks.append(add_cache_breakpoint({"type": "text", "text": doc}, self.ttl))
        user_blocks.append({"type": "text", "text": prompt})
        messages.append({"role": "user", "content": user_blocks})

        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
        }

        # Cache the system prompt
        if system:
            payload["system"] = [add_cache_breakpoint({"type": "text", "text": system}, self.ttl)]

        if diagnose:
            # Docs opt in on every call, using previous_message_id: None on
            # the very first one (nothing to compare against yet).
            payload["diagnostics"] = {"previous_message_id": self._last_message_id}

        data = self._post(payload, diagnose=diagnose)
        if "error" in data:
            return f"[API ERROR] {data['error']}"

        self._last_usage = data.get("usage", {})
        self._last_message_id = data.get("id") or self._last_message_id
        # diagnostics is a top-level field on the response, not part of
        # usage — {"cache_miss_reason": {"type": "system_changed", ...}} or
        # null if no divergence was detected (or the comparison is still
        # pending on a very first call).
        diag = data.get("diagnostics") or {}
        miss = diag.get("cache_miss_reason") or {}
        self._last_cache_miss_reason = miss.get("type")
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    # ── Cache pre-warming ──────────────────────────────────────────────────

    def warm_cache(self, system: str = None, docs: list = None) -> dict:
        """
        Pre-warm cache by sending a max_tokens=0 request.
        No output is produced and no output tokens are billed.
        Returns usage showing cache_creation_input_tokens.
        """
        user_blocks = [add_cache_breakpoint({"type": "text", "text": d}, self.ttl) for d in (docs or [])]
        user_blocks.append({"type": "text", "text": "."})  # minimal user msg

        payload: dict = {
            "model": self.model,
            "max_tokens": 1,  # minimal to satisfy API
            "messages": [{"role": "user", "content": user_blocks}],
        }
        if system:
            payload["system"] = [add_cache_breakpoint({"type": "text", "text": system}, self.ttl)]

        data = self._post(payload)
        self._last_usage = data.get("usage", {})
        return self._last_usage

    # ── Tool-definition caching ────────────────────────────────────────────

    def generate_with_cached_tools(
        self,
        prompt: str,
        tools: list,
        system: str | None = None,
    ) -> str:
        """Cache tool definitions at the tools level (invalidated only if tools change)."""
        if tools:
            # Mark the last tool with cache_control
            tools = list(tools)
            tools[-1] = dict(tools[-1])
            tools[-1]["cache_control"] = make_cache_control(self.ttl)

        messages = [{"role": "user", "content": prompt}]
        payload: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": messages,
            "tools": tools,
        }
        if system:
            payload["system"] = [add_cache_breakpoint({"type": "text", "text": system}, self.ttl)]

        data = self._post(payload)
        if "error" in data:
            return f"[API ERROR] {data['error']}"

        self._last_usage = data.get("usage", {})
        blocks = data.get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

    # ── Multi-turn with caching ────────────────────────────────────────────

    def multi_turn_cached(
        self,
        turns: list,
        system: str | None = None,
        mid_system_updates: dict | None = None,
    ) -> list:
        """
        Run a multi-turn conversation, caching the growing history each turn.
        Each assistant response is appended before the next user turn.

        mid_system_updates: optional {turn_index: text} map (0-based,
        turn_index i means "after sending turns[i]'s user message"). Each
        entry inserts a mid-conversation system message
        (build_mid_system_message()) right after that turn's user message
        and before the assistant reply — satisfying the documented
        placement rule (system message immediately follows a user turn,
        and is the last entry in `messages` when the request goes out,
        which satisfies "last entry or followed by an assistant turn").
        Requires self.model in MID_SYSTEM_SUPPORTED_MODELS (Fable 5, Mythos 5,
        Opus 4.8);
        raises ValueError otherwise.
        """
        if mid_system_updates and self.model not in MID_SYSTEM_SUPPORTED_MODELS:
            raise ValueError(
                f"Mid-conversation system messages require one of "
                f"{sorted(MID_SYSTEM_SUPPORTED_MODELS)}; got {self.model!r}."
            )

        messages = []
        responses = []
        mid_system_updates = mid_system_updates or {}

        for idx, turn in enumerate(turns):
            # Cache the entire message history so far
            if messages:
                # Add cache_control to last message
                last = dict(messages[-1])
                content = last.get("content", "")
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                if content:
                    content = list(content)
                    content[-1] = add_cache_breakpoint(content[-1], self.ttl)
                last["content"] = content
                messages[-1] = last

            messages.append({"role": "user", "content": turn})

            if idx in mid_system_updates:
                messages.append(build_mid_system_message(mid_system_updates[idx]))
                validate_system_message_placement(messages)

            payload: dict = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": messages,
            }
            if system:
                payload["system"] = [add_cache_breakpoint({"type": "text", "text": system}, self.ttl)]

            data = self._post(payload)
            self._last_usage = data.get("usage", {})

            if "error" in data:
                responses.append(f"[ERROR] {data['error']}")
                break

            resp_text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            responses.append(resp_text)
            messages.append({"role": "assistant", "content": resp_text})

        return responses

    # ── Cache stats ────────────────────────────────────────────────────────

    def cache_stats(self) -> dict:
        u = self._last_usage
        return {
            "input_tokens": u.get("input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0),
            "cache_creation_input_tokens": u.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": u.get("cache_read_input_tokens", 0),
            # Only populated when the last generate_cached() call passed
            # diagnose=True and the API had a previous request to compare
            # against — see Cache diagnostics (beta) in generate_cached().
            "cache_miss_reason": self._last_cache_miss_reason,
        }
