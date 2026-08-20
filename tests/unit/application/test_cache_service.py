"""tests/unit/application/test_cache_service.py

Covers application/cache_service.py, extracted 2026-08-18 (Phase C,
Context #5). Fake CachingCoder substituted in — no real network.
"""

import application.cache_service as service


class FakeCachingCoder:
    instances = []

    def __init__(self, api_key, model="claude-sonnet-5", ttl="5m"):
        self.api_key = api_key
        self.model = model
        self.ttl = ttl
        self._stats = {"input_tokens": 10, "output_tokens": 5,
                       "cache_creation_input_tokens": 0,
                       "cache_read_input_tokens": 0, "cache_miss_reason": None}
        FakeCachingCoder.instances.append(self)

    def generate_cached(self, prompt, system=None, cached_docs=None, diagnose=False):
        self.generate_args = (prompt, system, cached_docs, diagnose)
        return "generated text"

    def multi_turn_cached(self, turns, system=None, mid_system_updates=None):
        self.multi_turn_args = (turns, system, mid_system_updates)
        return [f"reply {i}" for i in range(len(turns))]

    def warm_cache(self, system=None, docs=None):
        self.warm_args = (system, docs)
        return {"cache_creation_input_tokens": 42}

    def cache_stats(self):
        return self._stats


def setup_function(_):
    FakeCachingCoder.instances.clear()


def test_read_doc_files_returns_content(tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("hello world")
    docs, errors = service.read_doc_files([str(f)])
    assert docs == ["hello world"]
    assert errors == []


def test_read_doc_files_collects_errors_for_missing_files():
    docs, errors = service.read_doc_files(["/nonexistent/path.txt"])
    assert docs == []
    assert len(errors) == 1
    assert errors[0][0] == "/nonexistent/path.txt"


def test_read_doc_files_empty_list():
    docs, errors = service.read_doc_files(None)
    assert docs == []
    assert errors == []


def test_generate_delegates_and_returns_stats(monkeypatch):
    monkeypatch.setattr(service, "CachingCoder", FakeCachingCoder)
    result, stats = service.generate("hi", "key", "claude-sonnet-5",
                                      system="be nice", docs=["doc1"], diagnose=True)
    assert result == "generated text"
    assert stats["input_tokens"] == 10
    fc = FakeCachingCoder.instances[0]
    assert fc.generate_args == ("hi", "be nice", ["doc1"], True)


def test_multi_turn_delegates_and_builds_mid_system_updates(monkeypatch):
    monkeypatch.setattr(service, "CachingCoder", FakeCachingCoder)
    responses, stats = service.multi_turn(["a", "b"], "key", "claude-opus-4-8",
                                           mid_system="update", mid_system_after=0)
    assert responses == ["reply 0", "reply 1"]
    fc = FakeCachingCoder.instances[0]
    assert fc.multi_turn_args == (["a", "b"], None, {0: "update"})


def test_multi_turn_no_mid_system_passes_none(monkeypatch):
    monkeypatch.setattr(service, "CachingCoder", FakeCachingCoder)
    service.multi_turn(["a"], "key", "claude-sonnet-5")
    fc = FakeCachingCoder.instances[0]
    assert fc.multi_turn_args[2] is None


def test_warm_reads_files_and_delegates(monkeypatch, tmp_path):
    monkeypatch.setattr(service, "CachingCoder", FakeCachingCoder)
    f = tmp_path / "doc.txt"
    f.write_text("cached content")

    usage, stats, errors = service.warm("key", "claude-sonnet-5",
                                         system="sys", doc_files=[str(f)])
    assert usage["cache_creation_input_tokens"] == 42
    assert errors == []
    fc = FakeCachingCoder.instances[0]
    assert fc.warm_args == ("sys", ["cached content"])


def test_warm_returns_read_errors_alongside_usage(monkeypatch):
    monkeypatch.setattr(service, "CachingCoder", FakeCachingCoder)
    usage, stats, errors = service.warm("key", "claude-sonnet-5",
                                         doc_files=["/nonexistent.txt"])
    assert len(errors) == 1
    fc = FakeCachingCoder.instances[0]
    assert fc.warm_args == (None, [])
