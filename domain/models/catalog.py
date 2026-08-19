"""
domain/models/catalog.py — Model catalog: capabilities, pricing, retirement/deprecation state
AI Model Coder CLI v1.41.0 (Clean Architecture refactor)

This is the SINGLE SOURCE OF TRUTH for model IDs, pricing, and lifecycle
state (retired / deprecated). Extracted 2026-08-14 from claude_models.py as
part of a Clean Architecture refactor.

Why this module is domain, not infrastructure: everything here is pure data
and pure functions with zero I/O — no HTTP calls, no file writes, no
`print()`. It has no dependency on `resilience.py`, `anthropic`, or any
transport concern, so it can be imported and unit-tested without mocking a
network call, and swapped underneath any presentation layer (CLI, web,
future integrations) without those layers needing to agree on anything but
this module's public names.

This consolidation directly fixes a real bug class found in the 2026-08-14
release-gate audit: Claude Sonnet 5's price was duplicated across FOUR
separate files (claude_models.py, claude_cost_optimizer.py,
claude_metrics.py, claude_sonnet5.py) and went stale in three of them
simultaneously when Anthropic's pricing changed. Every other module in this
codebase should import PRICE / MODEL_CATALOG / RETIRED_MODELS from HERE —
none should keep a local copy.

For live-account model info (context window/capabilities as your account's
API key actually sees them right now), see
infrastructure/anthropic_api/models_gateway.py's ModelsAPI — that is the
authoritative *live* source; this module is the offline convenience
cache + lifecycle registry.
"""

from typing import Optional

MODEL_CATALOG: dict = {
    "claude-opus-5": {
        "display_name": "Claude Opus 5", "tier": "current",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 5.0, "price_out": 25.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Launched 2026-07-24, a step-change over Opus 4.8 at the same "
                 "price. Thinking on by default. Full effort ladder (low/medium/"
                 "high/xhigh/max). Breaking change vs. Opus 4.8: disabling thinking "
                 "(thinking.type='disabled') is only allowed at effort high or "
                 "below -- xhigh or max with thinking disabled returns a 400.",
    },
    "claude-mythos-5": {
        "display_name": "Claude Mythos 5", "tier": "mythos",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 10.0, "price_out": 50.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Same underlying model as Fable 5, no safety classifiers. "
                 "Project Glasswing invitation-only access.",
    },
    "claude-fable-5": {
        "display_name": "Claude Fable 5", "tier": "mythos",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 10.0, "price_out": 50.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Anthropic's most capable widely-released model. Thinking is "
                 "always on and returned encrypted — omit `thinking` rather "
                 "than passing type:\"disabled\" (that returns a 400). Has "
                 "safety classifiers that can return stop_reason=\"refusal\".",
    },
    "claude-opus-4-8": {
        "display_name": "Claude Opus 4.8", "tier": "current",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 5.0, "price_out": 25.0,
        "thinking": "adaptive", "effort_default": "high",
        "notes": "Best for complex agentic coding and enterprise work. "
                 "Adaptive thinking only — manual budget_tokens returns 400.",
    },
    "claude-sonnet-5": {
        "display_name": "Claude Sonnet 5", "tier": "current",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 2.0, "price_out": 10.0,
        "thinking": "adaptive", "effort_default": "high",
        "notes": "Best speed/intelligence balance; builds on Sonnet 4.6. "
                 "$2/$10 per MTok is the standard price (was introductory "
                 "through 2026-08-31; Anthropic confirmed 2026-08-10 that the "
                 "scheduled increase to $3/$15 will not occur, so this is now "
                 "permanent, not a promo).",
    },
    "claude-haiku-4-5-20251001": {
        "display_name": "Claude Haiku 4.5", "tier": "current",
        "context_window": 200_000, "max_output": 64_000,
        "price_in": 1.0, "price_out": 5.0,
        "thinking": "extended", "effort_default": None,
        "notes": "Fastest, most cost-effective. Extended (manual budget_tokens) "
                 "thinking, not adaptive. Alias: claude-haiku-4-5.",
    },
    # Legacy — still callable, superseded by the row above in the same tier.
    "claude-opus-4-7": {
        "display_name": "Claude Opus 4.7", "tier": "legacy",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 5.0, "price_out": 25.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Superseded by Opus 4.8 (drop-in model-ID swap).",
    },
    "claude-opus-4-6": {
        "display_name": "Claude Opus 4.6", "tier": "legacy",
        "context_window": 1_000_000, "max_output": 128_000,
        "price_in": 5.0, "price_out": 25.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Superseded by Opus 4.7 / 4.8.",
    },
    "claude-opus-4-5": {
        "display_name": "Claude Opus 4.5", "tier": "legacy",
        "context_window": 1_000_000, "max_output": 64_000,
        "price_in": 5.0, "price_out": 25.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Superseded by later Opus releases.",
    },
    "claude-sonnet-4-6": {
        "display_name": "Claude Sonnet 4.6", "tier": "legacy",
        "context_window": 1_000_000, "max_output": 64_000,
        "price_in": 3.0, "price_out": 15.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Superseded by Sonnet 5.",
    },
    "claude-sonnet-4-5": {
        "display_name": "Claude Sonnet 4.5", "tier": "legacy",
        "context_window": 1_000_000, "max_output": 64_000,
        "price_in": 3.0, "price_out": 15.0,
        "thinking": "adaptive", "effort_default": None,
        "notes": "Superseded by Sonnet 4.6 / 5.",
    },
}

TIER_ORDER = ["mythos", "current", "legacy"]

# ── Fast mode (research preview) ────────────────────────────────────────────
# Was referenced only in this module's docstring/CLI-flag list with no actual
# code path — `--fast-mode` wasn't a real argparse flag anywhere and nothing
# ever sent `speed: "fast"`. Per platform.claude.com/docs (checked
# 2026-07-02): fast mode sends `speed: "fast"` on the request, is currently
# restricted to Opus models, and is billed at a premium rate ($10/$50 per
# MTok on Opus 4.8 vs. its $5/$25 standard rate). Not available on the
# Batch API.
#
# Fast mode's *removal* behavior differs by model, checked against the
# July 24, 2026 and June 29, 2026 release notes:
#   - Opus 4.7 (removed 2026-07-24): speed:"fast" now returns an ERROR.
#     Unlike Opus 4.6, it does NOT fall back to standard speed.
#   - Opus 4.6 (removed 2026-06-29): speed:"fast" is silently ignored --
#     the request runs at standard speed/pricing with no error.
# Both sets used to be represented by a single unused FAST_MODE_DEPRECATED
# constant that nothing ever actually checked against — coder.py sent
# speed:"fast" unconditionally whenever --fast-mode was passed, regardless
# of model. See validate_fast_mode() below, wired into coder.Coder.generate().
FAST_MODE_SUPPORTED = {"claude-opus-5", "claude-opus-4-8"}
FAST_MODE_REMOVED_ERROR = {"claude-opus-4-7"}
FAST_MODE_REMOVED_SILENT = {"claude-opus-4-6"}


def validate_fast_mode(model_id: str) -> Optional[str]:
    """Return None if `speed: "fast"` is safe to send for model_id, or a
    human-readable reason string if it isn't (or won't do what the caller
    expects). Callers should treat FAST_MODE_REMOVED_ERROR as a hard stop
    (don't send the request — it will 400) and FAST_MODE_REMOVED_SILENT as
    a warning (safe to send, but it silently runs at standard speed/price,
    not fast)."""
    if model_id in FAST_MODE_REMOVED_ERROR:
        return (f"fast mode was removed for {model_id} on 2026-07-24 and now "
                f"returns an error (unlike Opus 4.6, it does not fall back to "
                f"standard speed) -- use claude-opus-5 or claude-opus-4-8 instead")
    if model_id in FAST_MODE_REMOVED_SILENT:
        return (f"fast mode was removed for {model_id} on 2026-06-29 -- the "
                f"request will run at standard speed and standard pricing, "
                f"not fast, with no error")
    if model_id not in FAST_MODE_SUPPORTED:
        return f"fast mode is not supported on {model_id}"
    return None

# ── Priority Tier / service_tier ────────────────────────────────────────────
# Was entirely absent from the project. Per platform.claude.com/docs/en/
# api/service-tiers (checked 2026-07-02): service_tier accepts "auto"
# (default — use Priority Tier capacity if your org has a commitment,
# falling back to standard) or "standard_only". Priority Tier capacity
# commitments are no longer available for purchase, but organizations with
# an existing commitment can keep using it through their contract end date.
# Supported on all available models EXCEPT Claude Sonnet 5, Claude Mythos
# Preview, and Claude Mythos 5.
SERVICE_TIER_UNSUPPORTED = {"claude-sonnet-5", "claude-mythos-preview", "claude-mythos-5"}

# ── Data residency / inference_geo ──────────────────────────────────────────
# Also entirely absent. Per platform.claude.com/docs/en/manage-claude/
# data-residency (checked 2026-07-02): inference_geo accepts "us" (inference
# stays in US data centers, 1.1x pricing on input+output) or "global"
# (default, standard pricing). Only supported on Claude Opus 4.6, Sonnet
# 4.6, and later models — earlier models 400 if it's set at all.
INFERENCE_GEO_SUPPORTED = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5", "claude-sonnet-4-6",
    "claude-fable-5", "claude-mythos-5", "claude-mythos-preview",
}
INFERENCE_GEO_PRICING_MULTIPLIER = 1.1


# ── Retired models ──────────────────────────────────────────────────────────
# Unlike MODEL_CATALOG's "legacy" tier (superseded but still callable), these
# IDs now return API errors. Kept here so --model-info on an old pinned
# string gives a migration path instead of a bare 404, and so a codebase
# grep for these strings has a maintained reference for what to replace them
# with. Retirement dates per platform.claude.com/docs/en/about-claude/model-deprecations,
# checked 2026-07-02.
RETIRED_MODELS: dict = {
    "claude-opus-4-20250514": {
        "display_name": "Claude Opus 4 (original 4.0)",
        "retired": "2026-06-15",
        "replacement": "claude-opus-4-8",
        "notes": "Dateless alias claude-opus-4-0 retired alongside it.",
    },
    "claude-opus-4-0": {
        "display_name": "Claude Opus 4 (original 4.0, dateless alias)",
        "retired": "2026-06-15",
        "replacement": "claude-opus-4-8",
        "notes": "Alias for claude-opus-4-20250514.",
    },
    "claude-sonnet-4-20250514": {
        "display_name": "Claude Sonnet 4 (original 4.0)",
        "retired": "2026-06-15",
        "replacement": "claude-sonnet-5",
        "notes": "Dateless alias claude-sonnet-4-0 retired alongside it. Anthropic's "
                 "own migration notes point to claude-sonnet-4-6; claude-sonnet-5 is "
                 "the current recommendation as of this catalog's last check.",
    },
    "claude-sonnet-4-0": {
        "display_name": "Claude Sonnet 4 (original 4.0, dateless alias)",
        "retired": "2026-06-15",
        "replacement": "claude-sonnet-5",
        "notes": "Alias for claude-sonnet-4-20250514.",
    },
    "claude-haiku-3-20240307": {
        "display_name": "Claude Haiku 3",
        "retired": "2026-02-19",
        "replacement": "claude-haiku-4-5-20251001",
        "notes": "Retired well before this catalog's other entries; flagged in case "
                 "of very old pinned config.",
    },
    "claude-opus-4-1-20250805": {
        "display_name": "Claude Opus 4.1",
        "retired": "2026-08-05",
        "replacement": "claude-opus-4-8",
        "notes": "Moved here from DEPRECATED_MODELS 2026-08-14 (release-gate audit): "
                 "its 2026-08-05 retirement date had passed, confirmed against live "
                 "platform.claude.com/docs/en/release-notes/overview. All requests to "
                 "this model ID now return an error; researchers can request ongoing "
                 "access via the External Researcher Access Program.",
    },
}


def check_retired(model_id: str) -> Optional[dict]:
    """Return the retirement record for model_id, or None if it isn't a
    known-retired ID. Matched against RETIRED_MODELS only — an unknown ID
    that isn't in MODEL_CATALOG either is just unrecognized, not retired."""
    return RETIRED_MODELS.get(model_id)


# ── Deprecated (announced, not yet retired) models ──────────────────────────
# Distinct from RETIRED_MODELS: these IDs still work today but Anthropic has
# published a future retirement date for them. Added v1.37.0 after the
# project's own model catalog was found to have no way to represent this
# state at all — check_retired() only covers "already 404s", so an ID like
# claude-opus-4-1-20250805, which was never in MODEL_CATALOG to begin with,
# had nowhere to go even though its retirement is now on the calendar.
# Per platform.claude.com/docs/en/about-claude/model-deprecations, checked
# 2026-07-27.
DEPRECATED_MODELS: dict = {}


def check_deprecated(model_id: str) -> Optional[dict]:
    """Return the deprecation record for model_id if Anthropic has announced
    a future retirement date for it, or None. A model can appear here and
    still work fine today — this is an early-warning check, not a block.
    Once the retirement date passes, move the entry to RETIRED_MODELS
    instead (this dict is not auto-expired)."""
    return DEPRECATED_MODELS.get(model_id)


# ── Upgrade-all metadata (still pure data; the filesystem-walking logic
# that USES this lives in interfaces/cli/commands/model_commands.py) ────

UPGRADE_TARGETS = {
    "fable5": "claude-fable-5",
    "opus":   "claude-opus-4-8",
    # Added 2026-08-17 (audit against live docs, current date 2026-08-17):
    # --upgrade-all had no path to either of the two current-tier
    # flagships released since "opus" was last the newest target —
    # Claude Opus 5 (2026-07-24) and Claude Sonnet 5 (2026-06-xx, now
    # permanently $2/$10 as of the 2026-08-10 pricing confirmation, see
    # this file's PRICE table comment). "opus" is left pointing at
    # claude-opus-4-8 rather than repointed, so existing
    # --upgrade-target opus scripts/CI don't silently change behavior —
    # opus5 is the new, explicit way to target the actual latest Opus.
    "opus5":   "claude-opus-5",
    "sonnet5": "claude-sonnet-5",
}

# Known alternate spellings that aren't literal MODEL_CATALOG/RETIRED_MODELS
# keys but are documented elsewhere in this project as valid — e.g.
# claude_models.py's own MODEL_CATALOG note for claude-haiku-4-5-20251001:
# "Alias: claude-haiku-4-5." Included so --upgrade-all catches the alias
# form too, not just the dated ID.
MODEL_ID_ALIASES = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}


def _upgrade_source_ids(target_id: str) -> list:
    """Every model ID string this project knows about except the target
    itself, longest-first so no shorter alias can partially shadow a
    longer one when both would otherwise match at the same position.
    Includes DEPRECATED_MODELS (v1.37.0) — a still-callable-but-announced
    ID like claude-opus-4-1-20250805 is exactly the kind of reference
    --upgrade-all exists to clear out before it becomes a RETIRED_MODELS
    problem instead."""
    ids = (set(RETIRED_MODELS.keys()) | set(MODEL_CATALOG.keys())
           | set(MODEL_ID_ALIASES.keys()) | set(DEPRECATED_MODELS.keys()))
    ids.discard(target_id)
    return sorted(ids, key=len, reverse=True)


# ── Derived flat pricing table (Dict[model_id] -> {"in": x, "out": y}) ──────
# Kept as a separate derived view (not hand-duplicated) so
# claude_cost_optimizer.py / claude_metrics.py / claude_sonnet5.py can all
# import ONE dict instead of maintaining their own copies — the exact
# duplication pattern that caused the 2026-08-14 pricing bug. Includes
# legacy (still-callable, non-catalog) models that MODEL_CATALOG doesn't
# carry pricing for, so nothing downstream needs a second fallback table.
PRICE: dict = {
    model_id: {"in": info["price_in"], "out": info["price_out"]}
    for model_id, info in MODEL_CATALOG.items()
}
# Legacy models superseded by the catalog above but still callable on
# existing accounts — pricing confirmed against platform.claude.com/docs/en/
# about-claude/pricing, checked 2026-07-02.
PRICE.update({
    "claude-opus-4-7":   {"in": 5.0, "out": 25.0},
    "claude-opus-4-6":   {"in": 5.0, "out": 25.0},
    "claude-opus-4-5":   {"in": 5.0, "out": 25.0},
    "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
    "claude-sonnet-4-5": {"in": 3.0, "out": 15.0},
})
DEFAULT_PRICE = {"in": 3.0, "out": 15.0}


def get_price(model_id: str) -> dict:
    """{'in': $/MTok, 'out': $/MTok} for model_id, or DEFAULT_PRICE if
    unknown. This is the one place "what does this model cost" should be
    answered from — see this module's docstring."""
    return PRICE.get(model_id, DEFAULT_PRICE)


# ── Long-context surcharge (only the old 1M-context BETA models) ───────────
# Per platform.claude.com/docs/en/about-claude/pricing, checked 2026-07-02:
# current-tier models (Opus 4.6+, Sonnet 4.6+, Sonnet 5, Fable 5, Mythos 5)
# get the full 1M context window at FLAT pricing, no surcharge. Only
# claude-sonnet-4-5 (the older context-1m-2025-08-07 beta) still has one:
# 2x input / 1.5x output once the WHOLE request crosses 200K input tokens
# (not just the excess). That beta retires 2026-04-30, after which this
# table should shrink to empty.
LONG_CONTEXT_SURCHARGE: dict = {
    "claude-sonnet-4-5": {"threshold": 200_000, "in_mult": 2.0, "out_mult": 1.5},
}

# ── Data residency (inference_geo) pricing multiplier ───────────────────────
# Single canonical value — claude_models.py used to call this
# INFERENCE_GEO_PRICING_MULTIPLIER and claude_cost_optimizer.py called an
# identical constant INFERENCE_GEO_MULTIPLIER; both names are kept as
# aliases below so neither call site needs to change its imports.
INFERENCE_GEO_MULTIPLIER = 1.1
INFERENCE_GEO_PRICING_MULTIPLIER = INFERENCE_GEO_MULTIPLIER


def estimate_cost_usd(model_id: str, in_tokens: int, out_tokens: int,
                       inference_geo: str = "global") -> float:
    """Canonical cost estimator. Applies the long-context surcharge (if the
    model has one and in_tokens crosses its threshold) and the
    inference_geo multiplier (if requested and the model supports it).
    Every claude_*.py cost-estimation helper should delegate to this
    instead of re-implementing the surcharge/multiplier logic."""
    p = get_price(model_id)
    surcharge = LONG_CONTEXT_SURCHARGE.get(model_id)
    if surcharge and in_tokens > surcharge["threshold"]:
        in_price, out_price = p["in"] * surcharge["in_mult"], p["out"] * surcharge["out_mult"]
    else:
        in_price, out_price = p["in"], p["out"]
    if inference_geo == "us" and model_id in INFERENCE_GEO_SUPPORTED:
        in_price *= INFERENCE_GEO_MULTIPLIER
        out_price *= INFERENCE_GEO_MULTIPLIER
    return in_tokens / 1e6 * in_price + out_tokens / 1e6 * out_price