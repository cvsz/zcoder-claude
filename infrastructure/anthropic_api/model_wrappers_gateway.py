"""
# mypy: ignore-errors
infrastructure/anthropic_api/model_wrappers_gateway.py — per-model Messages API gateways
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase C, Context #6)

Real HTTP calls to api.anthropic.com's Messages API for the five
model-specific clients extracted 2026-08-21 from claude_fable5.py,
claude_mythos5.py, claude_opus5.py, claude_haiku45.py, and
claude_sonnet5.py, plus the header-preserving whoami call from
claude_response_metadata.py — zero print().

Each class is moved intact (never split across layers); request-shape
validation and pricing/info tables live in domain/model_wrappers.py and
are imported here. The five source modules each defined an identically
configured module-level `_breaker` (failure_threshold=5,
reset_timeout=30); those five instances were deliberately collapsed into
ONE shared instance here because every path targets the same endpoint.
Behavior delta to be aware of: a breaker opened by heavy traffic to one
wrapper now also trips calls through the others (and vice versa) — at
HEAD each module tripped independently. With identical thresholds and a
30s reset window this was judged acceptable for same-endpoint clients;
if per-model isolation is ever needed, give each class its own
`_breaker = _shared_breaker()`-style instance again. None of the moved
client classes ever printed directly (confirmed via a repo-wide grep
before extraction), so no print-method-to-callback conversion was
needed.

The response-header lookup (`_call_with_headers` /
`get_response_metadata`) is the reference implementation for reading
`anthropic-workspace-id` / `anthropic-organization-id`, which
resilience.urlopen_json() discards; see the original claude_response_metadata.py
docstring (preserved on its shim) for why this narrow path exists.
"""

import json
import urllib.request

from domain.model_wrappers import (
    FABLE5_MODEL_ID,
    FALLBACK_CREDIT_BETA_HEADER,
    HAIKU45_MODEL_ID,
    MESSAGES_ENDPOINT,
    MYTHOS5_MODEL_ID,
    OPUS5_MODEL_ID,
    SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER,
    SONNET5_MODEL_ID,
    MythosAccessError,
    RefusalError,
    ResponseMetadata,
    build_thinking_param,
    validate_effort_thinking,
    validate_fast_mode,
    validate_haiku45_inference_geo,
    validate_opus5_inference_geo,
    validate_sampling_params,
    validate_service_tier,
)
from domain.models.catalog import FAST_MODE_SUPPORTED
from exceptions import AICoderError, APIError
from infrastructure.anthropic_api.http_client import (
    CircuitBreaker,
    retry,
    urlopen_json,
    urlopen_json_with_headers,
)

_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

# Cheapest current-tier model with no special sampling/thinking gating —
# this call exists purely to read response headers, so cost matters more
# than capability. See claude_models.MODEL_CATALOG.
_WHOAMI_MODEL = HAIKU45_MODEL_ID


class Fable5Client:
    """Thin Messages API client with refusal detection and optional fallback,
    following the same _post() pattern used throughout this project's other
    claude_*.py modules for consistency."""

    def __init__(
        self,
        api_key: str,
        model: str = FABLE5_MODEL_ID,
        fallback_model: str = "claude-opus-4-8",
        max_tokens: int = 4096,
        fallback_chain=None,
    ):
        self.api_key = api_key
        self.model = model
        self.fallback_model = fallback_model
        self.max_tokens = max_tokens
        # Server-side fallback (`fallbacks` param, beta, checked against
        # platform.claude.com/docs 2026-07-04, "default" mode added
        # 2026-07-24). Either the literal string "default" (Anthropic's own
        # recommended fallback models by refusal category) or a list of up
        # to 3 models total, including the primary `self.model` — do not
        # repeat the primary in a list. When set, this replaces (not
        # supplements) the manual client-side retry path in
        # call_with_fallback().
        self.fallback_chain = fallback_chain

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict, extra_headers: dict | None = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict, extra_headers: dict | None = None) -> dict:
        try:
            return self._call(payload, extra_headers)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def _extract_text(self, data: dict) -> str:
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def call(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        is_fallback_retry: bool = False,
    ) -> dict:
        """One raw call. Returns the parsed response dict (caller inspects stop_reason).

        is_fallback_retry=True sends the fallback-credit beta header, per the
        "manual retry" pattern in Anthropic's docs — this is what gets the
        prompt-cache cost of the switch refunded instead of charged twice.
        """
        payload = {
            "model": model or self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        # Server-side fallback: only attached on the primary call (never on
        # a manual is_fallback_retry call, and never if a caller passed an
        # explicit `model=` override, since fallbacks only make sense
        # attached to the request naming the primary model).
        if self.fallback_chain and not is_fallback_retry and model is None:
            payload["fallbacks"] = self.fallback_chain
        extra_headers = {"anthropic-beta": FALLBACK_CREDIT_BETA_HEADER} if is_fallback_retry else None
        if self.fallback_chain == "default" and not is_fallback_retry and model is None:
            # "default" mode needs its own beta header; an explicit list
            # doesn't. is_fallback_retry can't also be true here (fallback
            # retries never carry `fallbacks` at all — see the comment
            # above), so no header conflict to resolve.
            extra_headers = {"anthropic-beta": SERVER_SIDE_FALLBACK_DEFAULT_BETA_HEADER}
        return self._post(payload, extra_headers=extra_headers)

    def call_with_fallback(self, prompt: str, system: str | None = None, allow_fallback: bool = True) -> dict:
        """
        Call the configured model.

        If self.fallback_chain is set, this is a thin compatibility
        wrapper around the server-side `fallbacks` param: call() already
        attached the chain to the request, so the platform itself retries
        against the next model in the list on a refusal, in the same round
        trip. This method just has to inspect the response to report which
        model actually answered — no second HTTP call from here.

        If self.fallback_chain is unset, falls through to the legacy
        manual retry path: on stop_reason == 'refusal', optionally retry
        against self.fallback_model as a second, separate request (sending
        the fallback-credit beta header so the switch isn't billed twice).

        Returns a dict:
          {text, stop_reason, refused: bool, fell_back: bool,
           served_by: str|None, classifier: str|None, category: str|None,
           explanation: str, raw}
        """
        data = self.call(prompt, system=system)
        if "error" in data:
            return {
                "text": f"[ERROR] {data['error']}",
                "stop_reason": None,
                "refused": False,
                "fell_back": False,
                "served_by": None,
                "classifier": None,
                "category": None,
                "explanation": "",
                "raw": data,
            }

        stop_reason = data.get("stop_reason")
        refused = stop_reason == "refusal"

        if self.fallback_chain:
            # Server-side path: the platform already retried internally if
            # it needed to. The docs specify the response echoes back which
            # model in the chain actually served the request (falls back to
            # self.model if the field isn't present, e.g. no refusal
            # occurred so the primary model answered).
            served_by = data.get("model", self.model)
            stop_details = (data.get("stop_details") or {}) if refused else {}
            category = stop_details.get("category")
            return {
                "text": self._extract_text(data),
                "stop_reason": stop_reason,
                "refused": refused,
                "fell_back": served_by != self.model,
                "served_by": served_by,
                "classifier": category,
                "category": category,
                "explanation": stop_details.get("explanation", ""),
                "raw": data,
            }
        # Was reading data["refusal"]["classifier"] — a field this project
        # invented rather than one the API documents. The documented shape
        # (per Refusals and fallback, checked 2026-07-04) is
        # stop_details: {type, category, explanation}, with category one of
        # "cyber", "bio", "frontier_llm", "reasoning_extraction", or null
        # (null is a documented permanent value, not a missing field).
        # classifier is kept as an alias of category below so any existing
        # caller reading result["classifier"] keeps working.
        stop_details = (data.get("stop_details") or {}) if refused else {}
        category = stop_details.get("category")
        classifier = category

        if refused and allow_fallback:
            # is_fallback_retry=True sends the fallback-credit beta header so
            # this manual retry doesn't get billed twice for prompt caching.
            fallback_data = self.call(
                prompt, system=system, model=self.fallback_model, is_fallback_retry=True
            )
            if "error" in fallback_data:
                return {
                    "text": f"[ERROR on fallback] {fallback_data['error']}",
                    "stop_reason": stop_reason,
                    "refused": True,
                    "fell_back": False,
                    "served_by": None,
                    "classifier": classifier,
                    "category": category,
                    "explanation": stop_details.get("explanation", ""),
                    "raw": data,
                }
            return {
                "text": self._extract_text(fallback_data),
                "stop_reason": fallback_data.get("stop_reason"),
                "refused": True,
                "fell_back": True,
                "served_by": self.fallback_model,
                "classifier": classifier,
                "category": category,
                "explanation": stop_details.get("explanation", ""),
                "raw": fallback_data,
            }

        if refused:
            raise RefusalError(
                f"Claude Fable 5 declined this request (category: {category or 'unspecified'}). "
                "Re-run with fallback enabled, or use claude-opus-4-8 directly.",
                classifier=classifier,
            )

        return {
            "text": self._extract_text(data),
            "stop_reason": stop_reason,
            "refused": False,
            "fell_back": False,
            "served_by": self.model,
            "classifier": None,
            "category": None,
            "explanation": "",
            "raw": data,
        }


class Mythos5Client:
    """Minimal Messages API client for claude-mythos-5. No refusal/fallback
    handling — see claude_mythos5.py's shim docstring for why. Follows the
    same _post() pattern as Fable5Client for consistency."""

    def __init__(self, api_key: str, max_tokens: int = 4096):
        self.api_key = api_key
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except APIError as e:
            if e.status_code in (403, 404):
                body = e.details.get("body", "")
                raise MythosAccessError(
                    f"HTTP {e.status_code} calling claude-mythos-5 — this looks like an "
                    "access-gate rejection rather than a normal API error. Mythos 5 "
                    "requires approved Project Glasswing access; most accounts will "
                    "see this. Use claude-fable-5 instead unless you've confirmed "
                    f"access with Anthropic. Raw response: {body}"
                ) from e
            return {"error": e.message, "status": e.status_code}
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call(self, prompt: str, system: str | None = None) -> dict:
        payload = {
            "model": MYTHOS5_MODEL_ID,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        return self._post(payload)

    def call_text(self, prompt: str, system: str | None = None) -> str:
        """Convenience wrapper returning just the response text (or an
        [ERROR] string), for callers that don't need the raw response dict."""
        data = self.call(prompt, system=system)
        if "error" in data:
            return f"[ERROR] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


class Opus5Client:
    """Messages API client for claude-opus-5 with client-side validation of
    the effort/thinking interaction, so a bad combination fails fast with a
    clear message instead of a bare 400 from the API. Follows the same
    _post() pattern as Fable5Client / Mythos5Client for consistency."""

    def __init__(self, api_key: str, max_tokens: int = 4096):
        self.api_key = api_key
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call(
        self,
        prompt: str,
        system: str | None = None,
        effort: str | None = None,
        disable_thinking: bool = False,
        fast: bool = False,
        use_geo: bool = False,
    ) -> dict:
        """Build and send one request. Raises ValueError client-side for
        combinations the API is documented to reject, rather than sending
        a request known in advance to 400."""
        err = validate_effort_thinking(effort, disable_thinking)
        if err:
            raise ValueError(err)
        if fast and OPUS5_MODEL_ID not in FAST_MODE_SUPPORTED:
            raise ValueError("fast mode is not supported on claude-opus-5 per the shared catalog")
        geo_warning = validate_opus5_inference_geo(use_geo)

        payload = {
            "model": OPUS5_MODEL_ID,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if effort:
            payload["effort"] = effort
        if disable_thinking:
            payload["thinking"] = {"type": "disabled"}
        if fast:
            payload["speed"] = "fast"
        if use_geo:
            payload["inference_geo"] = "us"

        data = self._post(payload)
        if geo_warning and "error" not in data:
            data["_geo_warning"] = geo_warning
        return data

    def call_text(self, prompt: str, **kwargs) -> str:
        data = self.call(prompt, **kwargs)
        if "error" in data:
            return f"[ERROR] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


class Haiku45Client:
    """Messages API client for claude-haiku-4-5-20251001. Follows the same
    _post() pattern as the other per-model gateway classes."""

    def __init__(self, api_key: str, max_tokens: int = 4096):
        self.api_key = api_key
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call(
        self,
        prompt: str,
        system: str | None = None,
        thinking_budget: int | None = None,
        fast: bool = False,
        use_geo: bool = False,
    ) -> dict:
        fast_err = validate_fast_mode(fast)
        if fast_err:
            raise ValueError(fast_err)
        geo_err = validate_haiku45_inference_geo(use_geo)
        if geo_err:
            raise ValueError(geo_err)

        thinking = build_thinking_param(thinking_budget)  # raises ValueError on bad budget

        payload = {
            "model": HAIKU45_MODEL_ID,
            "max_tokens": max(self.max_tokens, (thinking_budget or 0) + 1024),
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if thinking:
            payload["thinking"] = thinking
        return self._post(payload)

    def call_text(self, prompt: str, **kwargs) -> str:
        data = self.call(prompt, **kwargs)
        if "error" in data:
            return f"[ERROR] {data['error']}"
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


class Sonnet5Client:
    """Messages API client for claude-sonnet-5. Follows the same _post()
    pattern as the other per-model gateway classes."""

    def __init__(self, api_key: str, max_tokens: int = 4096):
        self.api_key = api_key
        self.max_tokens = max_tokens

    @retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
    def _call(self, payload: dict) -> dict:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }
        req = urllib.request.Request(
            MESSAGES_ENDPOINT,
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )
        return urlopen_json(req, timeout=300)

    def _post(self, payload: dict) -> dict:
        try:
            return self._call(payload)
        except AICoderError as e:
            return {"error": e.message, "status": getattr(e, "status_code", None)}
        except Exception as e:
            return {"error": str(e)}

    def call(
        self,
        prompt: str,
        system: str | None = None,
        use_geo: bool = False,
        service_tier: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
    ) -> dict:
        warning = validate_service_tier(service_tier)
        sampling_error = validate_sampling_params(temperature, top_p, top_k)
        if sampling_error:
            return {"error": sampling_error, "status": None}
        payload = {
            "model": SONNET5_MODEL_ID,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system
        if use_geo:
            payload["inference_geo"] = "us"
        if service_tier:
            payload["service_tier"] = service_tier
        data = self._post(payload)
        if warning and "error" not in data:
            data["_service_tier_warning"] = warning
        return data


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _call_with_headers(api_key: str) -> tuple:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": _WHOAMI_MODEL,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    req = urllib.request.Request(
        MESSAGES_ENDPOINT,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    return urlopen_json_with_headers(req, timeout=60)


def get_response_metadata(api_key: str) -> ResponseMetadata:
    """Make the minimal whoami call and return the parsed metadata.
    Raises AICoderError on failure (bad key, network error, etc.) — same
    exception type every other claude_*.py client raises, so callers can
    catch it uniformly."""
    _body, response_headers = _call_with_headers(api_key)
    # Header names arrive case-normalized inconsistently across urllib
    # versions/platforms; check both cases explicitly rather than assuming.
    workspace_id = response_headers.get("anthropic-workspace-id") or response_headers.get(
        "Anthropic-Workspace-Id"
    )
    organization_id = response_headers.get("anthropic-organization-id") or response_headers.get(
        "Anthropic-Organization-Id"
    )
    return ResponseMetadata(workspace_id, organization_id, response_headers)
