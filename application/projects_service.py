"""
application/projects_service.py — use-case layer for the Feature
Projects bounded context
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Orchestrates domain/projects.py + infrastructure/local_storage/
projects_store.py — no print() of its own (run_all_pending's per-task
progress flows through the on_progress callback to interfaces/).
Extracted 2026-08-22 from projects.py; every function here is called
from at least one cmd_* in interfaces/cli/commands/projects_commands.py
and has a direct unit test in tests/unit/application/
test_projects_service.py (exec-planning.md §6 DoD).
"""

from collections.abc import Callable

from infrastructure.local_storage.projects_store import ProjectManager, workspace_dir

_NOOP: Callable[[str], None] = lambda *a, **k: None  # noqa: E731


def create_project(name: str, description: str = "", template: str = "blank") -> dict:
    return ProjectManager().create_project(name, description, template)


def project_workspace_dir(project_id: str):
    return workspace_dir(project_id)


def list_projects() -> list:
    return ProjectManager().list_projects()


def show_project(project_id: str) -> str:
    return ProjectManager().show_project(project_id)


def delete_project(project_id: str) -> bool:
    return ProjectManager().delete_project(project_id)


def archive_project(project_id: str) -> dict:
    return ProjectManager().archive_project(project_id)


def add_task(
    project_id: str, title: str, description: str = "", agent: str = "", priority: str = "medium"
) -> dict:
    return ProjectManager().add_task(project_id, title, description, agent, priority)


def plan_project(project_id: str, coder) -> str:
    return ProjectManager().generate_plan(project_id, coder)


def run_project_task(project_id: str, task_id: str, coder) -> str:
    return ProjectManager().run_task(project_id, task_id, coder)


def run_all_pending(project_id: str, coder, on_progress: Callable[[str], None] = _NOOP) -> dict:
    return ProjectManager().run_all_pending(project_id, coder, on_progress=on_progress)


def list_templates() -> list:
    return ProjectManager().list_templates()
