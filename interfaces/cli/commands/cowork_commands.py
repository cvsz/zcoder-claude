"""
interfaces/cli/commands/cowork_commands.py — CLI presentation for the
Cowork bounded context
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Only print() lives here. Extracted 2026-08-22 from cowork.py's
cmd_cowork/cmd_cowork_list, print-for-print identical; run()'s original
stream_progress banner prints now arrive via the on_progress callback.
"""

from pathlib import Path

from application import cowork_service as service
from domain.cowork import COWORK_TASKS

__all__ = [
    "cmd_cowork",
    "cmd_cowork_list",
]


def cmd_cowork(
    task_type: str,
    prompt: str,
    api_key: str,
    model: str,
    files: list[str] | None = None,
    depth: int = 3,
    output_fmt: str = "markdown",
    output_file: str | None = None,
):
    result = service.run_cowork_task(
        api_key=api_key,
        model=model,
        task_type=task_type,
        prompt=prompt,
        files=files,
        depth=depth,
        output_fmt=output_fmt,
        on_progress=print,
    )

    print(result["output"])

    u = result.get("usage", {})
    # .get() rather than the original's result['task_name']: the original
    # crashed with a KeyError here whenever run() returned its error dict
    # (unknown task type / API error) — preserved output, minus the crash.
    print(
        f"\n\033[90m[{result.get('task_name', '-')}  in={u.get('input_tokens',0)}  out={u.get('output_tokens',0)}]\033[0m"
    )

    if output_file:
        Path(output_file).write_text(result["output"])
        print(f"\033[92m✓ Saved to {output_file}\033[0m")

    return result


def cmd_cowork_list():
    print("\nCowork task types:")
    print(f"\n  {'TYPE':<14}{'NAME':<26}DESCRIPTION")
    print("  " + "─" * 70)
    for key, task in COWORK_TASKS.items():
        print(f"  {key:<14}{(task['icon']+' '+task['name']):<26}{task['description']}")
    print('\n  Usage: zcoder --cowork <type> --cowork-prompt "your task"')
