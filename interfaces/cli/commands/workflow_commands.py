"""interfaces/cli/commands/workflow_commands.py — CLI presentation for Workflow engine
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/workflow_service.py.
"""
# mypy: ignore-errors

from pathlib import Path

from application import workflow_service as service
from infrastructure.anthropic_api.workflow_gateway import WorkflowGateway


def cmd_workflow_run(
    path: str, api_key: str, input_text: str = "", output: str | None = None, verbose: bool = True
):
    wf = service.parse_workflow(service.load_workflow(path, has_yaml=True))
    print(f"⚙  Running workflow '{wf.name}' ({len(wf.steps)} steps) …\\n")
    gateway = WorkflowGateway(api_key=api_key)
    run = service.run_workflow(gateway, wf, initial_vars={"input": input_text}, verbose=verbose)
    md = run.to_markdown()
    if output:
        Path(output).write_text(md)
        print(f"\\n✓ Output → {output}")
    else:
        print("\\n" + md)
    print(f"Elapsed: {run.elapsed_s}s")


def cmd_workflow_scaffold(output: str):
    Path(output).write_text(service.scaffold_workflow())
    print(f"✓ Starter workflow saved to {output}")
