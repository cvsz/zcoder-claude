"""tests/unit/application/test_cowork_service.py

Covers application/cowork_service.py + the domain/gateway pieces of the
Cowork bounded context, extracted 2026-08-22 from cowork.py. Per this
project's DoD (exec-planning.md §6), every function in the service layer
needs direct unit test coverage.

Gateway-level tests stub CoworkAgent._post (no real HTTP); they verify
the on_progress callback wiring that replaced run()'s original inline
stream_progress prints.
"""

import application.cowork_service as service
from domain.cowork import COWORK_TASKS, DEPTH_INSTRUCTIONS, FORMAT_INSTRUCTIONS, SYSTEM_PROMPTS
from infrastructure.anthropic_api.cowork_gateway import CoworkAgent

# ── domain ────────────────────────────────────────────────────────────


def test_task_registry_has_twelve_types_with_icons():
    assert len(COWORK_TASKS) == 12
    assert all({"name", "description", "icon"} <= set(t) for t in COWORK_TASKS.values())
    assert set(SYSTEM_PROMPTS) == set(COWORK_TASKS)


def test_build_task_prompt_assembles_depth_format_and_files():
    from domain.cowork import build_task_prompt

    build = build_task_prompt("do the thing", "", 2, "json")
    assert build.startswith("TASK: do the thing")
    assert f"DEPTH: {DEPTH_INSTRUCTIONS[2]}" in build
    assert f"FORMAT: {FORMAT_INSTRUCTIONS['json']}" in build
    assert "ATTACHED FILES" not in build

    with_files = build_task_prompt("t", "\n\n--- File: a.txt ---\nx\n", 5, "bullets")
    assert "ATTACHED FILES:\n\n--- File: a.txt ---" in with_files


def test_build_task_prompt_falls_back_for_unknown_depth_and_format():
    from domain.cowork import build_task_prompt

    p = build_task_prompt("t", "", 99, "xml")
    assert DEPTH_INSTRUCTIONS[3] in p and FORMAT_INSTRUCTIONS["markdown"] in p


# ── gateway ───────────────────────────────────────────────────────────


def _agent_with(monkeypatch, reply=None, error=None):
    agent = CoworkAgent(api_key="k", model="claude-sonnet-5")
    data = {"error": error} if error else {"content": [{"type": "text", "text": reply or ""}], "usage": {}}
    monkeypatch.setattr(agent, "_post", lambda payload: data)
    return agent


def test_run_returns_output_usage_and_task_metadata(monkeypatch):
    agent = _agent_with(monkeypatch, reply="hello")
    result = agent.run("research", "prompt")
    assert result["output"] == "hello"
    assert result["task_type"] == "research"
    assert result["task_name"] == COWORK_TASKS["research"]["name"]
    assert result["steps"] == []


def test_run_unknown_task_type_returns_error_without_calling_api(monkeypatch):
    called = {}
    agent = CoworkAgent(api_key="k")
    monkeypatch.setattr(agent, "_post", lambda payload: called.setdefault("hit", True) or {})
    result = agent.run("nope", "p")
    assert "[ERROR] Unknown task type: nope" in result["output"]
    assert not called


def test_run_error_payload_becomes_output_error(monkeypatch):
    agent = _agent_with(monkeypatch, error="boom")
    result = agent.run("write", "p")
    assert result["output"] == "[ERROR] boom"


def test_run_emits_banner_lines_through_on_progress(monkeypatch):
    agent = _agent_with(monkeypatch, reply="x")
    lines = []
    agent.run("review", "p", depth=4, output_fmt="outline", on_progress=lines.append)
    assert any("Code Review" in line for line in lines)
    assert any("Depth: 4/5" in line for line in lines)
    assert len(lines) == 3
    # The gateway's default callback is a no-op — silence lives there,
    # not in the caller (run must not crash without one).
    agent.run("review", "p")


def test_run_reads_attached_files_and_injects_them(monkeypatch, tmp_path):
    f = tmp_path / "notes.txt"
    f.write_text("attached body")
    seen = {}

    def fake_post(payload):
        seen["content"] = payload["messages"][0]["content"]
        return {"content": [{"type": "text", "text": "ok"}], "usage": {}}

    agent = CoworkAgent(api_key="k")
    monkeypatch.setattr(agent, "_post", fake_post)
    agent.run("summarise", "p", files=[str(f)])
    assert "--- File:" in seen["content"] and "attached body" in seen["content"]

    missing = tmp_path / "nope.txt"
    agent.run("summarise", "p", files=[str(missing)])
    assert "Could not read" in seen["content"]


# ── application service ───────────────────────────────────────────────


def test_run_cowork_task_delegates_to_gateway_with_callbacks(monkeypatch):
    seen = {}
    lines = []

    class FakeAgent:
        def __init__(self, api_key, model):
            seen["api_key"], seen["model"] = api_key, model

        def run(self, task_type, prompt, files=None, depth=3, output_fmt="markdown", on_progress=None):
            seen.update(task_type=task_type, prompt=prompt, files=files, depth=depth,
                        output_fmt=output_fmt)
            on_progress("banner")
            return {"output": "done", "task_name": "T"}

    monkeypatch.setattr(service, "CoworkAgent", FakeAgent)
    result = service.run_cowork_task(
        "key", "claude-opus-5", "plan", "build it",
        files=["a.txt"], depth=5, output_fmt="bullets", on_progress=lines.append,
    )
    assert result["output"] == "done"
    assert seen == {
        "api_key": "key", "model": "claude-opus-5", "task_type": "plan",
        "prompt": "build it", "files": ["a.txt"], "depth": 5, "output_fmt": "bullets",
    }
    assert lines == ["banner"]


def test_run_cowork_task_default_is_silent(monkeypatch):
    seen = {}

    class FakeAgent:
        def __init__(self, api_key, model):
            pass

        def run(self, task_type, prompt, files=None, depth=3, output_fmt="markdown", on_progress=None):
            seen["cb"] = on_progress
            return {"output": "done", "task_name": "T"}

    monkeypatch.setattr(service, "CoworkAgent", FakeAgent)
    result = service.run_cowork_task("k", "m", "write", "p")
    seen["cb"]("quiet")  # the default callback must swallow progress silently
    assert result["output"] == "done"
