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

Pricing note (2026-08-21): Anthropic's canonical Pricing and Sonnet 5
migration pages both state that $2/$10 per MTok applies through 2026-08-31
and $3/$15 starts 2026-09-01. Sonnet 5 therefore uses an explicit effective-
date schedule below instead of a timeless price literal. Every other module
should continue to delegate pricing to this module.
"""

from datetime import date

SONNET5_STANDARD_PRICE_DATE = date(2026, 9, 1)
SONNET5_INTRO_PRICE = {"in": 2.0, "out": 10.0}
SONNET5_STANDARD_PRICE = {"in": 3.0, "out": 15.0}


def sonnet5_price(as_of: date | None = None) -> dict:
    """Return the documented Sonnet 5 price effective on ``as_of``.

    Anthropic currently documents introductory $2/$10 pricing through
    2026-08-31 and standard $3/$15 pricing beginning 2026-09-01.
    ``as_of`` exists primarily so tests and historical reports can be
    deterministic instead of depending on the machine clock.
    """
    effective = as_of or date.today()
    price = SONNET5_STANDARD_PRICE if effective >= SONNET5_STANDARD_PRICE_DATE else SONNET5_INTRO_PRICE
    return dict(price)


MODEL_CATALOG: dict = {
    "claude-opus-5": {
        "display_name": "Claude Opus 5",
        "tier": "current",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": 5.0,
        "price_out": 25.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Launched 2026-07-24, a step-change over Opus 4.8 at the same "
        "price. Thinking on by default. Full effort ladder (low/medium/"
        "high/xhigh/max). Breaking change vs. Opus 4.8: disabling thinking "
        "(thinking.type='disabled') is only allowed at effort high or "
        "below -- xhigh or max with thinking disabled returns a 400.",
    },
    "claude-mythos-5": {
        "display_name": "Claude Mythos 5",
        "tier": "mythos",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": 10.0,
        "price_out": 50.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Same underlying model as Fable 5, no safety classifiers. "
        "Project Glasswing invitation-only access.",
    },
    "claude-fable-5": {
        "display_name": "Claude Fable 5",
        "tier": "mythos",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": 10.0,
        "price_out": 50.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Anthropic's most capable widely-released model. Thinking is "
        "always on and returned encrypted — omit `thinking` rather "
        'than passing type:"disabled" (that returns a 400). Has '
        'safety classifiers that can return stop_reason="refusal".',
    },
    "claude-opus-4-8": {
        "display_name": "Claude Opus 4.8",
        "tier": "current",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": 5.0,
        "price_out": 25.0,
        "thinking": "adaptive",
        "effort_default": "high",
        "notes": "Best for complex agentic coding and enterprise work. "
        "Adaptive thinking only — manual budget_tokens returns 400.",
    },
    "claude-sonnet-5": {
        "display_name": "Claude Sonnet 5",
        "tier": "current",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": sonnet5_price()["in"],
        "price_out": sonnet5_price()["out"],
        "thinking": "adaptive",
        "effort_default": "high",
        "notes": "Best speed/intelligence balance; builds on Sonnet 4.6. "
        "$2/$10 per MTok through 2026-08-31; $3/$15 per MTok starting "
        "2026-09-01 per Anthropic Pricing and Sonnet 5 migration docs.",
    },
    "claude-haiku-4-5-20251001": {
        "display_name": "Claude Haiku 4.5",
        "tier": "current",
        "context_window": 200_000,
        "max_output": 64_000,
        "price_in": 1.0,
        "price_out": 5.0,
        "thinking": "extended",
        "effort_default": None,
        "notes": "Fastest, most cost-effective. Extended (manual budget_tokens) "
        "thinking, not adaptive. Alias: claude-haiku-4-5.",
    },
    "claude-opus-4-7": {
        "display_name": "Claude Opus 4.7",
        "tier": "legacy",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": 5.0,
        "price_out": 25.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Superseded by Opus 4.8 (drop-in model-ID swap).",
    },
    "claude-opus-4-6": {
        "display_name": "Claude Opus 4.6",
        "tier": "legacy",
        "context_window": 1_000_000,
        "max_output": 128_000,
        "price_in": 5.0,
        "price_out": 25.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Superseded by Opus 4.7 / 4.8.",
    },
    "claude-opus-4-5": {
        "display_name": "Claude Opus 4.5",
        "tier": "legacy",
        "context_window": 1_000_000,
        "max_output": 64_000,
        "price_in": 5.0,
        "price_out": 25.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Superseded by later Opus releases.",
    },
    "claude-sonnet-4-6": {
        "display_name": "Claude Sonnet 4.6",
        "tier": "legacy",
        "context_window": 1_000_000,
        "max_output": 64_000,
        "price_in": 3.0,
        "price_out": 15.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Superseded by Sonnet 5.",
    },
    "claude-sonnet-4-5": {
        "display_name": "Claude Sonnet 4.5",
        "tier": "legacy",
        "context_window": 1_000_000,
        "max_output": 64_000,
        "price_in": 3.0,
        "price_out": 15.0,
        "thinking": "adaptive",
        "effort_default": None,
        "notes": "Superseded by Sonnet 4.6 / 5.",
    },
}

TIER_ORDER = ["mythos", "current", "legacy"]

FAST_MODE_SUPPORTED = {"claude-opus-5", "claude-opus-4-8"}
FAST_MODE_REMOVED_ERROR = {"claude-opus-4-7"}
FAST_MODE_REMOVED_SILENT = {"claude-opus-4-6"}


def validate_fast_mode(model_id: str) -> str | None:
    if model_id in FAST_MODE_REMOVED_ERROR:
        return (
            f"fast mode was removed for {model_id} on 2026-07-24 and now "
            f"returns an error (unlike Opus 4.6, it does not fall back to "
            f"standard speed) -- use claude-opus-5 or claude-opus-4-8 instead"
        )
    if model_id in FAST_MODE_REMOVED_SILENT:
        return (
            f"fast mode was removed for {model_id} on 2026-06-29 -- the "
            f"request will run at standard speed and standard pricing, "
            f"not fast, with no error"
        )
    if model_id not in FAST_MODE_SUPPORTED:
        return f"fast mode is not supported on {model_id}"
    return None


SERVICE_TIER_UNSUPPORTED = {"claude-sonnet-5", "claude-mythos-preview", "claude-mythos-5"}

INFERENCE_GEO_SUPPORTED = {
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-fable-5",
    "claude-mythos-5",
    "claude-mythos-preview",
}
INFERENCE_GEO_PRICING_MULTIPLIER = 1.1

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
        "notes": "Retired well before this catalog's other entries; flagged in case of very old pinned config.",
    },
    "claude-opus-4-1-20250805": {
        "display_name": "Claude Opus 4.1",
        "retired": "2026-08-05",
        "replacement": "claude-opus-4-8",
        "notes": "Retired 2026-08-05; requests to this model ID now error.",
    },
}


def check_retired(model_id: str) -> dict | None:
    return RETIRED_MODELS.get(model_id)


DEPRECATED_MODELS: dict = {}


def check_deprecated(model_id: str) -> dict | None:
    return DEPRECATED_MODELS.get(model_id)


UPGRADE_TARGETS = {
    "fable5": "claude-fable-5",
    "opus": "claude-opus-4-8",
    "opus5": "claude-opus-5",
    "sonnet5": "claude-sonnet-5",
}

MODEL_ID_ALIASES = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}


def _upgrade_source_ids(target_id: str) -> list:
    ids = (
        set(RETIRED_MODELS.keys())
        | set(MODEL_CATALOG.keys())
        | set(MODEL_ID_ALIASES.keys())
        | set(DEPRECATED_MODELS.keys())
    )
    ids.discard(target_id)
    return sorted(ids, key=len, reverse=True)


PRICE: dict = {
    model_id: {"in": info["price_in"], "out": info["price_out"]} for model_id, info in MODEL_CATALOG.items()
}
PRICE.update(
    {
        "claude-opus-4-7": {"in": 5.0, "out": 25.0},
        "claude-opus-4-6": {"in": 5.0, "out": 25.0},
        "claude-opus-4-5": {"in": 5.0, "out": 25.0},
        "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
        "claude-sonnet-4-5": {"in": 3.0, "out": 15.0},
    }
)
DEFAULT_PRICE = {"in": 3.0, "out": 15.0}


def get_price(model_id: str, as_of: date | None = None) -> dict:
    """Return input/output $/MTok, honoring date-effective Sonnet 5 pricing."""
    if model_id == "claude-sonnet-5":
        return sonnet5_price(as_of)
    return PRICE.get(model_id, DEFAULT_PRICE)


LONG_CONTEXT_SURCHARGE: dict = {
    "claude-sonnet-4-5": {"threshold": 200_000, "in_mult": 2.0, "out_mult": 1.5},
}

INFERENCE_GEO_MULTIPLIER = 1.1
INFERENCE_GEO_PRICING_MULTIPLIER = INFERENCE_GEO_MULTIPLIER


def estimate_cost_usd(
    model_id: str,
    in_tokens: int,
    out_tokens: int,
    inference_geo: str = "global",
    as_of: date | None = None,
) -> float:
    """Canonical cost estimator with date-effective Sonnet 5 pricing."""
    p = get_price(model_id, as_of=as_of)
    surcharge = LONG_CONTEXT_SURCHARGE.get(model_id)
    if surcharge and in_tokens > surcharge["threshold"]:
        in_price, out_price = p["in"] * surcharge["in_mult"], p["out"] * surcharge["out_mult"]
    else:
        in_price, out_price = p["in"], p["out"]
    if inference_geo == "us" and model_id in INFERENCE_GEO_SUPPORTED:
        in_price *= INFERENCE_GEO_MULTIPLIER
        out_price *= INFERENCE_GEO_MULTIPLIER
    return in_tokens / 1e6 * in_price + out_tokens / 1e6 * out_price
