"""
# mypy: ignore-errors
application/cache_service.py — use-case layer for the Prompt Caching
bounded context
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase C, Context #5)

Orchestrates infrastructure/anthropic_api/cache_gateway.py — no I/O of
its own except read_doc_files() (plain file reads, no print — errors
are returned, not printed), no print(). Extracted 2026-08-18 from
claude_cache.py's cmd_* bodies. Every op returns (result, cache_stats)
so interfaces/cli/commands/cache_commands.py can print the same
"── Cache Stats ──" block after any of the three call shapes, without
this layer or the gateway ever calling print() itself.
"""

from infrastructure.anthropic_api.cache_gateway import CachingCoder


def read_doc_files(doc_files: list) -> tuple:
    """Returns (docs, errors) — errors is a list of (filename, message)
    pairs for files that couldn't be read; the caller decides whether/how
    to report them (originally printed as "[WARN] Cannot read {f}: {e}")."""
    docs = []
    errors = []
    for f in doc_files or []:
        try:
            with open(f) as fh:
                docs.append(fh.read())
        except Exception as e:
            errors.append((f, str(e)))
    return docs, errors


def generate(
    prompt: str,
    api_key: str,
    model: str,
    system: str = None,
    docs: list = None,
    ttl: str = "5m",
    diagnose: bool = False,
) -> tuple:
    cc = CachingCoder(api_key=api_key, model=model, ttl=ttl)
    result = cc.generate_cached(prompt, system=system, cached_docs=docs, diagnose=diagnose)
    return result, cc.cache_stats()


def multi_turn(
    turns: list,
    api_key: str,
    model: str,
    system: str = None,
    ttl: str = "5m",
    mid_system: str = None,
    mid_system_after: int = 0,
) -> tuple:
    """May raise ValueError or domain.cache.SystemMessagePlacementError —
    same as the original, propagated for the CLI layer to catch."""
    cc = CachingCoder(api_key=api_key, model=model, ttl=ttl)
    updates = {mid_system_after: mid_system} if mid_system else None
    responses = cc.multi_turn_cached(turns, system=system, mid_system_updates=updates)
    return responses, cc.cache_stats()


def warm(api_key: str, model: str, system: str = None, doc_files: list = None, ttl: str = "5m") -> tuple:
    """Returns (usage, cache_stats, read_errors)."""
    docs, errors = read_doc_files(doc_files)
    cc = CachingCoder(api_key=api_key, model=model, ttl=ttl)
    usage = cc.warm_cache(system=system, docs=docs)
    return usage, cc.cache_stats(), errors
