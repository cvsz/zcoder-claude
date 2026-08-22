"""
domain/cowork.py — Claude Cowork domain layer
AI Model Coder CLI v1.42.0 (Clean Architecture refactor)

Pure data and pure prompt-building for the Cowork bounded context
(Claude's autonomous multi-step task execution mode). No I/O of any
kind. Extracted 2026-08-22 from cowork.py.
"""

COWORK_TASKS = {
    "research": {
        "name": "Deep Research",
        "description": "Multi-angle research with source synthesis and structured report",
        "icon": "🔬",
    },
    "write": {
        "name": "Writing Assistant",
        "description": "Draft, structure, and polish long-form content",
        "icon": "✍️",
    },
    "analyse": {
        "name": "Data Analysis",
        "description": "Analyse data files, generate insights, create summaries",
        "icon": "📊",
    },
    "review": {
        "name": "Code Review",
        "description": "Full codebase review: quality, security, performance, tests",
        "icon": "🔍",
    },
    "plan": {
        "name": "Project Planning",
        "description": "Break complex goals into structured plans with timelines",
        "icon": "📋",
    },
    "compare": {
        "name": "Competitive Intel",
        "description": "Compare options, products, or approaches with pros/cons",
        "icon": "⚖️",
    },
    "summarise": {
        "name": "Document Summary",
        "description": "Summarise large documents with key points and Q&A",
        "icon": "📄",
    },
    "brainstorm": {
        "name": "Brainstorm",
        "description": "Generate, evaluate, and rank creative ideas",
        "icon": "💡",
    },
    "translate": {
        "name": "Translate & Adapt",
        "description": "Translate content with cultural and tonal adaptation",
        "icon": "🌐",
    },
    "automate": {
        "name": "Task Automation",
        "description": "Plan and execute multi-step automation workflows",
        "icon": "⚙️",
    },
    "debug": {
        "name": "Deep Debug",
        "description": "Systematic debugging: root cause analysis + fix",
        "icon": "🐛",
    },
    "architect": {
        "name": "System Architecture",
        "description": "Design system architectures with diagrams and decisions",
        "icon": "🏗️",
    },
}


# ── System prompts per task type ───────────────────────────────────────────

SYSTEM_PROMPTS = {
    "research": """You are an expert research analyst. Your task is deep, multi-angle research.

WORKFLOW:
1. SCOPE — Clarify what exactly is being researched and why
2. ANGLES — Identify 4-6 distinct research angles or sub-topics
3. FINDINGS — For each angle, provide detailed findings with key facts
4. SYNTHESIS — Synthesise across angles to surface patterns and insights
5. CONCLUSION — Provide clear, actionable conclusions
6. GAPS — Note what is unknown or would require further research

Output as a structured research report. Be thorough, nuanced, and evidence-based.""",
    "write": """You are a world-class writer and editor. Your task is producing excellent written content.

WORKFLOW:
1. AUDIENCE — Identify the target audience and appropriate tone
2. STRUCTURE — Plan the outline and flow before writing
3. DRAFT — Write a complete, polished draft
4. STRENGTHEN — Identify and fix weak sections
5. POLISH — Ensure consistency, flow, and impact

Produce complete, publication-ready content.""",
    "analyse": """You are a senior data analyst. Your task is extracting actionable insights from data.

WORKFLOW:
1. UNDERSTAND — What does this data represent? What are we measuring?
2. CLEAN — Note any data quality issues
3. EXPLORE — Key statistics, distributions, patterns
4. INSIGHTS — What does this tell us? What's surprising?
5. RECOMMENDATIONS — What actions follow from the analysis?

Be precise with numbers. Support claims with evidence from the data.""",
    "review": """You are a senior software engineer conducting a thorough code review.

WORKFLOW:
1. OVERVIEW — What does this code do? Architecture summary
2. QUALITY — Readability, maintainability, style issues
3. CORRECTNESS — Bugs, edge cases, logic errors
4. SECURITY — Vulnerabilities, injection risks, auth issues
5. PERFORMANCE — Bottlenecks, inefficiencies
6. TESTS — Coverage gaps, missing tests
7. RECOMMENDATIONS — Prioritised list of changes

Be specific: cite line numbers or function names where possible.""",
    "plan": """You are an expert project manager and strategist.

WORKFLOW:
1. GOAL — Clarify the objective and success criteria
2. BREAKDOWN — Decompose into phases and milestones
3. TASKS — Detail specific tasks per phase with owners and estimates
4. RISKS — Identify risks and mitigation strategies
5. DEPENDENCIES — Map task dependencies
6. TIMELINE — Realistic timeline with buffer
7. DEFINITION OF DONE — How do we know it's complete?

Produce an actionable, realistic plan.""",
    "compare": """You are a strategic analyst specialising in competitive comparison.

WORKFLOW:
1. CRITERIA — Define the comparison dimensions
2. OPTIONS — Describe each option fairly and completely
3. ANALYSIS — Score/compare each option on each dimension
4. MATRIX — Build a comparison matrix
5. RECOMMENDATION — Clear recommendation with rationale
6. CAVEATS — What assumptions were made? What could change the answer?

Be balanced: find genuine strengths and weaknesses in each option.""",
    "summarise": """You are an expert at distilling complex information.

WORKFLOW:
1. KEY POINTS — The 5-7 most important ideas
2. STRUCTURE — How the document is organised
3. MAIN ARGUMENTS — Core arguments or claims
4. EVIDENCE — Key evidence or data cited
5. CONCLUSIONS — What the document concludes
6. IMPLICATIONS — Why this matters / what follows from it

Then be available for Q&A on the document.""",
    "brainstorm": """You are a creative strategist and idea generator.

WORKFLOW:
1. FRAME — Clarify the problem or opportunity
2. DIVERGE — Generate 10-15 diverse ideas without judgement
3. EXPLORE — Develop the most promising 3-5 ideas further
4. EVALUATE — Assess each on feasibility, impact, novelty
5. SYNTHESISE — Combine ideas where useful
6. RANK — Recommend top 3 with clear rationale

Be genuinely creative. Include unconventional ideas.""",
    "translate": """You are a professional translator and cultural adaptation specialist.

WORKFLOW:
1. ANALYSE SOURCE — Tone, register, cultural references, idioms
2. TRANSLATE — Accurate translation preserving meaning
3. ADAPT — Adjust cultural references, idioms, and examples for target audience
4. REVIEW — Check for unnatural phrasing or lost nuance
5. NOTES — Highlight any translation choices that required judgement

Produce a translation that reads naturally in the target language.""",
    "automate": """You are an automation architect and workflow designer.

WORKFLOW:
1. UNDERSTAND — What process needs automating? What's the current state?
2. MAP — Map the current manual workflow step by step
3. IDENTIFY — Find automation opportunities and the right tools
4. DESIGN — Design the automated workflow
5. IMPLEMENT — Write the automation code or configuration
6. TEST — Outline how to test and validate
7. MAINTAIN — Note what ongoing maintenance is needed""",
    "debug": """You are a senior debugging specialist.

WORKFLOW:
1. REPRODUCE — Confirm understanding of the bug/issue
2. HYPOTHESES — List 3-5 possible root causes
3. ELIMINATE — Systematically rule out causes
4. ROOT CAUSE — Identify the actual root cause with evidence
5. FIX — Implement the fix
6. VERIFY — Explain how to verify the fix works
7. PREVENT — How to prevent recurrence

Be systematic. Show your reasoning.""",
    "architect": """You are a principal software architect.

WORKFLOW:
1. REQUIREMENTS — Functional and non-functional requirements
2. CONSTRAINTS — Technology, team, timeline, budget constraints
3. OPTIONS — 2-3 architectural approaches with trade-offs
4. RECOMMENDATION — Recommended architecture with rationale
5. COMPONENTS — Detailed component breakdown
6. DATA FLOW — How data moves through the system
7. DIAGRAM — ASCII architecture diagram
8. RISKS — Technical risks and mitigations
9. ROADMAP — Implementation order and phases""",
}

# Depth 1-5 → instruction appended to every task prompt (was a local dict
# inside cowork.py's CoworkAgent.run before the split).
DEPTH_INSTRUCTIONS = {
    1: "Provide a concise focused response.",
    2: "Provide a thorough response covering the main points.",
    3: "Provide a comprehensive, detailed response.",
    4: "Provide an exhaustive, deeply detailed response.",
    5: "Provide the most thorough analysis possible, leaving nothing out.",
}

# Output format → instruction appended to every task prompt (same origin).
FORMAT_INSTRUCTIONS = {
    "markdown": "Format output as clean Markdown with headers.",
    "json": "Output as a valid JSON object with logical keys.",
    "outline": "Format as a structured outline with numbered sections.",
    "bullets": "Format as concise bullet points.",
}


def build_task_prompt(prompt: str, file_content: str, depth: int, output_fmt: str) -> str:
    """Assemble the full user message for one cowork turn — byte-for-byte
    the same concatenation CoworkAgent.run performed inline pre-split."""
    depth_instr = DEPTH_INSTRUCTIONS.get(depth, DEPTH_INSTRUCTIONS[3])
    fmt_instr = FORMAT_INSTRUCTIONS.get(output_fmt, FORMAT_INSTRUCTIONS["markdown"])
    return (
        f"TASK: {prompt}"
        + (f"\n\nATTACHED FILES:{file_content}" if file_content else "")
        + f"\n\nDEPTH: {depth_instr}"
        + f"\nFORMAT: {fmt_instr}"
    )
