"""tests/test_observability_gateway.py

Covers infrastructure/anthropic_api/observability_gateway.py — the real
HTTP-call half of the Cost, Metrics, Observability & Eval bounded
context, extracted 2026-08-19 (Phase D, Context #7). A fake
anthropic.Anthropic client is substituted in — no real network, no real
SDK calls. claude_observability.py and claude_eval.py had zero test
coverage before this migration; this closes that gap for the
gateway-level HTTP logic (optimized_call's spend logging + refusal
exemption, LLMJudge.score's JSON parsing, EvalRunner.run's on_case
callback wiring, and analyze_errors).
"""
import json

import infrastructure.anthropic_api.observability_gateway as gateway
from domain.observability import EvalCase


class FakeUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class FakeContentBlock:
    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text, input_tokens=10, output_tokens=5, stop_reason="end_turn"):
        self.content = [FakeContentBlock(text)] if text is not None else []
        self.usage = FakeUsage(input_tokens, output_tokens)
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return self._responses.pop(0) if len(self._responses) > 1 else self._responses[0]


class FakeAnthropicClient:
    _next_responses = [FakeResponse("hello")]

    def __init__(self, api_key):
        self.api_key = api_key
        self.messages = FakeMessages(FakeAnthropicClient._next_responses)


def _install_fake_client(monkeypatch, responses):
    FakeAnthropicClient._next_responses = responses
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)


# ── optimized_call ────────────────────────────────────────────────────

def test_optimized_call_logs_spend_and_returns_response(monkeypatch, tmp_path):
    _install_fake_client(monkeypatch, [FakeResponse("hi there", 100, 50)])
    logged = []
    monkeypatch.setattr(gateway, "log_spend",
                        lambda model, i, o, cost, prompt: logged.append((model, i, o, cost)))
    r = gateway.optimized_call("say hi", "key", "claude-sonnet-5", "low")
    assert r.text == "hi there"
    assert r.model_used == "claude-sonnet-5"
    assert r.in_tokens == 100 and r.out_tokens == 50
    assert len(logged) == 1
    assert logged[0][0] == "claude-sonnet-5"


def test_optimized_call_pure_refusal_is_not_billed(monkeypatch):
    _install_fake_client(monkeypatch, [FakeResponse(None, 100, 0, stop_reason="refusal")])
    logged = []
    monkeypatch.setattr(gateway, "log_spend", lambda *a, **k: logged.append(a))
    r = gateway.optimized_call("say hi", "key", "claude-sonnet-5", "low")
    assert r.cost_usd == 0.0
    assert logged == []


# ── LLMJudge ──────────────────────────────────────────────────────────

def test_llm_judge_parses_json_score(monkeypatch):
    _install_fake_client(monkeypatch, [FakeResponse(json.dumps({"score": 0.8, "reason": "close"}))])
    judge = gateway.LLMJudge(api_key="key")
    score, reason = judge.score("prompt", "expected", "actual")
    assert score == 0.8
    assert reason == "close"


def test_llm_judge_strips_code_fences(monkeypatch):
    fenced = "```json\n" + json.dumps({"score": 1.0, "reason": "ok"}) + "\n```"
    _install_fake_client(monkeypatch, [FakeResponse(fenced)])
    judge = gateway.LLMJudge(api_key="key")
    score, reason = judge.score("prompt", "expected", "actual")
    assert score == 1.0


def test_llm_judge_handles_malformed_json_gracefully(monkeypatch):
    _install_fake_client(monkeypatch, [FakeResponse("not json at all")])
    judge = gateway.LLMJudge(api_key="key")
    score, reason = judge.score("prompt", "expected", "actual")
    assert score == 0.0
    assert "judge error" in reason


# ── EvalRunner ────────────────────────────────────────────────────────

def test_eval_runner_run_invokes_on_case_callback(monkeypatch):
    _install_fake_client(monkeypatch, [FakeResponse("the answer")])

    def fake_score(self, prompt, expected, actual):
        return 0.9, "good"
    monkeypatch.setattr(gateway.LLMJudge, "score", fake_score)

    seen = []
    runner = gateway.EvalRunner(api_key="key", model="claude-sonnet-5")
    cases = [EvalCase(case_id="c1", prompt="p1", expected="e1")]
    run = runner.run(cases, on_case=lambda cid, score, passed, ms: seen.append((cid, score, passed)))
    assert run.cases == 1
    assert run.passed == 1
    assert seen == [("c1", 0.9, True)]


def test_eval_runner_run_default_on_case_is_a_noop(monkeypatch):
    _install_fake_client(monkeypatch, [FakeResponse("the answer")])
    monkeypatch.setattr(gateway.LLMJudge, "score", lambda self, p, e, a: (0.1, "bad"))
    runner = gateway.EvalRunner(api_key="key", model="claude-sonnet-5", pass_threshold=0.7)
    cases = [EvalCase(case_id="c1", prompt="p1", expected="e1")]
    run = runner.run(cases)  # should not raise
    assert run.passed == 0


# ── analyze_errors ────────────────────────────────────────────────────

def test_analyze_errors_returns_text_from_response(monkeypatch):
    _install_fake_client(monkeypatch, [FakeResponse("pattern: timeouts under load")])
    text = gateway.analyze_errors("key", "claude-sonnet-5",
                                  [{"ts": "2026-08-19T00:00", "model": "m", "error": "timeout"}])
    assert text == "pattern: timeouts under load"
