"""
interfaces/cli/commands/model_commands.py — CLI presentation for model catalog & tools
AI Model Coder CLI v1.43.0 (Clean Architecture refactor)

Presentation layer: every function here formats and print()s output. All
business logic (live-API-with-local-fallback, filesystem scans, rewrite
logic) now lives in application/models_service.py — this file should not
grow any new business rules, only formatting.
"""

import json
import os
import sys

from domain.models.catalog import MODEL_CATALOG
from application.models_service import (
    list_models, get_model_info, scan_for_deprecated_models,
    upgrade_all, run_computer_use, run_adaptive_thinking,
)


def cmd_list_models(api_key: str, include_legacy: bool = False):
    result = list_models(api_key, include_legacy=include_legacy)
    if result["source"] == "live":
        models = result["models"]
        print(f"\n{'MODEL ID':<35}{'DISPLAY NAME':<35}{'CONTEXT'}")
        print("─" * 85)
        for m in models:
            mid  = m.get("id", "")
            name = m.get("display_name", "")[:34]
            ctx  = m.get("context_window", 0)
            ctx_str = f"{ctx//1000}K" if ctx else "—"
            print(f"{mid:<35}{name:<35}{ctx_str}")
        print(f"\n{len(models)} models available")
        return

    # Offline: show the local catalog
    print(f"\n\033[93m⚠ Could not reach Models API: {result['error']}\033[0m")
    print("\nKnown models (local catalog, verify against --model-info when online):")
    for tier, rows in result["tiers"].items():
        label = {"mythos": "Mythos-class (above Opus)", "current": "Current",
                 "legacy": "Legacy (superseded, still callable)"}[tier]
        print(f"\n  \033[1m{label}\033[0m")
        for mid, info in rows:
            ctx = f"{info['context_window']//1000}K"
            print(f"    {mid:<32}{info['display_name']:<24}{ctx:<7}"
                 f"${info['price_in']}/${info['price_out']} per MTok")
    if not result["include_legacy"]:
        print("\n  (legacy models hidden — pass --list-models-legacy to include them)")
    print("\n  Mythos-tier note: Fable 5 and Mythos 5 share the same underlying model;")
    print("  Fable 5 additionally has safety classifiers for bio/cyber/LLM-R&D topics.")
    print("  Both were briefly suspended 2026-06-12 -> 2026-07-01 for US export-control")
    print("  compliance; access is restored. See anthropic.com/news/fable-mythos-access.")
    print("\n  Run --fable5-info / --mythos5-info for pricing, retention, and refusal-handling details.")


def cmd_model_info(model_id: str, api_key: str):
    result = get_model_info(model_id, api_key)
    retired, deprecated = result["retired"], result["deprecated"]

    if retired:
        print(f"\n  \033[91m✗ {model_id} was retired on {retired['retired']}\033[0m")
        print(f"    Was:         {retired['display_name']}")
        print(f"    Migrate to:  {retired['replacement']}")
        print(f"    Notes:       {retired['notes']}")
        print(f"\n  API calls to this ID will fail — this isn't a live lookup, "
              f"just the local retirement record. Continuing to check the live "
              f"API and local catalog below in case the record above is stale:\n")

    if deprecated:
        print(f"\n  \033[93m⚠ {model_id} is deprecated, retiring "
              f"{deprecated['retirement_scheduled']}\033[0m")
        print(f"    Was:            {deprecated['display_name']}")
        print(f"    Announced:      {deprecated['deprecation_announced']}")
        print(f"    Migrate to:     {deprecated['replacement']}")
        print(f"    Notes:          {deprecated['notes']}")
        print(f"\n  Still works today — this is an early warning, not a failure. "
              f"Continuing below:\n")

    if result["live"]:
        m = result["live"]
        print(f"\n  ID:             {m.get('id')}")
        print(f"  Display name:   {m.get('display_name')}")
        print(f"  Context window: {m.get('context_window', 0):,} tokens")
        print(f"  Created:        {m.get('created_at','')[:10]}")
        caps = m.get("capabilities")
        if caps:
            print(f"  Capabilities:")
            print(f"    Vision:              {caps.get('image_input', {}).get('supported')}")
            think = caps.get("thinking", {})
            types = think.get("types", {})
            print(f"    Adaptive thinking:    {types.get('adaptive', {}).get('supported', False)}")
            print(f"    Extended thinking:    {types.get('enabled', {}).get('supported', False)}")
            print(f"    Structured outputs:   {caps.get('structured_outputs', {}).get('supported')}")
            effort = caps.get("effort")
            if effort:
                levels = effort.get("levels") or effort.get("supported_levels")
                default = effort.get("default")
                if levels:
                    print(f"    Effort levels:       {', '.join(levels)}"
                          f"{f' (default: {default})' if default else ''}")
                elif default:
                    print(f"    Effort default:      {default}")
        return

    if result["local_fallback"]:
        info = result["local_fallback"]
        print(f"\n  \033[93m⚠ Live API unreachable — showing local catalog entry\033[0m")
        print(f"  ID:              {info['id']}")
        print(f"  Display name:    {info['display_name']}")
        print(f"  Tier:            {info['tier']}")
        print(f"  Context window:  {info['context_window']:,} tokens")
        print(f"  Max output:      {info['max_output']:,} tokens")
        print(f"  Pricing:         ${info['price_in']}/MTok in, ${info['price_out']}/MTok out")
        print(f"  Thinking mode:   {info['thinking']}")
        if info["effort_default"]:
            print(f"  Effort default:  {info['effort_default']}")
        print(f"  Notes:           {info['notes']}")
        return

    if result["error"]:
        print(f"[ERROR] {result['error']}")
    # else: retired and unrecognized by the live API — already reported above


def cmd_check_deprecated(path: str):
    """Scan a file or directory for retired/deprecated model ID strings
    and report migration targets. See application.models_service
    .scan_for_deprecated_models for the actual scan logic."""
    from domain.models.catalog import RETIRED_MODELS, DEPRECATED_MODELS

    hits = scan_for_deprecated_models(path)
    retired_hits, deprecated_hits = hits["retired_hits"], hits["deprecated_hits"]

    if not retired_hits and not deprecated_hits:
        print(f"\n\033[92m✓ No retired or deprecated model IDs found under {path}\033[0m")
        return

    if retired_hits:
        print(f"\n\033[91m⚠ Retired model IDs found under {path}\033[0m\n")
        for model_id, locations in retired_hits.items():
            rec = RETIRED_MODELS[model_id]
            print(f"  \033[1m{model_id}\033[0m — retired {rec['retired']}, "
                  f"migrate to \033[92m{rec['replacement']}\033[0m")
            for fp, lineno in locations[:5]:
                print(f"    {fp}:{lineno}")
            if len(locations) > 5:
                print(f"    ... and {len(locations) - 5} more")
            print()

    if deprecated_hits:
        print(f"\n\033[93m⚠ Deprecated model IDs found under {path} "
              f"(still work today, retiring soon)\033[0m\n")
        for model_id, locations in deprecated_hits.items():
            rec = DEPRECATED_MODELS[model_id]
            print(f"  \033[1m{model_id}\033[0m — retiring "
                  f"{rec['retirement_scheduled']}, migrate to "
                  f"\033[92m{rec['replacement']}\033[0m")
            for fp, lineno in locations[:5]:
                print(f"    {fp}:{lineno}")
            if len(locations) > 5:
                print(f"    ... and {len(locations) - 5} more")
            print()


def cmd_upgrade_all(path: str, target: str = "fable5", apply: bool = False,
                    no_backup: bool = False):
    """Rewrite every known Claude model ID under `path` to the chosen
    target. See application.models_service.upgrade_all for the actual
    rewrite logic."""
    result = upgrade_all(path, target=target, apply=apply, no_backup=no_backup)

    if "error" in result:
        print(f"[ERROR] {result['error']}")
        return

    if not result["per_file_report"]:
        print(f"\n\033[92m✓ No known model IDs found under {path} — nothing to upgrade\033[0m")
        return

    verb = "Upgraded" if apply else "Would upgrade"
    print(f"\n\033[94mℹ {verb} {result['total_hits']} model reference(s) across "
          f"{len(result['per_file_report'])} file(s) to \033[1m{result['target_id']}\033[0m\n")
    for fp, counts in result["per_file_report"]:
        detail = ", ".join(f"{mid} ×{n}" for mid, n in sorted(counts.items()))
        print(f"  {fp}: {detail}")

    if apply:
        backup_note = "" if no_backup else " (.bak backup written alongside each changed file)"
        print(f"\n\033[92m✓ {result['files_changed']} file(s) updated{backup_note}\033[0m")
    else:
        print(f"\n\033[93m⚠ Dry run — no files were changed. Re-run with --upgrade-yes to "
              f"apply (add --upgrade-no-backup to skip .bak files).\033[0m")


# ── Computer Use ───────────────────────────────────────────────────────────

def cmd_computer_use(task: str, api_key: str, model: str):
    print(f"\033[94mℹ Computer Use mode\033[0m")
    print(f"\033[93m⚠ Note: Actual execution requires a virtual display environment.\033[0m\n")
    result = run_computer_use(task, api_key, model)
    print(result["text"])
    if result["tool_calls"]:
        print(f"\n\033[90m── Tool calls planned ─────────────────\033[0m")
        for tc in result["tool_calls"]:
            print(f"  {tc['name']}: {json.dumps(tc['input'])[:120]}")
    return result


# ── Adaptive + Interleaved Thinking ───────────────────────────────────────

def cmd_adaptive_thinking(prompt: str, api_key: str, model: str,
                           effort: str = "medium", budget: int = None):
    print(f"\033[94mℹ Adaptive Thinking | effort={effort}\033[0m\n")
    result = run_adaptive_thinking(prompt, api_key, model, effort=effort, budget=budget)
    print(result)
    return result
