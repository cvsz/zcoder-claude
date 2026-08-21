"""domain/advisor.py — Advisor tool domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Pure data + pure functions for the advisor tool. No I/O, no print(), no
`import anthropic` — those belong to infrastructure/.
"""

from typing import Optional

ADVISOR_TOOL_TYPE = "advisor_20260301"
ADVISOR_TOOL_BETA = "advisor-tool-2026-03-01"

ADVISOR_EXECUTOR_MODELS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-haiku-4-5", "claude-haiku-4-5-20251001",
    "claude-fable-5",
}


def build_advisor_tool(advisor_model: str = "claude-opus-4-8",
                       max_uses: Optional[int] = None,
                       max_tokens: Optional[int] = None,
                       cache_ttl: Optional[str] = "5m") -> dict:
    tool = {
        "type": ADVISOR_TOOL_TYPE,
        "name": "advisor",
        "model": advisor_model,
    }
    if max_uses is not None:
        tool["max_uses"] = max_uses
    if max_tokens is not None:
        tool["max_tokens"] = max_tokens
    if cache_ttl:
        tool["caching"] = {"type": "ephemeral", "ttl": cache_ttl}
    return tool


def strip_advisor_blocks(messages: list) -> list:
    cleaned = []
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            content = [
                b for b in content
                if not (isinstance(b, dict) and (
                    (b.get("type") == "server_tool_use" and b.get("name") == "advisor")
                    or b.get("type") == "advisor_tool_result"
                ))
            ]
        cleaned.append({**m, "content": content})
    return cleaned
