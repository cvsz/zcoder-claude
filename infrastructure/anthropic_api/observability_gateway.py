"""
infrastructure/anthropic_api/observability_gateway.py — HTTP calls for the
Cost, Metrics, Observability & Eval bounded context.
AI Model Coder CLI v1.53.0 (Clean Architecture refactor, Phase D, Context #7)

Every `api.anthropic.com` call for this context lives here. No print() —
callers that want live progress (e.g. the CLI layer) supply an on_case
callback, same convention as agents_gateway.py's on_step/on_delta.
Extracted 2026-08-19 from claude_cost_optimizer.py (optimized_call),
claude_observability.py (error_analysis), and claude_eval.py
(LLMJudge, EvalRunner._generate/.run).
"""

import time
import uuid
from typing import Callable, List, Optional

import anthropic
from utils import sampling_kwargs
from domain.observability import EvalCase, EvalResult, EvalRun, OptimizedResponse, build_eval_run, estimate_cost
from infrastructure.local_storage.observability_store import log_spend

_NOOP = lambda *a, **k: None  # noqa: E731


def optimized_call(prompt: str, api_key: str, model: str, complexity: str,
                   system: str = "", max_tokens: int = 2048,
                   service_tier: Optional[str] = None,
                   inference_geo: Optional[str] = None) -> OptimizedResponse:
    """Send `prompt` to `model` (already selected by
    domain.observability.select_model()) and log the spend. Kept as one
    function rather than splitting the HTTP call from the spend-log write
    — same reasoning as claude_batch.py's CachingCoder gateway, which also
    pairs one HTTP call with its own bookkeeping write."""
    client = anthropic.Anthropic(api_key=api_key)
    t0     = time.time()
    # NOTE: was hardcoded temperature=0.5, which 400s (invalid_request_error)
    # on claude-sonnet-5 and newer — those models reject explicit sampling
    # params entirely. Route through sampling_kwargs() so it's a no-op there
    # and unchanged (temperature=0.5) on everything else.
    kwargs: dict = dict(model=model, max_tokens=max_tokens,
                        messages=[{"role": "user", "content": prompt}],
                        **sampling_kwargs(model, temperature=0.5))
    if system: kwargs["system"] = system
    if service_tier:
        # "auto" (use Priority Tier capacity if committed, else fall back to
        # standard) or "standard_only". Priority Tier commitments are no
        # longer purchasable but existing ones still work, and aren't
        # supported on Sonnet 5 / Mythos-tier models — let the API 400
        # surface rather than silently guarding it away client-side.
        kwargs["service_tier"] = service_tier
    if inference_geo:
        # "us" (US-only inference, 1.1x pricing) or "global" (default).
        # Only Opus 4.6+/Sonnet 4.6+ and later support this param at all;
        # earlier models 400 — same reasoning as service_tier above.
        kwargs["inference_geo"] = inference_geo
    resp    = client.messages.create(**kwargs)
    ms      = int((time.time() - t0) * 1000)
    stop_reason = getattr(resp, "stop_reason", None)
    text    = resp.content[0].text if resp.content else ""
    in_tok  = resp.usage.input_tokens
    out_tok = resp.usage.output_tokens
    # Refusal billing exemption: a request that returns stop_reason:"refusal"
    # with no generated output isn't billed on the Claude API (checked
    # platform.claude.com/docs 2026-07-02). Don't log spend for it, and don't
    # count it against cost estimates — it's free.
    if stop_reason == "refusal" and out_tok == 0:
        cost = 0.0
    else:
        cost = estimate_cost(model, in_tok, out_tok, inference_geo=inference_geo or "global")
        log_spend(model, in_tok, out_tok, cost, prompt)
    return OptimizedResponse(text=text, model_used=model, complexity=complexity,
                             in_tokens=in_tok, out_tokens=out_tok,
                             cost_usd=cost, latency_ms=ms)


class LLMJudge:
    """Uses Claude to judge whether a response satisfies the expected criterion."""

    def __init__(self, api_key: str, judge_model: str = "claude-sonnet-5"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = judge_model

    def score(self, prompt: str, expected: str, actual: str) -> "tuple[float, str]":
        """Return (score 0-1, reason)."""
        import json
        system = (
            "You are an evaluation judge. Score the response 0.0-1.0 where:\n"
            "1.0 = fully satisfies the expected criterion\n"
            "0.5 = partially satisfies\n"
            "0.0 = does not satisfy at all\n"
            "Return ONLY a JSON object: {\"score\": float, \"reason\": str}"
        )
        user = (
            f"Task prompt: {prompt}\n\n"
            f"Expected criterion: {expected}\n\n"
            f"Actual response:\n{actual}\n\n"
            "Score the actual response against the expected criterion."
        )
        try:
            resp = self.client.messages.create(
                model=self.model, max_tokens=256,
                **sampling_kwargs(self.model, temperature=0),
                system=system, messages=[{"role": "user", "content": user}])
            raw = resp.content[0].text.strip()
            if raw.startswith("```"): raw = "\n".join(raw.split("\n")[1:-1])
            d = json.loads(raw)
            return float(d.get("score", 0.0)), str(d.get("reason", ""))
        except Exception as e:
            return 0.0, f"judge error: {e}"


class EvalRunner:
    def __init__(self, api_key: str, model: str = "claude-sonnet-5",
                 judge_model: str = "claude-sonnet-5", pass_threshold: float = 0.7):
        self.client    = anthropic.Anthropic(api_key=api_key)
        self.model     = model
        self.judge     = LLMJudge(api_key, judge_model)
        self.threshold = pass_threshold

    def _generate(self, prompt: str) -> "tuple[str, int]":
        t0 = time.time()
        resp = self.client.messages.create(
            model=self.model, max_tokens=2048,
            **sampling_kwargs(self.model, temperature=0),
            messages=[{"role": "user", "content": prompt}])
        ms = int((time.time() - t0) * 1000)
        return resp.content[0].text, ms

    def run(self, cases: List[EvalCase],
           on_case: Callable[[str, float, bool, int], None] = _NOOP) -> EvalRun:
        """`on_case(case_id, score, passed, latency_ms)` is an optional
        callback for presentation-layer per-case progress — infrastructure/
        makes no print() calls of its own; callers that want live output
        (e.g. the CLI layer) supply a callback, same convention as
        agents_gateway.py's on_step/on_delta."""
        run_id  = str(uuid.uuid4())[:8]
        results = []
        for case in cases:
            actual, ms = self._generate(case.prompt)
            score, reason = self.judge.score(case.prompt, case.expected, actual)
            passed = score >= self.threshold
            results.append(EvalResult(
                case_id=case.case_id, prompt=case.prompt, expected=case.expected,
                actual=actual, score=score, passed=passed,
                latency_ms=ms, model=self.model, reason=reason))
            on_case(case.case_id, score, passed, ms)

        return build_eval_run(run_id, self.model, results)


def analyze_errors(api_key: str, model: str, error_records: List[dict]) -> str:
    """claude_observability.py's former error_analysis(), minus the
    print() and the log-reading half (now the application layer's job via
    infrastructure/local_storage/observability_store.read_observability_logs()).
    Returns the analysis text; caller decides whether/how to display it."""
    # NOTE: matches claude_observability.py's original call exactly —
    # temperature=0 passed directly rather than through sampling_kwargs().
    # Not changed here: fixing that (it would 400 on claude-sonnet-5+,
    # same class of bug sampling_kwargs() exists to prevent elsewhere in
    # this bounded context) is a separate, pre-existing behavior change
    # outside this migration's scope — flagged in exec-planning.md instead
    # of silently fixed mid-migration.
    summary = "\n".join(f"- {e['ts'][:16]} [{e['model']}] {e['error']}" for e in error_records[-20:])
    client  = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model, max_tokens=512, temperature=0,
        system="You are an SRE. Analyse these API error logs and identify patterns + fixes.",
        messages=[{"role": "user", "content": summary}])
    return resp.content[0].text


__all__ = ["optimized_call", "LLMJudge", "EvalRunner", "analyze_errors"]
