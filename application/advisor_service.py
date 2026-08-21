"""application/advisor_service.py — use-case layer for Advisor tool
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/advisor.py + infrastructure/anthropic_api/
advisor_gateway.py — no print() of its own.
"""

from typing import Optional

from infrastructure.anthropic_api.advisor_gateway import AdvisorGateway


def run_advisor(gateway: AdvisorGateway, prompt: str, advisor_tool: dict,
                extra_tools: Optional[list] = None, system: Optional[str] = None,
                max_advisor_calls: int = 10) -> str:
    result, _, _ = gateway.run(prompt, advisor_tool, extra_tools, system, max_advisor_calls)
    if "error" in result:
        return f"[ERROR] {result['error']}"
    return result.get("text", "")
