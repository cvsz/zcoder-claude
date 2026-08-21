"""interfaces/cli/commands/advisor_commands.py — CLI presentation for Advisor tool
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Only print() lives here — all real work delegated to
application/advisor_service.py.
"""

from typing import Optional

from application import advisor_service as service
from domain.advisor import build_advisor_tool
from infrastructure.anthropic_api.advisor_gateway import AdvisorGateway


def cmd_advisor(prompt: str, api_key: str, executor_model: str,
                advisor_model: str = "claude-opus-4-8",
                max_uses: Optional[int] = None,
                advisor_max_tokens: Optional[int] = None):
    print(f"\\033[94mℹ Advisor tool | executor={executor_model} advisor={advisor_model}\\033[0m\\n")
    advisor_tool = build_advisor_tool(
        advisor_model=advisor_model, max_uses=max_uses, max_tokens=advisor_max_tokens,
    )
    gateway = AdvisorGateway(api_key=api_key, executor_model=executor_model)
    result = service.run_advisor(gateway, prompt, advisor_tool)
    print(result)
    return result
