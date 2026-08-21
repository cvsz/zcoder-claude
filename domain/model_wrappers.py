"""
domain/model_wrappers.py — Model-specific wrapper domain layer
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Pure data + pure functions for the bounded context covering
claude_fable5.py, claude_mythos5.py, claude_opus5.py, claude_haiku45.py,
claude_sonnet5.py, and claude_response_metadata.py. No I/O, no print(),
no `import urllib.request` here — those all belong to
infrastructure/anthropic_api/model_wrappers_gateway.py.

Six genuinely model-specific concerns share one domain module because
they share one application service (`application/models_service.py`)
per §3's bounded-context table — grouped by source module with a section
header, not merged together.

Pricing note: every price below reads domain/models/catalog.py's PRICE
table instead of carrying its own literal — this file inherits the fix
already applied to the flat modules during the Phase B wrapper-folding
pass (§0/§9 of the master exec plan).

Naming note: the six flat modules each exported a same-named
`estimate_cost_usd` (and Opus 5 / Haiku 4.5 both had a
`validate_inference_geo` with model-specific bodies), which cannot coexist
in one shared module. The per-model variants are disambiguated here
(estimate_fable_mythos_cost_usd / estimate_opus5_cost_usd /
estimate_haiku45_cost_usd / estimate_sonnet5_cost_usd;
validate_opus5_inference_geo / validate_haiku45_inference_geo); the
original claude_*.py compatibility shims re-export each under its old
name so no caller breaks.
"""

from datetime import date

from domain.models.catalog import (
    FAST_MODE_SUPPORTED,
    INFERENCE_GEO_PRICING_MULTIPLIER,
    INFERENCE_GEO_SUPPORTED,
    SERVICE_TIER_UNSUPPORTED,
)
from domain.models.catalog import (
    PRICE as _CATALOG_PRICE,
)

# Shared by every per-model Messages API client in this bounded context.
MESSAGES_ENDPOINT = "https://api.anthropic.com/v1/messages"


# ── fable/mythos (claude_fable5.py) ──────────────────────────────────────

FABLE5_MODEL_ID = "claude-fable-5"
MYTHOS5_MODEL_ID = "claude-mythos-5"

# Verified against platform.claude.com/docs/en/build-with-claude/refusals-and-fallback
# (checked 2026-07-04). We build the retry ourselves with raw urllib rather than an
# SDK, so this is the "manual" fallback path the docs describe — sending this beta
# header on the retry earns fallback credit (refunds the prompt-cache cost of
# switching models) instead of paying that cost twice.
FALLBACK_CREDIT_BETA_HEADER = "fallback-credit-2026-06-01"

# Added 2026-07-24: `fallbacks` also accepts the literal string "default"
# instead of an explicit model list, applying Anthropic's own recommended
# fallback models by refusal category. Per the July 24, 2026 release note,
# this mode specifically requires this beta header (an explicit list does
# not, per the 2026-07-04 check above FALLBACK_CREDIT_BETA_HEADER).
SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER = "server-side-fallback-2026-07-01"

# The stop_details.category values Anthropic actually documents for a Fable 5
# refusal. `category` (and `explanation`) can legitimately be null even when
# stop_reason == "refusal" — that's a documented, permanent state, not a bug.
REFUSAL_CATEGORIES = {
    "cyber": "Could enable cyber harm (e.g. malware/exploit development); benign security work can also trigger it.",
    "bio": "Could enable biological harm; benign life-sciences work can also trigger it.",
    "frontier_llm": "Could assist a competing AI model's development (restricted under Anthropic's commercial terms).",
    "reasoning_extraction": "Asks the model to reproduce its internal reasoning as response text; use adaptive thinking instead.",
}

# Mirrors claude_models.py's "known models" fallback pattern — a local
# cache for when the live Models API isn't consulted, not a source of truth.
# Pricing fields below read domain/models/catalog.py's PRICE table instead
# of carrying their own literals — found 2026-08-15 during the Phase B
# wrapper-folding pass (§0/§9 of the master exec plan): the flat wrapper
# modules each had a local price_input_per_mtok_usd literal duplicating the
# catalog, the same anti-pattern already fixed once for claude_sonnet5.py.
FABLE_MYTHOS_INFO = {
    FABLE5_MODEL_ID: {
        "display_name": "Claude Fable 5",
        "class": "Mythos-class (publicly available)",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "price_input_per_mtok_usd": _CATALOG_PRICE[FABLE5_MODEL_ID]["in"],
        "price_output_per_mtok_usd": _CATALOG_PRICE[FABLE5_MODEL_ID]["out"],
        "cache_write_discount_note": "90% input-token discount applies for prompt caching, per Anthropic's standard caching pricing",
        "data_retention": "30-day retention required for safety monitoring; not available under zero data retention",
        "has_safety_classifiers": True,
        "us_only_inference_multiplier": INFERENCE_GEO_PRICING_MULTIPLIER,
        "notes": "Refuses certain cybersecurity/biology/chemistry queries via stop_reason='refusal' "
        "and can fall back to a less-restricted model server-side (beta `fallbacks` param) "
        "or client-side (this module's call_with_fallback).",
    },
    MYTHOS5_MODEL_ID: {
        "display_name": "Claude Mythos 5",
        "class": "Mythos-class (limited availability — Project Glasswing)",
        "context_window": 1_000_000,
        "max_output_tokens": 128_000,
        "price_input_per_mtok_usd": _CATALOG_PRICE[MYTHOS5_MODEL_ID]["in"],
        "price_output_per_mtok_usd": _CATALOG_PRICE[MYTHOS5_MODEL_ID]["out"],
        "cache_write_discount_note": "90% input-token discount applies for prompt caching, per Anthropic's standard caching pricing",
        "data_retention": "30-day retention required; not available under zero data retention",
        "has_safety_classifiers": False,
        "us_only_inference_multiplier": None,
        "notes": "Same underlying capability as Fable 5 without the safety classifiers. "
        "Requires approved access via Project Glasswing — contact your Anthropic, "
        "AWS, or Google Cloud account team. Most callers will not have this and "
        "should use Fable 5 instead.",
    },
}


class RefusalError(Exception):
    """Raised when a Fable 5 call is refused and fallback is disabled/exhausted."""

    def __init__(self, message: str, classifier: str | None = None):
        super().__init__(message)
        self.classifier = classifier


def estimate_fable_mythos_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float | None:
    """Rough cost estimate using the static table above. Returns None for unknown models."""
    info = FABLE_MYTHOS_INFO.get(model_id)
    if not info:
        return None
    return (
        input_tokens / 1_000_000 * info["price_input_per_mtok_usd"]
        + output_tokens / 1_000_000 * info["price_output_per_mtok_usd"]
    )


def parse_fallback_chain(raw: str | None):
    """Parse the --fable5-fallback-chain CLI value into either the literal
    string "default" (Anthropic's own recommended fallback models by
    refusal category, added 2026-07-24 — requires
    SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER) or a list parsed from
    'MODEL1,MODEL2', enforcing the documented max of 3 models total
    (including the primary, which the caller adds separately — so this
    list itself must be at most 2 entries for the common case of one
    primary + this chain, or up to 3 if the primary model is not repeated
    here). Returns None, "default", or a list."""
    if not raw:
        return None
    if raw.strip().lower() == "default":
        return "default"
    chain = [m.strip() for m in raw.split(",") if m.strip()]
    if len(chain) > 3:
        raise ValueError(
            f"--fable5-fallback-chain accepts at most 3 models total (including the "
            f"primary); got {len(chain)}."
        )
    return chain


# ── mythos access gate (claude_mythos5.py) ───────────────────────────────


class MythosAccessError(Exception):
    """Raised when a Mythos 5 call fails in a way that looks like an access-gate
    rejection (HTTP 403/404 on the model ID) rather than an ordinary API error,
    so the caller gets a pointed message instead of a generic stack trace."""

    pass


# ── opus 5 (claude_opus5.py) ─────────────────────────────────────────────

OPUS5_MODEL_ID = "claude-opus-5"

# Authoritative for Opus 5 — do not fall back to claude_models.EFFORT_BUDGETS,
# which has no "xhigh" rung and predates this model.
OPUS5_EFFORT_BUDGETS = {
    "low": 2_000,
    "medium": 8_000,
    "high": 16_000,
    "xhigh": 24_000,
    "max": 32_000,
}
OPUS5_EFFORT_LEVELS = list(OPUS5_EFFORT_BUDGETS.keys())

# Effort levels at which thinking MAY be disabled. xhigh/max + disabled = 400.
OPUS5_THINKING_DISABLE_ALLOWED = {"low", "medium", "high"}

OPUS5_INFO = {
    "display_name": "Claude Opus 5",
    "tier": "current",
    "launched": "2026-07-24",
    "context_window": 1_000_000,
    "max_output_tokens": 128_000,
    "price_input_per_mtok_usd": _CATALOG_PRICE[OPUS5_MODEL_ID]["in"],
    "price_output_per_mtok_usd": _CATALOG_PRICE[OPUS5_MODEL_ID]["out"],
    "thinking_default": "on (adaptive)",
    "effort_levels": OPUS5_EFFORT_LEVELS,
    "fast_mode_supported": OPUS5_MODEL_ID in FAST_MODE_SUPPORTED,
    "service_tier_supported": OPUS5_MODEL_ID not in SERVICE_TIER_UNSUPPORTED,
    "inference_geo_supported": OPUS5_MODEL_ID in INFERENCE_GEO_SUPPORTED,
    "notes": "A step-change over Opus 4.8 at the same per-token price. "
    "Breaking change vs. Opus 4.8: thinking can only be disabled "
    "at effort high or below.",
}


def validate_effort_thinking(effort: str | None, disable_thinking: bool) -> str | None:
    """Return None if this effort/thinking combination is safe to send to
    Opus 5, or a human-readable reason string if the API would 400 it.
    Callers should treat a non-None return as a hard stop, not a warning —
    unlike validate_fast_mode()'s REMOVED_SILENT case, there's no graceful
    degradation here."""
    if not disable_thinking:
        return None
    if effort is None:
        # No effort given at all defaults toward the low end in practice,
        # but we don't know the API's exact default resolution — be
        # conservative and only clear combinations we can confirm are safe.
        return None
    if effort not in OPUS5_EFFORT_LEVELS:
        return (
            f"unknown effort level '{effort}' for Opus 5 — choose from " f"{', '.join(OPUS5_EFFORT_LEVELS)}"
        )
    if effort not in OPUS5_THINKING_DISABLE_ALLOWED:
        return (
            f"Opus 5 rejects thinking disabled at effort '{effort}' (HTTP 400). "
            f"Thinking can only be disabled at effort {', '.join(sorted(OPUS5_THINKING_DISABLE_ALLOWED))}. "
            f"Either drop --opus5-disable-thinking or lower --opus5-effort."
        )
    return None


def validate_opus5_inference_geo(use_geo: bool) -> str | None:
    """Opus 5 is absent from claude_models.INFERENCE_GEO_SUPPORTED as of
    the 2026-07-02 catalog check, which predates this model's 2026-07-24
    launch — so treat this as unconfirmed rather than a confident yes/no."""
    if not use_geo:
        return None
    if OPUS5_MODEL_ID in INFERENCE_GEO_SUPPORTED:
        return None
    return (
        "inference_geo support for claude-opus-5 is unconfirmed (the shared "
        "INFERENCE_GEO_SUPPORTED list predates this model's launch by three "
        "weeks and has not been re-checked against live docs). Sending "
        "inference_geo may 400. Verify at platform.claude.com/docs before relying on this."
    )


def estimate_opus5_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * OPUS5_INFO["price_input_per_mtok_usd"]
        + output_tokens / 1_000_000 * OPUS5_INFO["price_output_per_mtok_usd"]
    )


# ── haiku 4.5 (claude_haiku45.py) ────────────────────────────────────────

HAIKU45_MODEL_ID = "claude-haiku-4-5-20251001"
HAIKU45_ALIAS = "claude-haiku-4-5"  # dateless alias, per claude_models.MODEL_ID_ALIASES

# Minimum budget_tokens the API accepts for extended thinking. Anthropic's
# docs specify 1024 as the floor for `thinking: {"type": "enabled", ...}`
# across models that support it in this manual-budget form.
MIN_THINKING_BUDGET = 1024

HAIKU45_INFO = {
    "display_name": "Claude Haiku 4.5",
    "tier": "current",
    "context_window": 200_000,
    "max_output_tokens": 64_000,
    "price_input_per_mtok_usd": _CATALOG_PRICE[HAIKU45_MODEL_ID]["in"],
    "price_output_per_mtok_usd": _CATALOG_PRICE[HAIKU45_MODEL_ID]["out"],
    "thinking": "extended (manual budget_tokens — NOT adaptive)",
    "fast_mode_supported": HAIKU45_MODEL_ID in FAST_MODE_SUPPORTED,
    "service_tier_supported": HAIKU45_MODEL_ID not in SERVICE_TIER_UNSUPPORTED,
    "inference_geo_supported": HAIKU45_MODEL_ID in INFERENCE_GEO_SUPPORTED,
    "alias": HAIKU45_ALIAS,
    "notes": "Fastest, most cost-effective current-tier model. The only "
    "current model using extended (not adaptive) thinking — always "
    "pass an explicit budget_tokens, never type:'adaptive'.",
}


def resolve_model_id(model_id: str) -> str:
    """Normalize the dateless alias to the full ID this module's info
    table is keyed on, so callers can pass either form."""
    return HAIKU45_MODEL_ID if model_id == HAIKU45_ALIAS else model_id


def build_thinking_param(budget_tokens: int | None) -> dict | None:
    """Build the `thinking` request block for Haiku 4.5, or None to omit
    it entirely. Always returns the *extended* (manual-budget) shape —
    {"type": "enabled", "budget_tokens": N} — never {"type": "adaptive"},
    which this model does not support. Raises ValueError if budget_tokens
    is below the documented floor."""
    if budget_tokens is None:
        return None
    if budget_tokens < MIN_THINKING_BUDGET:
        raise ValueError(
            f"budget_tokens must be >= {MIN_THINKING_BUDGET} for extended thinking; got {budget_tokens}"
        )
    return {"type": "enabled", "budget_tokens": budget_tokens}


def validate_fast_mode(want_fast: bool) -> str | None:
    if not want_fast:
        return None
    if HAIKU45_MODEL_ID in FAST_MODE_SUPPORTED:
        return None
    return (
        'fast mode (speed:"fast") is restricted to Opus models per '
        "claude_models.FAST_MODE_SUPPORTED — not available on Haiku 4.5."
    )


def validate_haiku45_inference_geo(use_geo: bool) -> str | None:
    if not use_geo:
        return None
    if HAIKU45_MODEL_ID in INFERENCE_GEO_SUPPORTED:
        return None
    return (
        "inference_geo data residency is not supported on Haiku 4.5 per "
        "claude_models.INFERENCE_GEO_SUPPORTED (Opus/Sonnet-5/Mythos-class "
        "only as of the 2026-07-02 catalog check) — sending it will 400."
    )


def estimate_haiku45_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * HAIKU45_INFO["price_input_per_mtok_usd"]
        + output_tokens / 1_000_000 * HAIKU45_INFO["price_output_per_mtok_usd"]
    )


# ── sonnet 5 (claude_sonnet5.py) ─────────────────────────────────────────

SONNET5_MODEL_ID = "claude-sonnet-5"

PROMO_PRICE_IN_USD = _CATALOG_PRICE["claude-sonnet-5"]["in"]
PROMO_PRICE_OUT_USD = _CATALOG_PRICE["claude-sonnet-5"]["out"]
# STANDARD_PRICE_IN_USD/STANDARD_PRICE_OUT_USD held the $3/$15 rate that was
# scheduled to take effect 2026-09-01. Per the Aug 10, 2026 release note,
# that increase was cancelled and $2/$10 is now the permanent price, so
# these constants are historical only and no longer used by current_pricing().
STANDARD_PRICE_IN_USD = _CATALOG_PRICE["claude-sonnet-5"]["in"]
STANDARD_PRICE_OUT_USD = _CATALOG_PRICE["claude-sonnet-5"]["out"]
PROMO_END_DATE = date(2026, 8, 31)  # kept for compatibility; no longer a pricing cliff-edge

SONNET5_INFO = {
    "display_name": "Claude Sonnet 5",
    "tier": "current",
    "context_window": 1_000_000,
    "max_output_tokens": 128_000,
    "thinking": "adaptive",
    "effort_default": "high",
    "service_tier_supported": SONNET5_MODEL_ID not in SERVICE_TIER_UNSUPPORTED,
    "inference_geo_supported": SONNET5_MODEL_ID in INFERENCE_GEO_SUPPORTED,
    "inference_geo_multiplier": INFERENCE_GEO_PRICING_MULTIPLIER,
    "notes": "Best speed/intelligence balance; builds on Sonnet 4.6. "
    "Unlike most current-tier models, does NOT support "
    "service_tier / Priority Tier.",
}


def current_pricing(as_of: date | None = None) -> dict:
    """Return the {'price_in', 'price_out', 'promo_active'} dict for Sonnet 5.
    `as_of` is accepted for backward compatibility but no longer changes the
    result: per Anthropic's Aug 10, 2026 release note, the $2/$10 per MTok
    rate is now the permanent standard price (the scheduled 2026-09-01
    increase to $3/$15 was cancelled), so there is no longer a second rate
    to switch to on any date. `promo_active` is always False now — the price
    is standard, not a time-limited promo, even though the number is
    unchanged from the original introductory rate."""
    as_of = as_of or date.today()
    return {"price_in": PROMO_PRICE_IN_USD, "price_out": PROMO_PRICE_OUT_USD, "promo_active": False}


def estimate_sonnet5_cost_usd(
    input_tokens: int, output_tokens: int, as_of: date | None = None, use_geo: bool = False
) -> float:
    """Cost estimate using whichever pricing tier applies on `as_of`
    (default: today). Applies the data-residency multiplier on top if
    use_geo=True, since inference_geo="us" pricing is 1.1x on both
    input and output per claude_models.INFERENCE_GEO_PRICING_MULTIPLIER."""
    pricing = current_pricing(as_of)
    multiplier = INFERENCE_GEO_PRICING_MULTIPLIER if use_geo else 1.0
    return (
        input_tokens / 1_000_000 * pricing["price_in"] * multiplier
        + output_tokens / 1_000_000 * pricing["price_out"] * multiplier
    )


def validate_service_tier(service_tier: str | None) -> str | None:
    """Return None if service_tier is safe to send for Sonnet 5 (i.e. not
    set at all), or a warning string if the caller is trying to use
    Priority Tier on a model that doesn't support it."""
    if service_tier is None:
        return None
    if SONNET5_MODEL_ID in SERVICE_TIER_UNSUPPORTED:
        return (
            f"claude-sonnet-5 does not support service_tier (grouped with the "
            f"Mythos-class models in claude_models.SERVICE_TIER_UNSUPPORTED). "
            f"Sending service_tier='{service_tier}' will likely be ignored or 400 — "
            f"omit it for this model."
        )
    return None


def validate_sampling_params(
    temperature: float | None = None, top_p: float | None = None, top_k: int | None = None
) -> str | None:
    """Sonnet 5 returns a 400 error if temperature, top_p, or top_k is set
    to a non-default value at all — unlike most other current-tier models,
    where non-default sampling values are simply accepted. Per the
    release note checked 2026-07-26: 'setting sampling parameters
    (temperature, top_p, top_k) to non-default values returns a 400
    error' on Claude Sonnet 5. This was a genuine gap: nothing previously
    exposed or guarded against these parameters at all. Returns None if
    none were passed (the only safe way to call this model), or a message
    string identifying which parameter(s) would 400."""
    offending = []
    if temperature is not None:
        offending.append(f"temperature={temperature}")
    if top_p is not None:
        offending.append(f"top_p={top_p}")
    if top_k is not None:
        offending.append(f"top_k={top_k}")
    if not offending:
        return None
    return (
        f"claude-sonnet-5 returns a 400 error if any sampling parameter is set "
        f"to a non-default value — {', '.join(offending)} would fail. Omit "
        f"these parameters entirely for this model (do not rely on it accepting "
        f"defaults passed explicitly)."
    )


# ── response metadata (claude_response_metadata.py) ──────────────────────


class ResponseMetadata:
    """Parsed subset of response headers this bounded context cares about.
    `raw` keeps the full header dict for callers who want more."""

    def __init__(self, workspace_id: str | None, organization_id: str | None, raw: dict):
        self.workspace_id = workspace_id
        self.organization_id = organization_id
        self.raw = raw
