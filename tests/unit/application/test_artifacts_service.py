"""tests/unit/application/test_artifacts_service.py

Covers application/artifacts_service.py — the use-case layer for the
Artifacts bounded context, extracted 2026-08-22 from artifacts.py. Per
this project's DoD (exec-planning.md §6), every function here needs
direct unit test coverage, not only indirect coverage via a CLI test
capturing stdout.

Store-level tests patch ARTIFACTS_DIR on its DEFINING module
(infrastructure.local_storage.artifacts_store) — the "second repoint"
pattern from exec-planning.md §5 step 5: patching an importing module's
re-export has no effect, since Python resolves module-level globals in
the defining namespace.
"""

import json

import application.artifacts_service as service
import infrastructure.local_storage.artifacts_store as store
from domain.artifacts import ARTIFACT_TYPES


class FakeCoder:
    def __init__(self, reply="generated content"):
        self.reply = reply
        self.calls = []

    def generate(self, prompt, system=None):
        self.calls.append({"prompt": prompt, "system": system})
        return f"{self.reply}: {prompt[:20]}"


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    return tmp_path / "artifacts"


# ── pure data ─────────────────────────────────────────────────────────


def test_artifact_types_registry_exposed_by_service():
    types = service.artifact_types()
    assert types == ARTIFACT_TYPES
    assert "code" in types and "diagram" in types


# ── create / iterate ──────────────────────────────────────────────────


def test_create_artifact_stores_v1_and_returns_meta(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("My Module", "write a module", "code", "python", ["x"], "p1", FakeCoder())
    assert meta["version"] == 1 and meta["name"] == "My Module"
    assert (base / meta["id"] / "meta.json").exists()
    assert (base / meta["id"] / "v0001.txt").read_text().startswith("generated content")


def test_create_artifact_without_coder_uses_placeholder(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("A", "p")
    content = (base / meta["id"] / "v0001.txt").read_text()
    assert content.startswith("[No coder]")


def test_iterate_artifact_appends_version_and_feedback_note(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("A", "p", coder=FakeCoder("v1 body"))
    meta2 = service.iterate_artifact(meta["id"], "make it better", FakeCoder("v2 body"))
    assert meta2["version"] == 2
    assert meta2["versions"][-1]["note"] == "make it better"
    assert (base / meta["id"] / "v0002.txt").read_text().startswith("v2 body")


def test_iterate_prompt_carries_original_and_feedback(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    coder = FakeCoder()
    meta = service.create_artifact("A", "original prompt", coder=FakeCoder())
    service.iterate_artifact(meta["id"], "the feedback", coder)
    prompt = coder.calls[0]["prompt"]
    assert "Original prompt: original prompt" in prompt and "the feedback" in prompt


# ── read / list ───────────────────────────────────────────────────────


def test_show_artifact_includes_header_history_and_content(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("Shown", "p", coder=FakeCoder("body line"))
    out = service.show_artifact(meta["id"])
    assert "ARTIFACT: Shown" in out and "--- Content (v1) ---" in out and "body line" in out


def test_list_artifacts_filters_by_tag_type_and_query(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    service.create_artifact("Alpha", "p", "docs", tags=["t1"])
    service.create_artifact("Beta", "searchable-thing", "code", tags=["t2"])

    assert len(service.list_artifacts()) == 2
    assert [a["name"] for a in service.list_artifacts(tag="t1")] == ["Alpha"]
    assert [a["name"] for a in service.list_artifacts(artifact_type="code")] == ["Beta"]
    assert [a["name"] for a in service.list_artifacts(query="searchable")] == ["Beta"]
    assert service.list_artifacts(query="nope") == []


# ── tag / attach ──────────────────────────────────────────────────────


def test_add_tag_is_idempotent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("A", "p")
    service.add_tag(meta["id"], "one")
    meta2 = service.add_tag(meta["id"], "one")
    assert meta2["tags"] == ["one"]


def test_attach_to_project_sets_project_id(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("A", "p")
    meta2 = service.attach_to_project(meta["id"], "proj-9")
    assert meta2["project_id"] == "proj-9"


# ── export / diff / delete ────────────────────────────────────────────


def test_export_artifact_writes_content_and_suggests_extension(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("My Doc", "p", "docs", coder=FakeCoder("doc body"))
    out = tmp_path / "exported.md"
    path = service.export_artifact(meta["id"], str(out))
    assert path == str(out)
    assert out.read_text() == "doc body: p"

    default_path = service.export_artifact(meta["id"])
    assert default_path.endswith("_v1.md")


def test_export_all_artifacts_exports_every_project_artifact(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    service.create_artifact("One", "p", "code", project_id="pj")
    service.create_artifact("Two", "p", "docs", project_id="pj")
    exported = service.export_all_artifacts("pj", str(tmp_path / "out"))
    assert len(exported) == 2
    for f in exported:
        assert (tmp_path / "out" / f.split("/")[-1]).exists()


def test_diff_versions_reports_difference_or_no_differences(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("A", "p", coder=FakeCoder("old"))
    service.iterate_artifact(meta["id"], "chg", FakeCoder("new"))
    diff = service.diff_versions(meta["id"], 1, 2)
    assert "-old" in diff and "+new" in diff
    assert service.diff_versions(meta["id"], 1, 1) == "No differences."


def test_delete_artifact_removes_directory_and_reports_missing(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("A", "p")
    assert service.delete_artifact(meta["id"]) is True
    assert not (base / meta["id"]).exists()
    assert service.delete_artifact("missing-id") is False


# ── store fidelity ────────────────────────────────────────────────────


def test_meta_json_round_trips_through_store_helpers(tmp_path, monkeypatch):
    base = _isolate(tmp_path, monkeypatch)
    meta = service.create_artifact("R", "p")
    with open(base / meta["id"] / "meta.json") as f:
        on_disk = json.load(f)
    assert on_disk["prompt"] == "p"
    assert store.ArtifactManager().get_meta(meta["id"]) == on_disk
