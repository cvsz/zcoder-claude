"""
# mypy: ignore-errors
interfaces/cli/commands/wrapper_commands.py — CLI presentation for the model-specific wrappers
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Presentation layer for claude_fable5.py / claude_mythos5.py /
claude_opus5.py / claude_haiku45.py / claude_sonnet5.py /
claude_response_metadata.py's CLI surface: every function here formats
and print()s output. All HTTP lives in infrastructure/anthropic_api/
model_wrappers_gateway.py (reached only through application/
models_service.py); the pure info tables, validators, and pricing
helpers live in domain/model_wrappers.py. Output text is byte-identical
to the pre-migration cmd_* bodies.
"""

from datetime import date

from application.models_service import (
    fable5_call,
    haiku45_call,
    mythos5_call,
    opus5_call,
    sonnet5_call,
    whoami_metadata,
)
from domain.model_wrappers import (
    FABLE_MYTHOS_INFO,
    HAIKU45_INFO,
    HAIKU45_MODEL_ID,
    MYTHOS5_MODEL_ID,
    OPUS5_INFO,
    OPUS5_MODEL_ID,
    PROMO_END_DATE,
    SONNET5_INFO,
    SONNET5_MODEL_ID,
    MythosAccessError,
    RefusalError,
    current_pricing,
)
from domain.model_wrappers import (
    estimate_sonnet5_cost_usd as estimate_cost_usd,
)
from exceptions import AICoderError

# ── Fable 5 / Mythos 5 ───────────────────────────────────────────────────


def cmd_fable5_info():
    print("\n\033[94mClaude Fable 5 / Claude Mythos 5\033[0m")
    print("\033[93m⚠ Sourced from recent web search results, not this CLI's own bundled\033[0m")
    print("\033[93m  product data — verify at platform.claude.com/docs before relying on\033[0m")
    print("\033[93m  pricing/availability for anything billing-sensitive.\033[0m\n")
    for model_id, info in FABLE_MYTHOS_INFO.items():
        print(f"  \033[1m{info['display_name']}\033[0m  ({model_id})")
        print(f"    Class:            {info['class']}")
        print(f"    Context window:   {info['context_window']:,} tokens")
        print(f"    Max output:       {info['max_output_tokens']:,} tokens")
        print(
            f"    Pricing:          ${info['price_input_per_mtok_usd']}/MTok in, "
            f"${info['price_output_per_mtok_usd']}/MTok out"
        )
        print(f"    Data retention:   {info['data_retention']}")
        print(
            f"    Safety classifiers: {'yes (can refuse, see fallback)' if info['has_safety_classifiers'] else 'no'}"
        )
        print(f"    Notes:            {info['notes']}")
        print()


def cmd_fable5_call(
    prompt: str,
    api_key: str,
    fallback_model: str = "claude-opus-4-8",
    allow_fallback: bool = True,
    system: str | None = None,
    fallback_chain: list | None = None,
):
    try:
        result = fable5_call(
            prompt,
            api_key,
            fallback_model=fallback_model,
            allow_fallback=allow_fallback,
            system=system,
            fallback_chain=fallback_chain,
        )
    except RefusalError as e:
        print(f"\033[91m✗ {e}\033[0m")
        return None

    if result["fell_back"]:
        served_by = result.get("served_by") or fallback_model
        mode = "server-side fallbacks" if fallback_chain else "client-side manual retry"
        print(
            f"\033[93mℹ Fable 5 declined this request (classifier: {result['classifier'] or 'unspecified'}); "
            f"showing the {served_by} response instead ({mode}).\033[0m\n"
        )
    print(result["text"])
    return result


def cmd_mythos5_info():
    info = FABLE_MYTHOS_INFO[MYTHOS5_MODEL_ID]
    print("\n\033[94mClaude Mythos 5\033[0m")
    print("\033[93m⚠ Sourced from the same uncertain web search results as claude_fable5.py.\033[0m")
    print("\033[93m  Access is described as limited/approval-gated (Project Glasswing) —\033[0m")
    print("\033[93m  most accounts will not have this. Verify before relying on anything below.\033[0m\n")
    print(f"    Class:            {info['class']}")
    print(f"    Context window:   {info['context_window']:,} tokens")
    print(f"    Max output:       {info['max_output_tokens']:,} tokens")
    print(
        f"    Pricing:          ${info['price_input_per_mtok_usd']}/MTok in, "
        f"${info['price_output_per_mtok_usd']}/MTok out"
    )
    print(f"    Data retention:   {info['data_retention']}")
    print("    Safety classifiers: no (unlike Fable 5 — see claude_fable5.py)")
    print(f"    Notes:            {info['notes']}")
    print("\n  To request access: contact your Anthropic, AWS, or Google Cloud account team")
    print("  about Project Glasswing. See also: --fable5-info for the publicly available sibling model.\n")


def cmd_mythos5_call(prompt: str, api_key: str, system: str | None = None):
    try:
        text = mythos5_call(prompt, api_key, system=system)
    except MythosAccessError as e:
        print(f"\033[91m✗ {e}\033[0m")
        return None
    print(text)
    return text


# ── Opus 5 ───────────────────────────────────────────────────────────────


def cmd_opus5_info():
    info = OPUS5_INFO
    print(f"\n\033[94mClaude Opus 5\033[0m  ({OPUS5_MODEL_ID})")
    print(f"  Launched:          {info['launched']}")
    print(f"  Context window:    {info['context_window']:,} tokens")
    print(f"  Max output:        {info['max_output_tokens']:,} tokens")
    print(
        f"  Pricing:           ${info['price_input_per_mtok_usd']}/MTok in, "
        f"${info['price_output_per_mtok_usd']}/MTok out"
    )
    print(f"  Thinking default:  {info['thinking_default']}")
    print(f"  Effort ladder:     {', '.join(info['effort_levels'])}")
    print(f"  Fast mode:         {'supported' if info['fast_mode_supported'] else 'not supported'}")
    print(f"  Priority Tier:     {'supported' if info['service_tier_supported'] else 'not supported'}")
    print(
        f"  Data residency:    {'supported' if info['inference_geo_supported'] else 'unconfirmed — see module notes'}"
    )
    print("\n  \033[93m⚠ Breaking change vs Opus 4.8:\033[0m thinking can only be disabled")
    print("    at effort high or below. --opus5-disable-thinking + --opus5-effort")
    print("    xhigh/max is rejected client-side here rather than sent as a 400.")
    print(f"\n  Notes: {info['notes']}\n")


def cmd_opus5_call(
    prompt: str,
    api_key: str,
    effort: str | None = None,
    disable_thinking: bool = False,
    fast: bool = False,
    use_geo: bool = False,
    system: str | None = None,
):
    try:
        data = opus5_call(
            prompt,
            api_key,
            effort=effort,
            disable_thinking=disable_thinking,
            fast=fast,
            use_geo=use_geo,
            system=system,
        )
    except ValueError as e:
        print(f"\033[91m✗ {e}\033[0m")
        return None

    if "error" in data:
        print(f"[ERROR] {data['error']}")
        return None
    if data.get("_geo_warning"):
        print(f"\033[93mℹ {data['_geo_warning']}\033[0m\n")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    print(text)
    return data


# ── Haiku 4.5 ────────────────────────────────────────────────────────────


def cmd_haiku45_info():
    info = HAIKU45_INFO
    print(f"\n\033[94mClaude Haiku 4.5\033[0m  ({HAIKU45_MODEL_ID}, alias: {info['alias']})")
    print(f"  Context window:    {info['context_window']:,} tokens")
    print(f"  Max output:        {info['max_output_tokens']:,} tokens")
    print(
        f"  Pricing:           ${info['price_input_per_mtok_usd']}/MTok in, "
        f"${info['price_output_per_mtok_usd']}/MTok out"
    )
    print(f"  Thinking:          {info['thinking']}")
    print(
        f"  Fast mode:         {'supported' if info['fast_mode_supported'] else 'NOT supported (Opus-only)'}"
    )
    print(f"  Priority Tier:     {'supported' if info['service_tier_supported'] else 'not supported'}")
    print(f"  Data residency:    {'supported' if info['inference_geo_supported'] else 'NOT supported'}")
    print(f"\n  Notes: {info['notes']}\n")


def cmd_haiku45_call(
    prompt: str,
    api_key: str,
    thinking_budget: int | None = None,
    fast: bool = False,
    use_geo: bool = False,
    system: str | None = None,
):
    try:
        data = haiku45_call(prompt, api_key, thinking_budget=thinking_budget, fast=fast, use_geo=use_geo, system=system)
    except ValueError as e:
        print(f"\033[91m✗ {e}\033[0m")
        return None
    if "error" in data:
        print(f"[ERROR] {data['error']}")
        return None
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    print(text)
    return data


# ── Sonnet 5 ─────────────────────────────────────────────────────────────


def cmd_sonnet5_info():
    info = SONNET5_INFO
    pricing = current_pricing()
    print(f"\n\033[94mClaude Sonnet 5\033[0m  ({SONNET5_MODEL_ID})")
    print(f"  Context window:    {info['context_window']:,} tokens")
    print(f"  Max output:        {info['max_output_tokens']:,} tokens")
    print(f"  Thinking:          {info['thinking']} (effort default: {info['effort_default']})")
    print(f"  Priority Tier:     {'supported' if info['service_tier_supported'] else 'NOT supported'}")
    print(
        f"  Data residency:    {'supported' if info['inference_geo_supported'] else 'not supported'}"
        f" ({info['inference_geo_multiplier']}x pricing when used)"
    )
    print(f"\n  Pricing today ({date.today().isoformat()}):")
    print(
        f"    ${pricing['price_in']}/${pricing['price_out']} per MTok "
        f"(standard price — was introductory through {PROMO_END_DATE.isoformat()}, "
        f"but Anthropic confirmed 2026-08-10 the scheduled increase to $3/$15 "
        f"will not happen, so this is now permanent)"
    )
    print(f"\n  Notes: {info['notes']}\n")


def cmd_sonnet5_call(
    prompt: str,
    api_key: str,
    use_geo: bool = False,
    service_tier: str | None = None,
    system: str | None = None,
):
    data = sonnet5_call(prompt, api_key, use_geo=use_geo, service_tier=service_tier, system=system)
    if "error" in data:
        print(f"[ERROR] {data['error']}")
        return None
    if data.get("_service_tier_warning"):
        print(f"\033[93mℹ {data['_service_tier_warning']}\033[0m\n")
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    print(text)
    return data


def cmd_sonnet5_cost(spec: str):
    """Parse 'IN,OUT' token counts and print a cost estimate at today's rate."""
    try:
        in_tok, out_tok = (int(x.strip()) for x in spec.split(","))
    except ValueError:
        print("[ERROR] --sonnet5-cost expects 'INPUT_TOKENS,OUTPUT_TOKENS', e.g. 10000,2000")
        return
    cost = estimate_cost_usd(in_tok, out_tok)
    pricing = current_pricing()
    print(f"\n  {in_tok:,} input + {out_tok:,} output tokens on Sonnet 5")
    print(
        f"  at today's standard rate (${pricing['price_in']}/${pricing['price_out']} per MTok): "
        f"\033[1m${cost:.4f}\033[0m\n"
    )


# ── Response metadata (--whoami) ─────────────────────────────────────────


def cmd_whoami(api_key: str):
    try:
        meta = whoami_metadata(api_key)
    except AICoderError as e:
        print(f"[ERROR] {e.message}")
        return None
    print("\n\033[94mResponse metadata\033[0m (from a minimal Messages API call)")
    print(f"  Workspace ID:     {meta.workspace_id or '(none returned)'}")
    print(f"  Organization ID:  {meta.organization_id or '(none returned)'}")
    if not meta.workspace_id:
        print(
            "\033[90m  No anthropic-workspace-id header — this key/token may predate the "
            "2026-08-11 rollout, or you're hitting a non-Claude-API endpoint.\033[0m"
        )
    print()
    return meta
