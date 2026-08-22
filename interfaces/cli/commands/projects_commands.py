"""
interfaces/cli/commands/projects_commands.py — CLI presentation for the
Feature Projects bounded context
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Only print() lives here. Extracted 2026-08-22 from projects.py's seven
cmd_project_* functions, print-for-print identical; cmd_project_delete /
cmd_project_archive absorb the dispatcher's inline "✓ Deleted." /
"✓ Archived." prints so all presentation lives in interfaces/.
"""

from application import projects_service as service

__all__ = [
    "cmd_project_create",
    "cmd_project_list",
    "cmd_project_show",
    "cmd_project_delete",
    "cmd_project_archive",
    "cmd_project_plan",
    "cmd_project_run",
    "cmd_project_add_task",
    "cmd_project_templates",
]


def cmd_project_create(name, description="", template="blank"):
    m = service.create_project(name, description, template)
    print(f"\033[92m✓ Project created: {m['name']} (ID: {m['id']})\033[0m")
    print(f"  Template: {template}  |  Tasks: {len(m['tasks'])}")
    print(f"  Workspace: {service.project_workspace_dir(m['id'])}")
    return m


def cmd_project_list():
    projects = service.list_projects()
    if not projects:
        print("No projects yet. Create one with --project-create <name>")
        return
    print(f"\n{'ID':<14}{'NAME':<25}{'STATUS':<12}{'PROGRESS':<12}{'UPDATED'}")
    print("─" * 75)
    for p in projects:
        done = p["tasks_done"]
        total = p["tasks_total"]
        prog = f"{done}/{total}" if total else "—"
        print(f"{p['id']:<14}{p['name'][:24]:<25}{p['status']:<12}{prog:<12}{p['updated_at'][:10]}")


def cmd_project_show(project_id):
    print(service.show_project(project_id))


def cmd_project_delete(project_id):
    service.delete_project(project_id)
    print("✓ Deleted.")


def cmd_project_archive(project_id):
    service.archive_project(project_id)
    print("✓ Archived.")


def cmd_project_plan(project_id, coder):
    print(f"\033[94mℹ Generating AI plan for project {project_id}…\033[0m")
    result = service.plan_project(project_id, coder)
    print(result)
    print(service.show_project(project_id))


def cmd_project_run(project_id, task_id, coder):
    if task_id == "all":
        results = service.run_all_pending(project_id, coder, on_progress=print)
        print(f"\033[92m✓ Completed {len(results)} tasks.\033[0m")
    else:
        result = service.run_project_task(project_id, task_id, coder)
        print(result)


def cmd_project_add_task(project_id, title, description="", agent="", priority="medium"):
    t = service.add_task(project_id, title, description, agent, priority)
    print(f"\033[92m✓ Task added: [{t['id']}] {t['title']}\033[0m")


def cmd_project_templates():
    templates = service.list_templates()
    print("\nAvailable project templates:")
    descriptions = {
        "blank": "Empty project — start from scratch",
        "web_app": "Full-stack web app (backend + frontend + DB + security)",
        "api": "REST API with auth, tests, and OpenAPI docs",
        "cli_tool": "Command-line tool with packaging and README",
        "data_pipeline": "ETL/data pipeline with validation and monitoring",
        "ml_model": "Machine learning project from data prep to serving",
    }
    for t in templates:
        print(f"  {t:<18} — {descriptions.get(t, '')}")
