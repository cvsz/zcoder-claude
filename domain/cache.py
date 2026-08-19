"""
domain/cache.py — Prompt Caching domain layer
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Pure data and pure logic for the Prompt Caching bounded context —
MID_SYSTEM_SUPPORTED_MODELS, SystemMessagePlacementError,
build_mid_system_message(), validate_system_message_placement(), and
the cache_control breakpoint helpers. No I/O, no print(). Extracted
2026-08-18 from claude_cache.py.

CachingCoder itself is NOT here — it's a pure HTTP gateway (no local
disk I/O at all, unlike every other Context #5 module), so it lives in
infrastructure/anthropic_api/cache_gateway.py.
"""

# ── Mid-conversation system messages (v1.18.0; model gate corrected v1.36.0) ─
# Per platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages
# (re-checked 2026-07-26): available on Claude Fable 5, Claude Mythos 5, and
# Claude Opus 4.8, on the Claude API, Amazon Bedrock, and Google Cloud; no
# beta header required. The July 15, 2026 release notes explicitly flagged
# this as a *correction* to an earlier availability note that said Opus 4.8
# only — this module had baked in exactly that stale note at v1.18.0 launch
# and was never revisited, so it silently rejected Fable 5 / Mythos 5 calls
# that the platform has accepted since launch. Not supported on Claude
# Sonnet 5 or Claude Opus 5 (use the top-level `system` field instead).
MID_SYSTEM_SUPPORTED_MODELS = {"claude-fable-5", "claude-mythos-5", "claude-opus-4-8"}


class SystemMessagePlacementError(ValueError):
    """Raised when a mid-conversation system message would violate the
    API's documented placement rules (these return a 400 error server-side;
    validating client-side catches it before spending a round trip)."""


def build_mid_system_message(text: str) -> dict:
    """Build a {"role": "system", ...} message for the `messages` array.

    Content supports text blocks only — no images, documents, tool blocks,
    or citations (per docs). This is a *message*, not the top-level
    `system` field: it carries the same operator-level authority, so never
    build one from untrusted content (tool output, retrieved documents,
    web content) — that would grant that text operator authority.
    """
    return {"role": "system", "content": [{"type": "text", "text": text}]}


def validate_system_message_placement(messages: list) -> None:
    """Validate every role:"system" entry in `messages` against the
    documented placement rules. Raises SystemMessagePlacementError on the
    first violation found; does nothing if there are no system messages or
    all of them are correctly placed.

    Rules (platform.claude.com/docs, checked 2026-07-08):
      - Cannot be the first entry in `messages`.
      - Must immediately follow a user turn (including one carrying
        tool_result blocks) or an assistant turn that ends in a server
        tool use.
      - Must either be the last entry in `messages` or be followed by an
        assistant turn.
      - Cannot sit between a tool_use block and its tool_result.
      - Cannot be adjacent to another system message (no consecutive
        system messages).
    """
    def _is_system(m: dict) -> bool:
        return m.get("role") == "system"

    def _block_types(content) -> set:
        if isinstance(content, str):
            return set()
        return {b.get("type") for b in (content or []) if isinstance(b, dict)}

    for i, msg in enumerate(messages):
        if not _is_system(msg):
            continue

        if i == 0:
            raise SystemMessagePlacementError(
                "A system message cannot be the first entry in messages; "
                "use the top-level `system` field for turn-one instructions.")

        prev = messages[i - 1]
        if _is_system(prev):
            raise SystemMessagePlacementError(
                f"System message at index {i} is adjacent to another system "
                f"message at index {i-1}; consecutive system messages are "
                "not allowed.")

        prev_types = _block_types(prev.get("content"))

        # An assistant turn ending in a client-side tool_use (not
        # server_tool_use) is always followed by that tool's tool_result —
        # inserting a system message right after it would sit between the
        # tool_use and its tool_result, which is invalid regardless of the
        # more general "must follow user/server-tool-use" rule below.
        if prev.get("role") == "assistant" and "tool_use" in prev_types \
                and "server_tool_use" not in prev_types:
            raise SystemMessagePlacementError(
                f"System message at index {i} cannot sit between a tool_use "
                "block and its tool_result.")

        prev_ok = (
            prev.get("role") == "user"
            or (prev.get("role") == "assistant" and "server_tool_use" in prev_types)
        )
        if not prev_ok:
            raise SystemMessagePlacementError(
                f"System message at index {i} must immediately follow a user "
                "turn or an assistant turn ending in server tool use "
                f"(preceding message has role={prev.get('role')!r}).")

        if i < len(messages) - 1:
            nxt = messages[i + 1]
            if _is_system(nxt):
                raise SystemMessagePlacementError(
                    f"System message at index {i} is adjacent to another "
                    f"system message at index {i+1}; consecutive system "
                    "messages are not allowed.")
            if nxt.get("role") != "assistant":
                raise SystemMessagePlacementError(
                    f"System message at index {i} must be the last entry in "
                    f"messages or be followed by an assistant turn "
                    f"(next message has role={nxt.get('role')!r}).")


# ── Cache-control breakpoint helpers ─────────────────────────────────────

def make_cache_control(ttl: str = "5m") -> dict:
    """Build a cache_control block."""
    if ttl == "1h":
        return {"type": "ephemeral", "ttl": 3600}
    return {"type": "ephemeral"}          # 5-minute default


def add_cache_breakpoint(block: dict, ttl: str = "5m") -> dict:
    """Return a copy of block with cache_control injected."""
    b = dict(block)
    b["cache_control"] = make_cache_control(ttl)
    return b
