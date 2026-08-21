"""application/research_service.py — use-case layer for Deep Research
AI Model Coder CLI v1.55.0 (Clean Architecture refactor, Phase D, Context #9)

Orchestrates domain/research.py + infrastructure/anthropic_api/
research_gateway.py — no print() of its own.
"""

from typing import List, Optional

from domain.research import (
    SYS_PLAN, SYS_ANAL, SYS_SYNTH,
    SubQ, Report, parse_subquestions, parse_findings,
)
from infrastructure.anthropic_api.research_gateway import DeepResearchGateway


def plan_research(gateway: DeepResearchGateway, topic: str, depth: int = 4) -> List[SubQ]:
    raw = gateway._call(SYS_PLAN,
        f"Break '{topic}' into exactly {depth} focused, non-overlapping research "
        "sub-questions. Return ONLY a JSON array of strings, nothing else.")
    qs = parse_subquestions(raw, depth)
    return [SubQ(question=q) for q in qs]


def gather_research(gateway: DeepResearchGateway, sq: SubQ,
                    source_urls: Optional[List[str]] = None) -> SubQ:
    ctx_parts = []
    for url in (source_urls or []):
        body = gateway.fetch_url(url)
        ctx_parts.append(f"[{url}]\\n{body}")
        sq.sources.append(url)
    ctx = "\\n\\n".join(ctx_parts)
    raw = gateway._call(SYS_ANAL,
        f"Answer this research sub-question thoroughly.\\n"
        f"Sub-question: {sq.question}\\n\\n"
        + (f"Source material:\\n{ctx}\\n\\n" if ctx else
           "(No sources — answer from knowledge; flag claims that need verification.)\\n\\n")
        + "Return 3–6 concise bullet-point findings.")
    sq.findings = parse_findings(raw)
    sq.answered = True
    return sq


def synthesize_research(gateway: DeepResearchGateway, topic: str,
                        sqs: List[SubQ]) -> str:
    block = "\\n\\n".join(
        f"Q: {sq.question}\\n" + "\\n".join(f"- {f}" for f in sq.findings)
        for sq in sqs)
    return gateway._call(SYS_SYNTH,
        f'Synthesize these findings on "{topic}" into 4–8 coherent sentences '
        "that connect sub-questions rather than list them. Note tensions or gaps.\\n\\n"
        + block, max_tokens=1024)


def run_research(gateway: DeepResearchGateway, topic: str, depth: int = 4,
                 source_urls: Optional[List[str]] = None) -> Report:
    sqs = plan_research(gateway, topic, depth)
    for sq in sqs:
        gather_research(gateway, sq, source_urls)
    synthesis = synthesize_research(gateway, topic, sqs)
    return Report(topic=topic, sub_questions=sqs, synthesis=synthesis)
