"""
interfaces/cli/commands/code_agent_commands.py — CLI presentation for
Code Execution tool, Hooks, Permissions, Plan Mode, Multi-Agent Router
AI Model Coder CLI v1.48.0 (Clean Architecture refactor, Phase C)

Only print() lives here — all real work is delegated to
application/code_agent_service.py. Extracted 2026-08-16 from
claude_code_exec.py, claude_hooks_perms_plan.py, claude_router.py.
"""

from pathlib import Path
from typing import Optional

from application import code_agent_service as service

__all__ = [
    "cmd_code_exec", "cmd_code_debug",
    "cmd_hooks_add", "cmd_hooks_list", "cmd_hooks_remove",
    "cmd_perms_list", "cmd_perms_add",
    "cmd_plan", "cmd_route", "cmd_route_list",
]


# ── Code Execution tool ──────────────────────────────────────────────────

def cmd_code_exec(prompt: str, api_key: str, model: str, file_ids: Optional[list] = None,
                   output_dir: Optional[str] = None,
                   code_exec_version: str = "code_execution_20260521"):
    print("\033[94mℹ Code Execution Tool (Anthropic sandbox)\033[0m\n")

    def on_file_saved(path):
        print(f"  \033[92m✓ Image saved: {path}\033[0m")

    result = service.run_code_exec(prompt, api_key, model, file_ids=file_ids,
                                    output_dir=output_dir, code_exec_version=code_exec_version,
                                    on_file_saved=on_file_saved)
    print(result["text"])
    if result["outputs"]:
        print("\n\033[90m── Execution Trace ─────────────────────\033[0m")
        for out in result["outputs"]:
            ot = out.get("type", "")
            if ot in ("code", "executed_code"):
                print(f"\033[36m[code]\033[0m {out.get('code','')[:200]}")
            elif ot == "stdout":
                print(f"\033[37m[out]  {out.get('text','')[:200]}\033[0m")
            elif ot == "image_output":
                print(f"\033[35m[img]  {out.get('media_type','')}\033[0m")
    u = result.get("usage", {})
    if u:
        print(f"\n\033[90m[tokens] in={u.get('input_tokens',0)}  out={u.get('output_tokens',0)}\033[0m")
    return result


def cmd_code_debug(file_path: str, api_key: str, model: str,
                    code_exec_version: str = "code_execution_20260521"):
    print(f"\033[94mℹ Debugging {file_path} with live execution…\033[0m\n")
    result = service.debug_code(file_path, api_key, model, code_exec_version=code_exec_version)
    print(result["text"])
    return result


# ── Hooks ────────────────────────────────────────────────────────────────

def cmd_hooks_add(event: str, command: str, tool_match: Optional[str] = None):
    service.hooks_add(event, command, tool_match)
    print(f"✓ Hook registered for {event}: {command}")


def cmd_hooks_list():
    hooks = service.hooks_list()
    if not hooks:
        print("No hooks registered.")
        return
    for i, h in enumerate(hooks):
        match = f" [match={h.tool_match}]" if h.tool_match else ""
        print(f"  {i}. [{h.event.value}]{match}  {h.command}")


def cmd_hooks_remove(idx: int):
    if service.hooks_remove(idx):
        print(f"✓ Hook {idx} removed.")
    else:
        print(f"No hook at index {idx}")


# ── Permissions ──────────────────────────────────────────────────────────

def cmd_perms_list():
    rules = service.perms_list()
    print(f"{'Pattern':<25} {'Decision':<8} Reason")
    print("─" * 55)
    for r in rules:
        print(f"  {r.pattern:<23} {r.decision.value:<8} {r.reason}")


def cmd_perms_add(pattern: str, decision: str, reason: str = ""):
    service.perms_add(pattern, decision, reason)
    print(f"✓ Rule added: {pattern} → {decision}")


# ── Plan Mode ────────────────────────────────────────────────────────────

def cmd_plan(task: str, api_key: str, model: str, context: str = "",
             execute: bool = False, output: Optional[str] = None):
    plan = service.plan_propose(task, api_key, model, context)
    print(plan.to_markdown())
    if execute:
        print("\nExecuting …\n")

        def on_step_start(step):
            print(f"  Step {step.number}: {step.description}")

        def on_step(step):
            print(f"  → {(step.result or '')[:200]}\n")

        service.plan_execute_all(plan, api_key, model, on_step_start=on_step_start, on_step=on_step)
        if output:
            md = plan.to_markdown() + "\n\n" + "\n\n".join(
                f"## Step {s.number}\n{s.result or ''}" for s in plan.steps)
            Path(output).write_text(md)
            print(f"✓ Saved to {output}")
    else:
        print("\n(Not executed — re-run with --execute to approve and run.)")


# ── Multi-Agent Router ───────────────────────────────────────────────────

def cmd_route(prompt: str, api_key: str, model: str, explain: bool = False,
              parallel: bool = False, extra_table: Optional[dict] = None):
    def on_route(agent_name, reason):
        print(f"\033[90m→ Routing to [{agent_name}]: {reason}\033[0m\n")

    answer = service.route_query(prompt, api_key, model, explain=explain, parallel=parallel,
                                  extra_table=extra_table, on_route=on_route)
    print(answer)


def cmd_route_list(extra_table: Optional[dict] = None):
    table = service.route_list_table(extra_table)
    print("\n\033[94mRouting Table\033[0m")
    for name, desc in sorted(table.items()):
        print(f"  \033[1m{name:<14}\033[0m {desc}")
    print()
