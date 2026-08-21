"""
# mypy: ignore-errors
application/models_service.py — Use-case layer for model catalog operations
AI Model Coder CLI v1.43.0 (Clean Architecture refactor)

This is the layer that was missing after the first four modules were split
(2026-08-14 gap analysis): interfaces/cli/commands/model_commands.py used
to call infrastructure/anthropic_api/models_gateway.py directly, so any
future Web UI would either duplicate this logic or import a CLI-presentation
module just to reach it. Everything here takes/returns plain data (dicts,
lists, dataclasses) — zero print(), zero argparse, so any interface
(CLI today, Web later) can call the same functions and format the result
its own way.

Functions here own the "what to do" business rules that used to be
tangled into cmd_* — e.g. cmd_model_info's live-API-with-local-fallback
logic, cmd_check_deprecated's filesystem scan, cmd_upgrade_all's rewrite
logic. The gateway classes (ModelsAPI, ComputerUseCoder,
AdaptiveThinkingCoder) stay pure HTTP; domain/models/catalog.py stays pure
data; this module is the glue between them.
"""

import os
import re

from domain.models.catalog import (
    DEPRECATED_MODELS,
    MODEL_CATALOG,
    RETIRED_MODELS,
    TIER_ORDER,
    UPGRADE_TARGETS,
    _upgrade_source_ids,
    check_deprecated,
    check_retired,
)
from infrastructure.anthropic_api.models_gateway import (
    AdaptiveThinkingCoder,
    ComputerUseCoder,
    ModelsAPI,
)


def list_models(api_key: str, include_legacy: bool = False) -> dict:
    """{'source': 'live', 'models': [...]} from the real Models API, or
    {'source': 'local', 'tiers': {tier: [(id, info), ...]}, 'error': str}
    from the offline catalog if the live call fails. Caller decides how
    to render either shape."""
    ma = ModelsAPI(api_key=api_key)
    try:
        models = ma.list_models()
        return {"source": "live", "models": models}
    except RuntimeError as e:
        tiers = TIER_ORDER if include_legacy else ["mythos", "current"]
        by_tier = {}
        for tier in tiers:
            rows = [(mid, info) for mid, info in MODEL_CATALOG.items() if info["tier"] == tier]
            if rows:
                by_tier[tier] = rows
        return {"source": "local", "tiers": by_tier, "include_legacy": include_legacy, "error": str(e)}


def get_model_info(model_id: str, api_key: str) -> dict:
    """{'retired': rec|None, 'deprecated': rec|None, 'live': dict|None,
    'local_fallback': dict|None, 'error': str|None}. `live` is populated
    on a successful Models API call; if that fails, `local_fallback` is
    populated from MODEL_CATALOG when known, else `error` is set (unless
    the model is already known `retired`, in which case a live 400/404 is
    expected and not surfaced as an error)."""
    retired = check_retired(model_id)
    deprecated = check_deprecated(model_id)
    result = {
        "retired": retired,
        "deprecated": deprecated,
        "live": None,
        "local_fallback": None,
        "error": None,
    }

    ma = ModelsAPI(api_key=api_key)
    try:
        result["live"] = ma.get_model(model_id)
    except RuntimeError as e:
        info = MODEL_CATALOG.get(model_id)
        if info:
            result["local_fallback"] = dict(info, id=model_id)
        elif not retired:
            result["error"] = str(e)
        # else: retired and unknown to the live API — expected, not an error
    return result


def scan_for_deprecated_models(path: str) -> dict:
    """Text-scan `path` (file or directory) for retired/deprecated model
    ID strings. Returns {'retired_hits': {id: [(file, line), ...]},
    'deprecated_hits': {...}}. Matches Anthropic's own documented
    migration advice (grep the whole codebase, not just the primary call
    site) — intentionally a text scan, not an AST, so it also catches IDs
    in env files, CI configs, etc."""
    retired_targets = list(RETIRED_MODELS.keys())
    deprecated_targets = list(DEPRECATED_MODELS.keys())
    all_targets = retired_targets + deprecated_targets
    pattern = re.compile("|".join(re.escape(t) for t in all_targets))

    if os.path.isfile(path):
        files = [path]
    else:
        files = []
        for root, _dirs, fnames in os.walk(path):
            if any(part.startswith(".") for part in root.split(os.sep)):
                continue
            for fn in fnames:
                files.append(os.path.join(root, fn))

    hits: dict = {}
    for fp in files:
        try:
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                for lineno, line in enumerate(fh, 1):
                    for m in pattern.finditer(line):
                        hits.setdefault(m.group(0), []).append((fp, lineno))
        except (IsADirectoryError, PermissionError):
            continue

    return {
        "retired_hits": {k: v for k, v in hits.items() if k in RETIRED_MODELS},
        "deprecated_hits": {k: v for k, v in hits.items() if k in DEPRECATED_MODELS},
    }


def _walk_upgrade_candidates(path: str):
    if os.path.isfile(path):
        yield path
        return
    for root, dirs, fnames in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in fnames:
            if fn.endswith(".bak"):
                continue
            yield os.path.join(root, fn)


def upgrade_all(path: str, target: str = "fable5", apply: bool = False, no_backup: bool = False) -> dict:
    """Rewrite every known Claude model ID under `path` to `target`
    (one of UPGRADE_TARGETS' keys — currently 'fable5', 'opus', 'opus5',
    'sonnet5'). Dry-run (report only) unless apply=True.
    Returns {'error': str} on an unknown target, else
    {'target_id': str, 'total_hits': int, 'per_file_report': [(file,
    {id: count})...], 'files_changed': int, 'applied': bool}."""
    if target not in UPGRADE_TARGETS:
        return {"error": f"Unknown upgrade target '{target}'. Choose from: " f"{', '.join(UPGRADE_TARGETS)}"}

    target_id = UPGRADE_TARGETS[target]
    old_ids = _upgrade_source_ids(target_id)
    pattern = re.compile(r"(?<![\w-])(" + "|".join(re.escape(i) for i in old_ids) + r")(?![\w-])")

    files_changed = 0
    total_hits = 0
    per_file_report = []

    for fp in _walk_upgrade_candidates(path):
        try:
            with open(fp, encoding="utf-8", errors="strict") as fh:
                text = fh.read()
        except (UnicodeDecodeError, PermissionError, IsADirectoryError):
            continue  # binary / unreadable — skip rather than risk corrupting it

        matches = pattern.findall(text)
        if not matches:
            continue

        counts: dict = {}
        for m in matches:
            counts[m] = counts.get(m, 0) + 1
        per_file_report.append((fp, counts))
        total_hits += len(matches)

        if apply:
            new_text = pattern.sub(target_id, text)
            if not no_backup:
                with open(fp + ".bak", "w", encoding="utf-8") as bak:
                    bak.write(text)
            with open(fp, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            files_changed += 1

    return {
        "target_id": target_id,
        "total_hits": total_hits,
        "per_file_report": per_file_report,
        "files_changed": files_changed,
        "applied": apply,
    }


def run_computer_use(task: str, api_key: str, model: str) -> dict:
    """{'text': str, 'tool_calls': [...]} from ComputerUseCoder.run_task()."""
    cu = ComputerUseCoder(api_key=api_key, model=model)
    return cu.run_task(task)


def run_adaptive_thinking(
    prompt: str, api_key: str, model: str, effort: str = "medium", budget: int | None = None
) -> str:
    atc = AdaptiveThinkingCoder(api_key=api_key, model=model)
    return atc.adaptive(prompt, budget=budget or 8000, effort=effort)
