"""tests/test_batch_gateway.py

Covers infrastructure/anthropic_api/batch_gateway.py's BatchCoder —
specifically the on_warning/on_progress callback wiring that used to be
direct print() calls in the original claude_batch.py, extracted
2026-08-18 (Phase C, Context #4). A fake anthropic.Anthropic client is
substituted in — no real network, no real SDK calls.
"""

import infrastructure.anthropic_api.batch_gateway as gateway


class FakeRequestCounts:
    def model_dump(self):
        return {"processing": 1, "succeeded": 0}


class FakeBatch:
    id = "batch_abc"
    processing_status = "in_progress"
    request_counts = FakeRequestCounts()
    created_at = "2026-08-18T00:00:00Z"
    expires_at = "2026-08-25T00:00:00Z"


class FakeBatchEndpoint:
    def __init__(self):
        self.create_calls = []
        self.retrieve_calls = []
        self._ended = False

    def create(self, requests):
        self.create_calls.append(requests)
        return FakeBatch()

    def retrieve(self, batch_id):
        self.retrieve_calls.append(batch_id)
        if self._ended:
            b = FakeBatch()
            b.processing_status = "ended"
            return b
        return FakeBatch()


class FakeMessages:
    def __init__(self):
        self.batches = FakeBatchEndpoint()


class FakeBeta:
    def __init__(self, messages):
        self.messages = messages


class FakeAnthropicClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.messages = FakeMessages()
        self.beta = FakeBeta(self.messages)


def test_init_warns_when_model_ineligible_for_300k(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    warnings = []
    gateway.BatchCoder(api_key="key", model="claude-haiku-4-5-20251001",
                        use_300k_output=True, on_warning=warnings.append)
    assert len(warnings) == 1
    assert "OUTPUT_300K_MODELS" in warnings[0]


def test_init_no_warning_for_eligible_model(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    warnings = []
    gateway.BatchCoder(api_key="key", model="claude-sonnet-5",
                        use_300k_output=True, on_warning=warnings.append)
    assert warnings == []


def test_init_no_warning_when_300k_not_requested(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    warnings = []
    gateway.BatchCoder(api_key="key", model="claude-haiku-4-5-20251001",
                        use_300k_output=False, on_warning=warnings.append)
    assert warnings == []


def test_default_on_warning_is_noop_when_unspecified(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    # Should not raise or print — default callback is a true no-op.
    gateway.BatchCoder(api_key="key", model="claude-haiku-4-5-20251001",
                        use_300k_output=True)


def test_wait_calls_on_progress_and_stops_when_ended(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    monkeypatch.setattr(gateway.time, "sleep", lambda *a: None)

    bc = gateway.BatchCoder(api_key="key")
    bc.client.messages.batches._ended = True  # first status() call already "ended"

    calls = []
    result = bc.wait("batch_abc", poll_interval=1, on_progress=lambda *a: calls.append(a))

    assert result["status"] == "ended"
    assert len(calls) == 1
    assert calls[0][0] == "batch_abc"
    assert calls[0][2] == 0  # waited seconds on the call that ended the loop


def test_wait_default_on_progress_is_noop(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    bc = gateway.BatchCoder(api_key="key")
    bc.client.messages.batches._ended = True
    # Should not raise — default on_progress is a true no-op.
    result = bc.wait("batch_abc", poll_interval=1)
    assert result["status"] == "ended"


def test_use_300k_output_adds_beta_header_on_create(monkeypatch):
    monkeypatch.setattr(gateway.anthropic, "Anthropic", FakeAnthropicClient)
    bc = gateway.BatchCoder(api_key="key", model="claude-sonnet-5", use_300k_output=True)
    original_beta_create = bc.client.beta.messages.batches.create
    captured = {}

    def spy_create(requests, betas=None):
        captured["betas"] = betas
        return original_beta_create(requests)

    bc.client.beta.messages.batches.create = spy_create
    bc.submit_prompts(["hello"])
    assert captured["betas"] == [gateway.OUTPUT_300K_BETA]
