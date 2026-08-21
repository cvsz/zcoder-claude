"""interfaces/cli/commands/research_commands.py — CLI presentation for Deep Research
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/research_service.py.
"""

from pathlib import Path

from application import research_service as service
from infrastructure.anthropic_api.research_gateway import DeepResearchGateway


def cmd_research(
    topic: str,
    api_key: str,
    model: str,
    depth: int = 4,
    source_urls: list | None = None,
    output: str | None = None,
):
    print(f"🔎 Deep Research: {topic!r}  (depth={depth})\\n")
    gateway = DeepResearchGateway(api_key=api_key, model=model)
    report = service.run_research(gateway, topic, depth=depth, source_urls=source_urls)
    md = report.to_markdown()
    if output:
        Path(output).write_text(md)
        print(f"✓ Report saved to {output}")
    else:
        print(md)
