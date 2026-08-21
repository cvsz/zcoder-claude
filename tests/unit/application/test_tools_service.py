"""tests/unit/application/test_tools_service.py

Covers application/tools_service.py — the use-case layer added
2026-08-16 (Phase C) for the Tool Use & Retrieval bounded context. Fake
gateway classes substituted in — no print() capture, no real network.
"""

import json

import application.tools_service as service

# ── agentic tool runner ─────────────────────────────────────────────────


def test_run_tool_agent_delegates_and_threads_callback(monkeypatch):
    calls = {}

    class FakeToolCoder:
        def __init__(self, api_key, model):
            calls["init"] = (api_key, model)

        def run_agent(self, prompt, registry, system=None, max_turns=10, on_tool_call=None):
            on_tool_call("read_file", {"path": "x"})
            return "done"

    monkeypatch.setattr(service, "ToolCoder", FakeToolCoder)
    seen = []
    result = service.run_tool_agent(
        "q", "k", "claude-sonnet-5", on_tool_call=lambda n, i: seen.append((n, i))
    )
    assert result == "done"
    assert seen == [("read_file", {"path": "x"})]


def test_build_code_tools_registry_has_expected_tools():
    reg = service.build_code_tools_registry()
    names = {d["name"] for d in reg.definitions()}
    assert names == {"run_python", "read_file", "write_file", "list_files"}


def test_run_server_tools_marks_extra_tools_with_ptc(monkeypatch):
    captured = {}

    class FakeToolCoder:
        def __init__(self, api_key, model):
            pass

        def generate_with_server_tools(self, prompt, tool_names, **kwargs):
            captured.update(kwargs)
            return "ok"

    monkeypatch.setattr(service, "ToolCoder", FakeToolCoder)
    service.run_server_tools(
        "q",
        ["code_execution"],
        "k",
        "claude-sonnet-5",
        use_ptc=True,
        extra_tool_defs=[{"name": "my_tool", "input_schema": {}}],
    )
    assert captured["extra_tools"][0]["allowed_callers"]


def test_run_memory_agent_delegates(monkeypatch):
    class FakeMemory:
        def __init__(self, base_dir):
            self.base_dir = base_dir

    class FakeToolCoder:
        def __init__(self, api_key, model):
            pass

        def run_agent_with_memory(self, prompt, memory, max_turns=10, on_memory_op=None):
            on_memory_op("view", "/memories")
            return "ok"

    monkeypatch.setattr(service, "ToolCoder", FakeToolCoder)
    monkeypatch.setattr(service, "MemoryToolHandler", FakeMemory)
    seen = []
    result = service.run_memory_agent(
        "q", "k", "claude-sonnet-5", on_memory_op=lambda c, p: seen.append((c, p))
    )
    assert result == "ok"
    assert seen == [("view", "/memories")]


def test_list_server_tools_info_includes_retirement_notes():
    rows = service.list_server_tools_info()
    names = {r["name"] for r in rows}
    assert "web_search" in names
    assert "memory" in names


# ── vision ───────────────────────────────────────────────────────────────


def test_analyse_image_code_mode_calls_screenshot(monkeypatch):
    calls = {}

    class FakeVisionCoder:
        def __init__(self, api_key, model):
            pass

        def code_from_screenshot(self, path=None, url=None, language="auto"):
            calls["args"] = (path, url, language)
            return "code"

    monkeypatch.setattr(service, "VisionCoder", FakeVisionCoder)
    result = service.analyse_image("img.png", "", "k", "claude-sonnet-5", is_code=True, language="python")
    assert result == "code"
    assert calls["args"] == ("img.png", None, "python")


def test_ocr_image_delegates(monkeypatch):
    class FakeVisionCoder:
        def __init__(self, api_key, model):
            pass

        def extract_text(self, path=None, url=None):
            return "extracted text"

    monkeypatch.setattr(service, "VisionCoder", FakeVisionCoder)
    assert service.ocr_image("img.png", "k", "claude-sonnet-5") == "extracted text"


# ── web search & fetch ───────────────────────────────────────────────────


def test_web_search_delegates(monkeypatch):
    class FakeSearchCoder:
        def __init__(self, api_key, model):
            pass

        def search(self, prompt, **kwargs):
            return {"response": "answer", "citations": [], "searches": 1, "usage": {}}

    monkeypatch.setattr(service, "SearchCoder", FakeSearchCoder)
    result = service.web_search("q", "k", "claude-sonnet-5")
    assert result["response"] == "answer"


def test_fetch_url_delegates(monkeypatch):
    class FakeSearchCoder:
        def __init__(self, api_key, model):
            pass

        def fetch_and_summarise(self, url, instruction):
            return f"summary of {url}"

    monkeypatch.setattr(service, "SearchCoder", FakeSearchCoder)
    assert service.fetch_url("http://x", "", "k", "claude-sonnet-5") == "summary of http://x"


# ── embeddings ───────────────────────────────────────────────────────────


def test_embed_text_unwraps_single_vector(monkeypatch):
    monkeypatch.setattr(service, "embed", lambda texts, model, input_type: [[1.0, 2.0]])
    assert service.embed_text("hi") == [1.0, 2.0]


def test_embed_lines_reads_file(tmp_path, monkeypatch):
    f = tmp_path / "lines.txt"
    f.write_text("a\nb\n\nc\n")
    monkeypatch.setattr(service, "embed", lambda texts, model, input_type: [[1], [2], [3]])
    outcome = service.embed_lines(str(f))
    assert outcome["lines"] == ["a", "b", "c"]
    assert outcome["vecs"] == [[1], [2], [3]]


def test_embed_similarity_uses_cosine(monkeypatch):
    monkeypatch.setattr(service, "embed", lambda texts, model, input_type: [[1, 0], [1, 0]])
    assert service.embed_similarity("a", "b") == 1.0


# ── RAG ──────────────────────────────────────────────────────────────────


def test_rag_query_missing_index(monkeypatch):
    monkeypatch.setattr(service.rag_index_store, "load_index", lambda name: None)
    outcome = service.rag_query("nope", "q", "k", "claude-sonnet-5")
    assert outcome == {"found_index": False, "chunks": [], "answer": None}


def test_rag_query_no_relevant_chunks(monkeypatch):
    class FakeIndex:
        chunks = []
        idf = {}

    monkeypatch.setattr(service.rag_index_store, "load_index", lambda name: FakeIndex())
    monkeypatch.setattr(service, "rag_retrieve", lambda idx, query, k: [])
    outcome = service.rag_query("idx", "q", "k", "claude-sonnet-5")
    assert outcome["found_index"] is True
    assert outcome["chunks"] == []
    assert outcome["answer"] is None


def test_rag_query_generates_answer(monkeypatch):
    from domain.tools import Chunk

    class FakeIndex:
        chunks = [Chunk(cid="c1", source="f.txt", content="hello")]
        idf = {}

    chunk = Chunk(cid="c1", source="f.txt", content="hello")
    monkeypatch.setattr(service.rag_index_store, "load_index", lambda name: FakeIndex())
    monkeypatch.setattr(service, "rag_retrieve", lambda idx, query, k: [chunk])
    monkeypatch.setattr(service, "rag_generate", lambda query, chunks, api_key, model: "the answer")
    outcome = service.rag_query("idx", "q", "k", "claude-sonnet-5")
    assert outcome["answer"] == "the answer"
    assert outcome["chunks"] == [chunk]


def test_rag_list_indexes_reads_json(tmp_path, monkeypatch):
    f = tmp_path / "myidx.json"
    f.write_text(json.dumps({"name": "myidx", "chunks": [1, 2, 3]}))
    monkeypatch.setattr(service.rag_index_store, "list_index_files", lambda: [f])
    rows = service.rag_list_indexes()
    assert rows == [{"name": "myidx", "chunk_count": 3}]
