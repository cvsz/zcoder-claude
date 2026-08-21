"""
# mypy: ignore-errors
interfaces/cli/commands/cache_commands.py — CLI presentation for the
Prompt Caching bounded context
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Only print() lives here — all real work delegated to
application/cache_service.py. Extracted 2026-08-18 from claude_cache.py's
cmd_cache_generate, cmd_cache_multi_turn, cmd_cache_warm, and
CachingCoder.print_cache_stats() (moved here as _print_cache_stats() —
see infrastructure/anthropic_api/cache_gateway.py's module docstring for
why it isn't a method on CachingCoder anymore).
"""

from application import cache_service as service
from domain.cache import SystemMessagePlacementError

__all__ = ["cmd_cache_generate", "cmd_cache_multi_turn", "cmd_cache_warm"]


def _print_cache_stats(s: dict):
    hit = s["cache_read_input_tokens"]
    miss = s["cache_creation_input_tokens"]
    inp = s["input_tokens"]
    out = s["output_tokens"]
    ratio = f"{hit/(hit+miss+inp)*100:.1f}%" if (hit + miss + inp) > 0 else "—"
    print("\n\033[90m── Cache Stats ─────────────────────────")
    print(f"  input tokens:        {inp}")
    print(f"  cache write tokens:  {miss}  (billed at 1.25x)")
    print(f"  cache read tokens:   {hit}  (billed at 0.1x)")
    print(f"  output tokens:       {out}")
    print(f"  cache hit rate:      {ratio}")
    if s["cache_miss_reason"]:
        print(f"  cache miss reason:   {s['cache_miss_reason']}  (diagnostics beta)")
    print("──────────────────────────────────────\033[0m")


def cmd_cache_generate(
    prompt: str,
    api_key: str,
    model: str,
    system: str = None,
    docs: list = None,
    ttl: str = "5m",
    show_stats: bool = True,
    diagnose: bool = False,
) -> str:
    print(f"\033[94mℹ Prompt caching enabled (TTL={ttl})\033[0m\n")
    result, stats = service.generate(
        prompt, api_key, model, system=system, docs=docs, ttl=ttl, diagnose=diagnose
    )
    print(result)
    if show_stats:
        _print_cache_stats(stats)
    return result


def cmd_cache_multi_turn(
    turns: list,
    api_key: str,
    model: str,
    system: str = None,
    ttl: str = "5m",
    mid_system: str = None,
    mid_system_after: int = 0,
    show_stats: bool = True,
) -> list:
    """
    Run a multi-turn cached conversation. If mid_system is given, it's
    inserted as a mid-conversation system message immediately after
    turns[mid_system_after] (0-based) — see
    application/cache_service.py's multi_turn() and Mid-conversation
    system messages (Fable 5, Mythos 5, Opus 4.8 only) in
    infrastructure/anthropic_api/cache_gateway.py. Requires at least 2
    turns so there's an assistant reply downstream of the injected
    instruction to demonstrate the effect.
    """
    print(f"\033[94mℹ Prompt caching enabled (TTL={ttl}, {len(turns)} turns)\033[0m")
    if mid_system:
        print(
            f"\033[94mℹ Mid-conversation system message queued after turn "
            f"{mid_system_after}: {mid_system!r}\033[0m"
        )
    try:
        responses, stats = service.multi_turn(
            turns,
            api_key,
            model,
            system=system,
            ttl=ttl,
            mid_system=mid_system,
            mid_system_after=mid_system_after,
        )
    except (ValueError, SystemMessagePlacementError) as e:
        print(f"\033[91m✗ {e}\033[0m")
        return []
    for i, r in enumerate(responses):
        print(f"\n\033[90m── Turn {i+1} ──\033[0m\n{r}")
    if show_stats:
        _print_cache_stats(stats)
    return responses


def cmd_cache_warm(api_key: str, model: str, system: str = None, doc_files: list = None, ttl: str = "5m"):
    print(f"\033[94mℹ Pre-warming cache (TTL={ttl})…\033[0m")
    usage, stats, errors = service.warm(api_key, model, system=system, doc_files=doc_files, ttl=ttl)
    for f, err in errors:
        print(f"  [WARN] Cannot read {f}: {err}")
    created = usage.get("cache_creation_input_tokens", 0)
    print(f"\033[92m✓ Cache warmed — {created} tokens written to cache\033[0m")
    _print_cache_stats(stats)
