"""tests/unit/application/test_batch_service.py

Covers application/batch_service.py — the use-case layer for the
Messages Batch API bounded context, extracted 2026-08-18 (Phase C,
Context #4). Fake BatchCoder substituted in — no real network, no
real anthropic SDK client.
"""

import application.batch_service as service


class FakeBatchCoder:
    instances = []

    def __init__(self, api_key, model="claude-sonnet-5", use_300k_output=False, on_warning=None):
        self.api_key = api_key
        self.model = model
        self.use_300k_output = use_300k_output
        self.on_warning = on_warning
        FakeBatchCoder.instances.append(self)

    def submit_from_jsonl(self, jsonl_path, system=None):
        self.jsonl_path = jsonl_path
        self.system = system
        return "batch_from_jsonl"

    def submit_prompts(self, prompts, system=None):
        self.prompts = prompts
        self.system = system
        return "batch_from_prompts"

    def status(self, batch_id):
        self.status_id = batch_id
        return {"id": batch_id, "status": "in_progress"}

    def results(self, batch_id, save_to=None):
        self.results_id = batch_id
        self.save_to = save_to
        return [{"custom_id": "r1", "type": "succeeded", "text": "hi"}]

    def list_batches(self):
        return [{"id": "batch_1"}]

    def cancel(self, batch_id):
        self.cancelled = batch_id
        return True

    def wait(self, batch_id, on_progress=None):
        self.waited_id = batch_id
        self.on_progress = on_progress
        if on_progress:
            on_progress(batch_id, {"status": "ended"}, 15)
        return {"id": batch_id, "status": "ended"}


def setup_function(_):
    FakeBatchCoder.instances.clear()


def test_build_variant_prompts():
    prompts = service.build_variant_prompts("write a test", 3)
    assert prompts == [
        "write a test (variant 1 of 3)",
        "write a test (variant 2 of 3)",
        "write a test (variant 3 of 3)",
    ]


def test_submit_from_jsonl_delegates(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    bid = service.submit_from_jsonl("tasks.jsonl", "key", "claude-sonnet-5", system="be terse")
    assert bid == "batch_from_jsonl"
    fc = FakeBatchCoder.instances[0]
    assert fc.jsonl_path == "tasks.jsonl"
    assert fc.system == "be terse"


def test_submit_from_jsonl_forwards_300k_flag_and_warning_callback(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    captured_warning = []
    service.submit_from_jsonl(
        "tasks.jsonl", "key", "claude-opus-4-8", use_300k_output=True, on_warning=captured_warning.append
    )
    fc = FakeBatchCoder.instances[0]
    assert fc.use_300k_output is True
    fc.on_warning("test message")
    assert captured_warning == ["test message"]


def test_get_status_delegates(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    s = service.get_status("batch_123", "key")
    assert s == {"id": "batch_123", "status": "in_progress"}


def test_get_results_delegates(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    items = service.get_results("batch_123", "key", save_to="out.jsonl")
    assert items[0]["custom_id"] == "r1"
    assert FakeBatchCoder.instances[0].save_to == "out.jsonl"


def test_list_batches_delegates(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    assert service.list_batches("key") == [{"id": "batch_1"}]


def test_cancel_batch_delegates(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    service.cancel_batch("batch_123", "key")
    assert FakeBatchCoder.instances[0].cancelled == "batch_123"


def test_generate_and_submit_builds_variants_and_submits(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    bid = service.generate_and_submit("write code", 2, "key", "claude-sonnet-5")
    assert bid == "batch_from_prompts"
    fc = FakeBatchCoder.instances[0]
    assert fc.prompts == ["write code (variant 1 of 2)", "write code (variant 2 of 2)"]


def test_wait_for_batch_forwards_progress_callback(monkeypatch):
    monkeypatch.setattr(service, "BatchCoder", FakeBatchCoder)
    calls = []
    result = service.wait_for_batch("batch_123", "key", on_progress=lambda *a: calls.append(a))
    assert result == {"id": "batch_123", "status": "ended"}
    assert calls == [("batch_123", {"status": "ended"}, 15)]
