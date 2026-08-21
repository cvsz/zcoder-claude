"""interfaces/cli/commands/settings_commands.py — CLI presentation for Settings
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/settings_service.py.
"""

from application import settings_service as service


def cmd_settings_show():
    import json as __json

    result = service.get_settings_with_provenance()
    print("\nResolved settings (precedence: user < project < local < CLI flags)\n")
    if not result["settings"]:
        print("  (none set — using built-in defaults)")
    for k, v in result["settings"].items():
        src = result["provenance"].get(k, "?")
        print(f"  {k:<20} = {__json.dumps(v):<40} [{src}]")
    from domain.settings import LOCAL_SETTINGS, PROJECT_SETTINGS, USER_SETTINGS

    print(f"\n  user:    {USER_SETTINGS}  {'(exists)' if USER_SETTINGS.exists() else '(absent)'}")
    print(f"  project: {PROJECT_SETTINGS}  {'(exists)' if PROJECT_SETTINGS.exists() else '(absent)'}")
    print(f"  local:   {LOCAL_SETTINGS}  {'(exists)' if LOCAL_SETTINGS.exists() else '(absent)'}")


def cmd_status_line(model: str, cwd: str = ".", turns: int = 0, cost: float = 0.0):
    line = service.render_status_line_text(
        {
            "model": model,
            "cwd": cwd,
            "turns": turns,
            "cost": f"{cost:.4f}",
        }
    )
    print(line)
