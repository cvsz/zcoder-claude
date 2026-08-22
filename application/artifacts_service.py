"""
application/artifacts_service.py — use-case layer for the Artifacts
bounded context
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Orchestrates domain/artifacts.py + infrastructure/local_storage/
artifacts_store.py — no print() of its own. Extracted 2026-08-22 from
artifacts.py; every function here is called from at least one cmd_* in
interfaces/cli/commands/artifacts_commands.py and has a direct unit test
in tests/unit/application/test_artifacts_service.py (exec-planning.md
§6 DoD).
"""

from infrastructure.local_storage.artifacts_store import ArtifactManager


def create_artifact(
    name: str,
    prompt: str,
    artifact_type: str = "code",
    language: str = "",
    tags: list | None = None,
    project_id: str = "",
    coder=None,
) -> dict:
    """Generate an artifact from a prompt and store v1."""
    return ArtifactManager().create(name, prompt, artifact_type, language, tags, project_id, coder)


def list_artifacts(query: str = "", artifact_type: str = "", project_id: str = "", tag: str = "") -> list:
    return ArtifactManager().list_artifacts(query, artifact_type, project_id, tag)


def show_artifact(artifact_id: str, version: int | None = None) -> str:
    return ArtifactManager().show(artifact_id, version)


def iterate_artifact(artifact_id: str, feedback: str, coder) -> dict:
    return ArtifactManager().iterate(artifact_id, feedback, coder)


def export_artifact(artifact_id: str, output_path: str = "", version: int | None = None) -> str:
    return ArtifactManager().export(artifact_id, output_path, version)


def add_tag(artifact_id: str, tag: str) -> dict:
    return ArtifactManager().add_tag(artifact_id, tag)


def attach_to_project(artifact_id: str, project_id: str) -> dict:
    return ArtifactManager().attach_to_project(artifact_id, project_id)


def diff_versions(artifact_id: str, v1: int, v2: int) -> str:
    return ArtifactManager().diff(artifact_id, v1, v2)


def delete_artifact(artifact_id: str) -> bool:
    return ArtifactManager().delete(artifact_id)


def artifact_types() -> dict:
    from domain.artifacts import ARTIFACT_TYPES

    return dict(ARTIFACT_TYPES)


def export_all_artifacts(project_id: str, output_dir: str = "") -> list:
    return ArtifactManager().export_all(project_id, output_dir)
