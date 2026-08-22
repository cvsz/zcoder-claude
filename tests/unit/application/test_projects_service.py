"""tests/unit/application/test_projects_service.py

Covers application/projects_service.py — the use-case layer for the
Feature Projects bounded context, extracted 2026-08-22 from projects.py.
Per this project's DoD (exec-planning.md §6), every function here needs
direct unit test coverage.

Store-level tests patch PROJECTS_DIR on its DEFINING module
(infrastructure.local_storage.projects_store) — the "second repoint"
pattern from exec-planning.md §5 step 5: patching an importing module's
re-export has no effect, since Python resolves module-level globals in
the defining namespace.
"""

import json

import application.projects_service as service
import infrastructure.local_storage.projects_store as store
from domain.projects import ProjectStatus, Task


class FakeCoder:
    def __init__(self, reply="generated plan"):
        self.reply = reply
        self.calls = []

    def generate(self, prompt, system=None):
        self.calls.append({"prompt": prompt, "system": system})
        return self.reply


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path / "projects"


# ── domain ────────────────────────────────────────────────────────────


def test_task_round_trips_through_dict():
    t = Task("Do thing", "desc", "coder", "high")
    d = t.to_dict()
    assert d["status"] == "todo" and d["id"] == t.id
    t2 = Task.from_dict(dict(d))
    assert t2.id == t.id and t2.title == "Do thing"


def test_project_status_constants():
    assert ProjectStatus.PLANNING == "planning"
    assert ProjectStatus.ARCHIVED == "archived"


# ── CRUD ──────────────────────────────────────────────────────────────


def test_create_project_writes_manifest_and_workspace(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    m = service.create_project("My Proj", "desc", "api")
    assert m["status"] == ProjectStatus.PLANNING
    manifest = base / m["id"] / "project.json"
    assert manifest.exists()
    assert (base / m["id"] / "workspace").is_dir()
    with open(manifest) as f:
        on_disk = json.load(f)
    assert len(on_disk["tasks"]) == 6  # the api template's tasks


def test_create_project_unknown_template_falls_back_to_blank(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("X", template="does-not-exist")
    assert m["tasks"] == []


def test_list_projects_summarises_task_progress(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("P1")
    service.add_task(m["id"], "T1")
    t2 = service.add_task(m["id"], "T2")
    store.ProjectManager().complete_task(m["id"], t2["id"])
    rows = service.list_projects()
    assert rows[0]["tasks_done"] == 1 and rows[0]["tasks_total"] == 2


def test_show_project_renders_header_and_tasks(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("Shown", description="the description", template="blank")
    service.add_task(m["id"], "Only task", priority="high")
    out = service.show_project(m["id"])
    assert "PROJECT: Shown" in out and "the description" in out and "Only task" in out


def test_delete_and_archive_project(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    m = service.create_project("Gone")
    archived = service.archive_project(m["id"])
    assert archived["status"] == ProjectStatus.ARCHIVED
    assert service.delete_project(m["id"]) is True
    assert not (base / m["id"]).exists()
    assert service.delete_project(m["id"]) is False


def test_add_task_appends_to_manifest(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("P")
    t = service.add_task(m["id"], "New task", "d", "tester", "critical")
    assert t["priority"] == "critical"
    fresh = store.ProjectManager().get_project(m["id"])
    assert [x["title"] for x in fresh["tasks"]] == ["New task"]


# ── AI-powered actions ────────────────────────────────────────────────


def test_plan_project_parses_json_array_into_tasks(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("Planned")
    reply = json.dumps(
        [
            {"title": "A", "description": "da", "agent": "code_generator", "priority": "high"},
            {"title": "B", "description": "db", "agent": "testing_agent", "priority": "low"},
        ]
    )
    result = service.plan_project(m["id"], FakeCoder(reply))
    assert "Generated 2 tasks" in result
    fresh = store.ProjectManager().get_project(m["id"])
    assert [t["title"] for t in fresh["tasks"]] == ["A", "B"]
    assert fresh["status"] == ProjectStatus.ACTIVE


def test_plan_project_strips_markdown_fences(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("Fenced")
    reply = "```json\n[{\"title\": \"T\"}]\n```"
    result = service.plan_project(m["id"], FakeCoder(reply))
    assert "Generated 1 tasks" in result


def test_plan_project_prose_fallback_stored_as_context(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("Prose")
    result = service.plan_project(m["id"], FakeCoder("Here is a prose plan."))
    assert result == "Here is a prose plan."
    fresh = store.ProjectManager().get_project(m["id"])
    assert fresh["context"] == "Here is a prose plan."


def test_run_project_task_completes_logs_and_saves_result(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    m = service.create_project("Runner")
    t = service.add_task(m["id"], "The task")

    result = service.run_project_task(m["id"], t["id"], FakeCoder("task output"))

    assert result == "task output"
    fresh = store.ProjectManager().get_project(m["id"])
    assert fresh["tasks"][0]["status"] == "done"
    assert fresh["run_log"][0]["task_id"] == t["id"]
    saved = base / m["id"] / "workspace" / f"task_{t['id']}.md"
    assert saved.read_text() == "# The task\n\ntask output"


def test_run_project_task_missing_task_returns_error_string(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("P")
    assert "[ERROR] Task nope not found." in service.run_project_task(m["id"], "nope", FakeCoder())


def test_run_all_pending_runs_only_todo_tasks_with_progress(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    m = service.create_project("Batch")
    t1 = service.add_task(m["id"], "First")
    t2 = service.add_task(m["id"], "Second")
    store.ProjectManager().complete_task(m["id"], t2["id"])

    lines = []
    results = service.run_all_pending(m["id"], FakeCoder(), on_progress=lines.append)

    assert list(results) == [t1["id"]]
    assert lines == ["  → Running: First"]


# ── templates / workspace accessor ────────────────────────────────────


def test_list_templates_matches_builtin_registry():
    templates = service.list_templates()
    assert templates == ["blank", "web_app", "api", "cli_tool", "data_pipeline", "ml_model"]


def test_project_workspace_dir_points_inside_project(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    d = service.project_workspace_dir("abc123")
    assert str(d).endswith("abc123/workspace") or d.name == "workspace" and d.parent.name == "abc123"
