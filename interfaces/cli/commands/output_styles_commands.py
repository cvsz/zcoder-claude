"""interfaces/cli/commands/output_styles_commands.py — CLI presentation for Output Styles
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/output_styles_service.py.
"""


from application import output_styles_service as service


def cmd_list_output_styles(plugin_dirs: list | None = None):
    styles = service.get_all_styles(plugin_dirs)
    print("\nOutput styles:")
    for s in styles:
        tag = (
            "(builtin)" if s["builtin"] else f"(plugin: {s.get('plugin')})" if s.get("plugin") else "(custom)"
        )
        print(f"  {s['name']:<14} {tag:<22} {s['description']}")
    from domain.output_styles import PROJECT_STYLES_DIR, USER_STYLES_DIR

    print(f"\nProject styles dir: {PROJECT_STYLES_DIR}")
    print(f"User styles dir:    {USER_STYLES_DIR}")
