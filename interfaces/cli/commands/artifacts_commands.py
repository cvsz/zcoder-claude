"""
interfaces/cli/commands/artifacts_commands.py — CLI presentation for the
Artifacts bounded context
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Only print() lives here — all real work delegated to
application/artifacts_service.py. Extracted 2026-08-22 from artifacts.py's
eleven cmd_artifact_* functions, print-for-print identical.
"""

from application import artifacts_service as service

__all__ = [
    "cmd_artifact_create",
    "cmd_artifact_list",
    "cmd_artifact_show",
    "cmd_artifact_iterate",
    "cmd_artifact_export",
    "cmd_artifact_tag",
    "cmd_artifact_attach",
    "cmd_artifact_diff",
    "cmd_artifact_delete",
    "cmd_artifact_types",
    "cmd_artifact_export_all",
]


def cmd_artifact_create(
    name, prompt, artifact_type="code", language="", tags=None, project_id="", coder=None
):
    print(f"\033[94mℹ Generating artifact '{name}' (type: {artifact_type})…\033[0m")
    meta = service.create_artifact(name, prompt, artifact_type, language, tags, project_id, coder)
    print(f"\033[92m✓ Artifact created: {meta['name']} (ID: {meta['id']}, v1)\033[0m")
    print(service.show_artifact(meta["id"]))
    return meta


def cmd_artifact_list(query="", artifact_type="", project_id="", tag=""):
    arts = service.list_artifacts(query, artifact_type, project_id, tag)
    if not arts:
        print("No artifacts found.")
        return
    print(f"\n{'ID':<14}{'NAME':<25}{'TYPE':<12}{'VER':<6}{'TAGS':<20}{'UPDATED'}")
    print("─" * 85)
    for a in arts:
        tags = ", ".join(a["tags"][:3]) or "—"
        print(
            f"{a['id']:<14}{a['name'][:24]:<25}{a['type']:<12}v{a['version']:<5}{tags[:19]:<20}{a['updated_at'][:10]}"
        )
    print(f"\n{len(arts)} artifact(s)")


def cmd_artifact_show(artifact_id, version=None):
    print(service.show_artifact(artifact_id, version))


def cmd_artifact_iterate(artifact_id, feedback, coder):
    print(f"\033[94mℹ Generating new version of artifact {artifact_id}…\033[0m")
    meta = service.iterate_artifact(artifact_id, feedback, coder)
    print(f"\033[92m✓ Artifact updated to v{meta['version']}\033[0m")
    print(service.show_artifact(artifact_id))


def cmd_artifact_export(artifact_id, output_path="", version=None):
    path = service.export_artifact(artifact_id, output_path, version)
    print(f"\033[92m✓ Exported to: {path}\033[0m")


def cmd_artifact_tag(artifact_id, tag):
    meta = service.add_tag(artifact_id, tag)
    print(f"\033[92m✓ Tag '{tag}' added. Tags: {', '.join(meta['tags'])}\033[0m")


def cmd_artifact_attach(artifact_id, project_id):
    service.attach_to_project(artifact_id, project_id)
    print(f"\033[92m✓ Artifact {artifact_id} attached to project {project_id}\033[0m")


def cmd_artifact_diff(artifact_id, v1, v2):
    diff = service.diff_versions(artifact_id, int(v1), int(v2))
    print(diff)


def cmd_artifact_delete(artifact_id):
    ok = service.delete_artifact(artifact_id)
    if ok:
        print(f"\033[92m✓ Artifact {artifact_id} deleted.\033[0m")
    else:
        print(f"\033[91m✗ Artifact {artifact_id} not found.\033[0m")


def cmd_artifact_types():
    print("\nAvailable artifact types:")
    for t, desc in service.artifact_types().items():
        print(f"  {t:<14} — {desc}")


def cmd_artifact_export_all(project_id, output_dir=""):
    exported = service.export_all_artifacts(project_id, output_dir)
    print(f"\033[92m✓ Exported {len(exported)} artifacts:\033[0m")
    for p in exported:
        print(f"  {p}")
