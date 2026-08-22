import argparse

from domain.agents.role_prompts import AGENT_SYSTEM_PROMPTS
from domain.personalities import PERSONALITIES
from version import VERSION

try:
    from domain.models.catalog import UPGRADE_TARGETS
except ImportError:
    UPGRADE_TARGETS = {}


def build_parser():
    from domain.models.catalog import UPGRADE_TARGETS

    p = argparse.ArgumentParser(
        prog="zcoder",
        description=f"AI Model Coder CLI v{VERSION}",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    g = p.add_argument_group("Global")
    g.add_argument("-p", "--prompt")
    g.add_argument("-f", "--file")
    g.add_argument("-o", "--output")
    g.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Start a persistent multi-turn chat REPL (see claude_interactive.py)",
    )
    g.add_argument(
        "--interactive-system",
        metavar="TEXT",
        dest="interactive_system",
        help="Starting system prompt for --interactive",
    )
    g.add_argument(
        "--tui",
        action="store_true",
        help="Launch the full-screen Textual TUI (see tui.py) — model/personality/"
        "agent/skill sidebar plus a streaming chat transcript, in the terminal",
    )
    g.add_argument("--model", default="claude-sonnet-5")
    g.add_argument("--temperature", type=float, default=0.3)
    g.add_argument("--max-tokens", type=int, default=4096, dest="max_tokens")
    g.add_argument("--api-key", default="", dest="api_key")
    g.add_argument(
        "--whoami",
        action="store_true",
        dest="whoami",
        help="Make a minimal Messages API call and print the anthropic-workspace-id "
        "and anthropic-organization-id response headers for --api-key",
    )
    g.add_argument("--version", action="store_true")
    g.add_argument(
        "--service-tier",
        choices=["auto", "standard_only"],
        default=None,
        dest="service_tier",
        help="Priority Tier routing (requires an existing capacity "
        "commitment; not supported on Sonnet 5 or Mythos-tier models)",
    )
    g.add_argument(
        "--inference-geo",
        choices=["us", "global"],
        default=None,
        dest="inference_geo",
        help="Data residency: 'us' pins inference to US data centers "
        "at 1.1x pricing (Opus 4.6+/Sonnet 4.6+ only)",
    )
    g.add_argument(
        "--fast-mode",
        action="store_true",
        dest="fast_mode",
        help='Research-preview reduced-latency mode (speed:"fast"); '
        "currently Opus-only and billed at a premium rate",
    )
    g.add_argument(
        "--health-check",
        action="store_true",
        dest="health_check",
        help="Run liveness/readiness checks and exit (config, API key, "
        "disk-writable); prints JSON, exit code 0=healthy 1=unhealthy",
    )
    g.add_argument(
        "--health-check-deep",
        action="store_true",
        dest="health_check_deep",
        help="With --health-check, also make one minimal live API call "
        "(use for a startup probe, not a frequent liveness probe)",
    )

    sa = p.add_argument_group("Skills & Agents")
    # --skill/--agent were accepted by the parser and never read anywhere
    # (no args.skill / args.agent reference existed in this file at all) —
    # picking a skill or agent silently had zero effect on the request.
    # Now: --skill injects that skill's description into the system prompt,
    # --agent injects a role prompt for one of the named roles --list-agents
    # already prints (previously the only place those names existed), and
    # --personality was the same story one module over — personalities.py's
    # PersonalityManager was fully implemented and even wired into
    # coder.py's Coder.generate() via personality_style, but nothing in
    # main.py ever passed personality_style to a Coder(...) call because
    # there was no flag to source it from.
    sa.add_argument("--skill", help="Prepend a named skill's system prompt (see --list-skills)")
    sa.add_argument(
        "--agent",
        choices=sorted(AGENT_SYSTEM_PROMPTS),
        help="Prepend a named agent role's system prompt (see --list-agents)",
    )
    sa.add_argument(
        "--personality",
        choices=sorted(PERSONALITIES),
        help="Apply a response style/personality (see --list-personalities)",
    )
    sa.add_argument("--list-skills", action="store_true")
    sa.add_argument("--list-agents", action="store_true")
    sa.add_argument("--list-personalities", action="store_true", dest="list_personalities")

    pr = p.add_argument_group("Feature Projects")
    pr.add_argument("--project-create", metavar="NAME")
    pr.add_argument("--project-list", action="store_true")
    pr.add_argument("--project-show", metavar="ID")
    pr.add_argument("--project-plan", metavar="ID")
    pr.add_argument("--project-run", metavar="ID")
    pr.add_argument("--project-add-task", metavar="ID")
    pr.add_argument("--project-delete", metavar="ID")
    pr.add_argument("--project-archive", metavar="ID")
    pr.add_argument("--project-templates", action="store_true")
    pr.add_argument("--project-template", default="blank")
    pr.add_argument("--project-desc", default="")
    pr.add_argument("--task", metavar="TASK_ID")
    pr.add_argument("--task-title", default="")
    pr.add_argument("--task-desc", default="")
    pr.add_argument("--task-agent", default="")
    pr.add_argument("--task-priority", default="medium")

    ar = p.add_argument_group("Artifacts")
    ar.add_argument("--artifact-create", metavar="NAME")
    ar.add_argument("--artifact-list", action="store_true")
    ar.add_argument("--artifact-show", metavar="ID")
    ar.add_argument("--artifact-iterate", metavar="ID")
    ar.add_argument("--artifact-export", metavar="ID")
    ar.add_argument("--artifact-export-all", metavar="PROJ_ID")
    ar.add_argument("--artifact-tag", metavar="ID")
    ar.add_argument("--artifact-attach", metavar="ART_ID")
    ar.add_argument("--artifact-diff", metavar="ID")
    ar.add_argument("--artifact-delete", metavar="ID")
    ar.add_argument("--artifact-types", action="store_true")
    ar.add_argument("--artifact-type", default="code")
    ar.add_argument("--artifact-lang", default="")
    ar.add_argument("--artifact-tags", default="")
    ar.add_argument("--artifact-version", type=int)
    ar.add_argument("--artifact-query", default="")
    ar.add_argument("--artifact-project", default="")
    ar.add_argument("--tag", default="")
    ar.add_argument("--to-project", default="")
    ar.add_argument("--v1", type=int)
    ar.add_argument("--v2", type=int)
    ar.add_argument("--artifact-output-dir", default="")

    th = p.add_argument_group("Extended Thinking")
    th.add_argument("--thinking", action="store_true")
    th.add_argument("--thinking-budget", type=int, default=8000, dest="thinking_budget")
    th.add_argument("--effort", default="", choices=["", "low", "medium", "high", "xhigh", "max"])
    th.add_argument(
        "--adaptive",
        action="store_true",
        help="Force adaptive thinking (thinking.type='adaptive' + top-level "
        "output_config.effort, GA, no beta header). Default (neither this "
        "nor --effort-legacy-budget) auto-selects per model: adaptive on "
        "Opus 4.6+/Sonnet 4.6+/Sonnet 5/Opus 4.7/4.8/Fable 5/Mythos 5/Mythos "
        "Preview, legacy manual budget_tokens on Opus 4.5/Haiku 4.5/earlier",
    )
    th.add_argument(
        "--effort-legacy-budget",
        action="store_true",
        dest="effort_legacy_budget",
        help="Force the old manual thinking.type='enabled'+budget_tokens path "
        "(--thinking-budget/--effort still apply) even on a model where "
        "adaptive would otherwise be auto-selected. Errors out immediately, "
        "before any API call, on models where budget_tokens is a 400 "
        "(Opus 4.7/4.8, Sonnet 5, Fable 5, Mythos 5, Mythos Preview)",
    )
    th.add_argument("--interleaved-thinking", action="store_true", dest="interleaved_thinking")
    th.add_argument("--show-thinking", action="store_true", dest="show_thinking")
    th.add_argument(
        "--thinking-display-omitted",
        action="store_true",
        dest="thinking_display_omitted",
        help="v1.25.0: thinking.display='omitted' — faster streaming/smaller "
        "payloads for a caller that doesn't render thinking text "
        "(billing unchanged, GA, no beta header)",
    )

    p.add_argument("--stream", action="store_true")

    ws = p.add_argument_group("Web Search & Fetch")
    ws.add_argument("--web-search", action="store_true")
    ws.add_argument("--web-fetch", action="store_true")
    ws.add_argument("--max-searches", type=int, default=5, dest="max_searches")
    ws.add_argument("--no-citations", action="store_true", dest="no_citations")
    ws.add_argument("--fetch-url", metavar="URL", dest="fetch_url")
    ws.add_argument(
        "--response-inclusion",
        metavar="VALUE",
        dest="response_inclusion",
        default="",
        help="v1.24.0: drop a consumed result's blocks from the "
        'response (currently only "excluded" is documented); requires '
        "web_search_20260318/web_fetch_20260318, both defaults as of v1.24.0",
    )

    vi = p.add_argument_group("Vision")
    vi.add_argument("--vision", metavar="FILE")
    vi.add_argument("--vision-pdf", metavar="FILE", dest="vision_pdf")
    vi.add_argument("--vision-url", metavar="URL", dest="vision_url")
    vi.add_argument("--vision-code", action="store_true", dest="vision_code")
    vi.add_argument("--vision-compare", nargs=2, metavar="FILE", dest="vision_compare")
    vi.add_argument("--vision-ocr", metavar="FILE", dest="vision_ocr")
    vi.add_argument("--vision-lang", default="auto", dest="vision_lang")

    ba = p.add_argument_group("Batch API")
    ba.add_argument("--batch-submit", metavar="FILE", dest="batch_submit")
    ba.add_argument("--batch-status", metavar="ID", dest="batch_status")
    ba.add_argument("--batch-results", metavar="ID", dest="batch_results")
    ba.add_argument("--batch-cancel", metavar="ID", dest="batch_cancel")
    ba.add_argument("--batch-list", action="store_true", dest="batch_list")
    ba.add_argument("--batch-wait", action="store_true", dest="batch_wait")
    ba.add_argument("--batch-generate", type=int, default=0, dest="batch_generate")
    ba.add_argument(
        "--batch-300k-output",
        action="store_true",
        dest="batch_300k_output",
        help="Opt into 300k max output tokens per request (beta "
        "output-300k-2026-03-24), Opus 4.8/4.7/4.6 and Sonnet 5/4.6 only",
    )

    ca = p.add_argument_group("Prompt Caching")
    ca.add_argument("--cache", action="store_true")
    ca.add_argument("--cache-ttl", default="5m", choices=["5m", "1h"], dest="cache_ttl")
    ca.add_argument("--cache-warm", action="store_true", dest="cache_warm")
    ca.add_argument("--cache-system", default="", dest="cache_system")
    ca.add_argument(
        "--cache-stats",
        action="store_true",
        dest="cache_stats",
        help="With --cache: print token/hit-rate stats after the response "
        "(previously accepted by the parser but never read anywhere, "
        "so it had no effect either way — --cache always silently "
        "printed stats and there was no way to turn that off)",
    )
    ca.add_argument("--cache-docs", nargs="+", metavar="FILE", dest="cache_docs")
    ca.add_argument(
        "--cache-diagnose",
        action="store_true",
        dest="cache_diagnose",
        help="With --cache: opt into Cache diagnostics (beta) — report "
        "cache_miss_reason against this process's previous call. "
        "The client-side support for this (diagnose= on "
        "generate_cached()) has existed since v1.10.x, but no CLI "
        "flag ever set it, so it was unreachable from the CLI.",
    )
    ca.add_argument(
        "--cache-multi-turn",
        nargs="+",
        metavar="TEXT",
        dest="cache_multi_turn",
        help="Run a multi-turn cached conversation instead of a single "
        "--cache call; each TEXT is one user turn.",
    )
    ca.add_argument(
        "--cache-mid-system",
        default="",
        dest="cache_mid_system",
        help="With --cache-multi-turn: insert a mid-conversation system "
        "message (Opus 4.8 only) after the turn given by "
        "--cache-mid-system-after, without invalidating the cached "
        "prefix that came before it.",
    )
    ca.add_argument(
        "--cache-mid-system-after",
        type=int,
        default=0,
        dest="cache_mid_system_after",
        metavar="N",
        help="0-based turn index to insert --cache-mid-system after "
        "(default: 0, i.e. right after the first turn).",
    )

    tu = p.add_argument_group("Tool Use")
    tu.add_argument("--tool-agent", action="store_true", dest="tool_agent")
    tu.add_argument("--server-tool", metavar="TOOL", dest="server_tool")
    tu.add_argument("--list-server-tools", action="store_true", dest="list_server_tools")
    tu.add_argument("--max-turns", type=int, default=10, dest="max_turns")
    tu.add_argument(
        "--memory-agent",
        metavar="PROMPT",
        dest="memory_agent",
        help="Run an agent loop backed by the native memory tool (memory_20250818)",
    )
    tu.add_argument(
        "--memory-dir",
        default="~/.zcoder/memory",
        dest="memory_dir",
        help="Local directory backing --memory-agent (default: ~/.zcoder/memory)",
    )
    tu.add_argument(
        "--context-management",
        action="store_true",
        dest="context_management",
        help="With --server-tool: auto-clear stale tool results on long calls "
        "(context-management-2025-06-27 beta)",
    )
    tu.add_argument(
        "--compaction",
        action="store_true",
        dest="compaction",
        help="With --server-tool: enable server-side conversation compaction "
        "(compact_20260112 beta) instead of / alongside clear_tool_uses",
    )
    tu.add_argument(
        "--task-budget",
        type=int,
        default=0,
        dest="task_budget",
        help="With --server-tool: advisory task_budget in tokens for the full "
        "agentic loop (task-budgets-2026-03-13 beta; Opus 4.7/4.8, "
        "Fable 5, Mythos 5 only)",
    )
    tu.add_argument(
        "--ptc",
        action="store_true",
        dest="ptc",
        help="With --server-tool code_execution and --tool-file: mark those "
        "custom tools as callable from code (Programmatic Tool Calling)",
    )
    tu.add_argument(
        "--stream-tools",
        metavar="PROMPT",
        dest="stream_tools",
        help="Stream a turn with fine-grained tool input streaming, using "
        "--tool-file for the tool definitions",
    )
    tu.add_argument(
        "--mid-conv-tool-check",
        metavar="MODEL_ID",
        dest="mid_conv_tool_check",
        help="Check whether MODEL_ID supports mid-conversation tool changes "
        "(mid-conversation-tool-changes-2026-07-01 beta; Fable 5, Mythos 5, "
        "Opus 4.8, Opus 5 only)",
    )

    adv = p.add_argument_group("Advisor Tool")
    adv.add_argument(
        "--advisor",
        metavar="PROMPT",
        dest="advisor",
        help="Run PROMPT with an advisor model consulted mid-generation " "(advisor_20260301 beta)",
    )
    adv.add_argument(
        "--advisor-model",
        default="claude-opus-4-8",
        dest="advisor_model",
        help="Advisor model (default: claude-opus-4-8)",
    )
    adv.add_argument(
        "--advisor-max-uses",
        type=int,
        default=0,
        dest="advisor_max_uses",
        help="Cap on advisor tool definition's max_uses (unset = no cap)",
    )
    adv.add_argument(
        "--advisor-max-tokens",
        type=int,
        default=0,
        dest="advisor_max_tokens",
        help="Cap the advisor model's output tokens per call",
    )

    em = p.add_argument_group("Embeddings")
    em.add_argument(
        "--embed",
        metavar="TEXT",
        dest="embed",
        help="Embed TEXT via Voyage AI, print vector info (needs VOYAGE_API_KEY; "
        "Anthropic doesn't host its own embedding model)",
    )
    em.add_argument(
        "--embed-file", metavar="FILE", dest="embed_file", help="Embed each line of FILE via Voyage AI"
    )
    em.add_argument(
        "--embed-similarity",
        nargs=2,
        metavar=("A", "B"),
        dest="embed_similarity",
        help="Cosine similarity between two strings' embeddings",
    )
    em.add_argument("--embed-model", default="voyage-3.5", dest="embed_model")
    em.add_argument(
        "--embed-input-type", default="document", choices=["document", "query"], dest="embed_input_type"
    )

    so = p.add_argument_group("Structured Outputs")
    so.add_argument("--structured", action="store_true")
    so.add_argument("--schema", metavar="FILE")
    so.add_argument("--schema-inline", metavar="JSON", dest="schema_inline")
    so.add_argument("--structured-analyse", metavar="FILE", dest="structured_analyse")
    so.add_argument("--structured-extract", metavar="FILE", dest="structured_extract")

    fa = p.add_argument_group("Files API")
    fa.add_argument("--file-upload", metavar="FILE", dest="file_upload")
    fa.add_argument("--file-list", action="store_true", dest="file_list")
    fa.add_argument("--file-delete", metavar="ID", dest="file_delete")
    fa.add_argument("--file-ask", metavar="ID", dest="file_ask")
    fa.add_argument("--file-download", metavar="ID", dest="file_download")
    fa.add_argument("--file-output", default="", dest="file_output")
    fa.add_argument("--file-media-type", default="application/pdf", dest="file_media_type")

    ce = p.add_argument_group("Code Execution")
    ce.add_argument("--code-exec", action="store_true", dest="code_exec")
    ce.add_argument("--code-debug", metavar="FILE", dest="code_debug")
    ce.add_argument("--code-exec-output", default="", dest="code_exec_output")
    ce.add_argument(
        "--code-exec-version",
        metavar="VERSION",
        dest="code_exec_version",
        default="code_execution_20260521",
        help="Pin a code_execution tool version (default: code_execution_20260521 "
        "— GA, no beta header, discloses the 90s per-cell limit). Pass "
        "code_execution_20260120 or code_execution_20250522 to pin an older, "
        "still-supported version.",
    )

    tc = p.add_argument_group("Token Counting")
    tc.add_argument("--count-tokens", action="store_true", dest="count_tokens")
    tc.add_argument("--count-budget", type=int, default=0, dest="count_budget")

    ci = p.add_argument_group("Citations & RAG")
    ci.add_argument("--cite", nargs="+", metavar="FILE")
    ci.add_argument("--rag", metavar="DIR")
    ci.add_argument("--rag-pattern", default="*.md", dest="rag_pattern")

    mo = p.add_argument_group("Models API")
    mo.add_argument("--list-models", action="store_true", dest="list_models")
    mo.add_argument(
        "--list-models-legacy",
        action="store_true",
        dest="list_models_legacy",
        help="Include superseded (still-callable) models in --list-models' offline view",
    )
    mo.add_argument("--model-info", metavar="ID", dest="model_info")
    mo.add_argument(
        "--check-deprecated",
        metavar="PATH",
        dest="check_deprecated",
        help="Scan a file or directory for retired model ID strings and print migration targets",
    )
    mo.add_argument(
        "--upgrade-all",
        metavar="PATH",
        dest="upgrade_all",
        help="Rewrite EVERY known Claude model ID under PATH (retired, legacy, "
        "or just a different current model) to --upgrade-target. Unlike "
        "--check-deprecated this actually edits files. Dry-run by default.",
    )
    mo.add_argument(
        "--upgrade-target",
        choices=sorted(UPGRADE_TARGETS),
        default="fable5",
        dest="upgrade_target",
        help="Target for --upgrade-all: fable5 (claude-fable-5), opus "
        "(claude-opus-4-8), opus5 (claude-opus-5, latest Opus), or "
        "sonnet5 (claude-sonnet-5, latest Sonnet). Default: fable5",
    )
    mo.add_argument(
        "--upgrade-yes",
        action="store_true",
        dest="upgrade_yes",
        help="With --upgrade-all: actually write changes (default is a dry-run preview)",
    )
    mo.add_argument(
        "--upgrade-no-backup",
        action="store_true",
        dest="upgrade_no_backup",
        help="With --upgrade-all --upgrade-yes: skip writing .bak backup files",
    )

    f5 = p.add_argument_group("Claude Fable 5 / Mythos 5")
    f5.add_argument(
        "--fable5-info",
        action="store_true",
        dest="fable5_info",
        help="Show what's known about Fable 5 / Mythos 5 (pricing, context, refusal handling)",
    )
    f5.add_argument(
        "--fable5",
        metavar="PROMPT",
        dest="fable5",
        help="Call Claude Fable 5 with refusal detection and automatic fallback",
    )
    f5.add_argument(
        "--fable5-no-fallback",
        action="store_true",
        dest="fable5_no_fallback",
        help="With --fable5: disable automatic fallback on refusal (just report it). "
        "Only affects the manual retry path; no effect if "
        "--fable5-fallback-chain is set.",
    )
    f5.add_argument(
        "--fallback-model",
        default="claude-opus-4-8",
        dest="fallback_model",
        help="Manual-retry fallback model (default: claude-opus-4-8). "
        "No effect if --fable5-fallback-chain is set.",
    )
    f5.add_argument(
        "--fable5-fallback-chain",
        metavar="MODEL1,MODEL2|default",
        dest="fable5_fallback_chain",
        help="Server-side fallback (beta `fallbacks` param): comma-separated "
        "models (up to 3 total including the primary) that the platform "
        "itself retries against, in order, in the same round trip if the "
        "primary refuses. Or pass the literal value 'default' to use "
        "Anthropic's own recommended fallback models by refusal category "
        "(added 2026-07-24, needs its own beta header, sent automatically). "
        "Preferred over --fallback-model when available.",
    )

    m5 = p.add_argument_group("Claude Mythos 5 (limited access)")
    m5.add_argument(
        "--mythos5-info",
        action="store_true",
        dest="mythos5_info",
        help="Show what's known about Mythos 5 access/pricing (approval-gated, see --fable5-info for the public sibling)",
    )
    m5.add_argument(
        "--mythos5",
        metavar="PROMPT",
        dest="mythos5",
        help="Call Claude Mythos 5 directly (requires approved Project Glasswing access)",
    )

    o5 = p.add_argument_group("Claude Opus 5 (deep model-specific support)")
    o5.add_argument(
        "--opus5-info",
        action="store_true",
        dest="opus5_info",
        help="Show Opus 5's capability table (effort ladder, thinking rules, "
        "fast mode, Priority Tier, data residency)",
    )
    o5.add_argument("--opus5", metavar="PROMPT", dest="opus5", help="Call Claude Opus 5")
    o5.add_argument(
        "--opus5-effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        dest="opus5_effort",
        help="Effort level for --opus5 (default: model default)",
    )
    o5.add_argument(
        "--opus5-disable-thinking",
        action="store_true",
        dest="opus5_disable_thinking",
        help="Disable thinking for --opus5. Rejected client-side (not sent to the "
        "API) if combined with --opus5-effort xhigh or max — Opus 5 only allows "
        "disabling thinking at effort high or below.",
    )
    o5.add_argument(
        "--opus5-fast",
        action="store_true",
        dest="opus5_fast",
        help='Send speed:"fast" with --opus5 (supported on this model)',
    )
    o5.add_argument(
        "--opus5-geo",
        action="store_true",
        dest="opus5_geo",
        help='Send inference_geo:"us" with --opus5 (support unconfirmed for this '
        "model — see --opus5-info)",
    )

    s5 = p.add_argument_group("Claude Sonnet 5 (deep model-specific support)")
    s5.add_argument(
        "--sonnet5-info",
        action="store_true",
        dest="sonnet5_info",
        help="Show Sonnet 5's capability table and today's pricing "
        "($2/$10 per MTok, the permanent standard price as of "
        "2026-08-10; the previously scheduled increase to $3/$15 "
        "was cancelled)",
    )
    s5.add_argument("--sonnet5", metavar="PROMPT", dest="sonnet5", help="Call Claude Sonnet 5")
    s5.add_argument(
        "--sonnet5-geo",
        action="store_true",
        dest="sonnet5_geo",
        help='Send inference_geo:"us" with --sonnet5 (supported; 1.1x pricing)',
    )
    s5.add_argument(
        "--sonnet5-cost",
        metavar="IN,OUT",
        dest="sonnet5_cost",
        help="Estimate cost in USD for IN input / OUT output tokens on Sonnet 5, "
        "using whichever pricing tier (introductory/standard) applies today",
    )

    h45 = p.add_argument_group("Claude Haiku 4.5 (deep model-specific support)")
    h45.add_argument(
        "--haiku45-info",
        action="store_true",
        dest="haiku45_info",
        help="Show Haiku 4.5's capability table (extended, non-adaptive thinking; "
        "no fast mode; no data residency)",
    )
    h45.add_argument("--haiku45", metavar="PROMPT", dest="haiku45", help="Call Claude Haiku 4.5")
    h45.add_argument(
        "--haiku45-thinking-budget",
        type=int,
        metavar="N",
        dest="haiku45_thinking_budget",
        help="Enable extended thinking with explicit budget_tokens=N (min 1024). "
        "Haiku 4.5 uses extended (manual-budget) thinking only, never adaptive.",
    )

    ad = p.add_argument_group("Admin API (usage/cost reporting + API key management)")
    ad.add_argument(
        "--admin-api-key",
        metavar="KEY",
        dest="admin_api_key",
        help="Admin API key (sk-ant-admin...). Falls back to the "
        "ANTHROPIC_ADMIN_API_KEY env var if not given.",
    )
    ad.add_argument(
        "--usage-report",
        action="store_true",
        dest="usage_report",
        help="Print an org usage/cost report (requires an Admin API key)",
    )
    ad.add_argument(
        "--usage-report-start",
        metavar="DATE",
        dest="usage_report_start",
        help="Report start date, YYYY-MM-DD (default: 30 days ago)",
    )
    ad.add_argument(
        "--usage-report-end",
        metavar="DATE",
        dest="usage_report_end",
        help="Report end date, YYYY-MM-DD (default: today)",
    )
    ad.add_argument(
        "--usage-report-group-by",
        default="model",
        metavar="FIELD",
        dest="usage_report_group_by",
        help="Group usage report by field, e.g. model, api_key_id (default: model)",
    )
    ad.add_argument(
        "--cost-report",
        action="store_true",
        dest="cost_report",
        help="Print an org cost report (billed spend, requires an Admin API key). "
        "Distinct from --usage-report, which reports token counts, not cost.",
    )
    ad.add_argument(
        "--cost-report-start",
        metavar="DATE",
        dest="cost_report_start",
        help="Report start date, YYYY-MM-DD (default: 30 days ago)",
    )
    ad.add_argument(
        "--cost-report-end",
        metavar="DATE",
        dest="cost_report_end",
        help="Report end date, YYYY-MM-DD (default: today)",
    )
    ad.add_argument(
        "--cost-report-group-by",
        default="model",
        metavar="FIELD",
        dest="cost_report_group_by",
        help="Group cost report by field, e.g. model, api_key_id (default: model)",
    )
    ad.add_argument(
        "--admin-list-keys",
        action="store_true",
        dest="admin_list_keys",
        help="List organization API keys (requires an Admin API key)",
    )
    ad.add_argument(
        "--admin-revoke-key",
        metavar="ID",
        dest="admin_revoke_key",
        help="Revoke (deactivate) an organization API key by ID",
    )
    ad.add_argument(
        "--admin-create-key",
        metavar="NAME",
        dest="admin_create_key",
        help="Explains why key creation isn't available via the API "
        "(Console-only by design) instead of silently failing",
    )
    ad.add_argument(
        "--spend-limits-list",
        action="store_true",
        dest="spend_limits_list",
        help="List every member's resolved effective spend limit (v1.23.0, " "Claude Enterprise only)",
    )
    ad.add_argument(
        "--spend-limit-set",
        metavar=("USER_ID", "AMOUNT"),
        nargs=2,
        dest="spend_limit_set",
        help="Set a per-user spend limit override (amount: decimal string, minor units)",
    )
    ad.add_argument(
        "--spend-limit-get", metavar="ID", dest="spend_limit_get", help="Get one spend limit override by id"
    )
    ad.add_argument(
        "--spend-limit-delete",
        metavar="ID",
        dest="spend_limit_delete",
        help="Delete a per-user spend limit override",
    )
    ad.add_argument(
        "--spend-limit-requests-list",
        action="store_true",
        dest="spend_limit_requests_list",
        help="List spend limit increase requests",
    )
    ad.add_argument(
        "--spend-limit-status",
        metavar="STATUS",
        dest="spend_limit_status",
        default="",
        choices=["", "pending", "approved", "denied"],
        help="Filter --spend-limit-requests-list by status",
    )
    ad.add_argument(
        "--spend-limit-request-approve",
        metavar="ID",
        dest="spend_limit_request_approve",
        help="Approve a pending increase request",
    )
    ad.add_argument(
        "--spend-limit-request-deny",
        metavar="ID",
        dest="spend_limit_request_deny",
        help="Deny a pending increase request",
    )
    ad.add_argument(
        "--rate-limits",
        action="store_true",
        dest="rate_limits",
        help="Print the organization's configured rate limits (v1.23.0)",
    )
    ad.add_argument(
        "--rate-limits-model",
        metavar="MODEL",
        dest="rate_limits_model",
        default="",
        help="Filter --rate-limits to one model's group",
    )
    ad.add_argument(
        "--rate-limits-workspace",
        metavar="WORKSPACE_ID",
        dest="rate_limits_workspace",
        help="Print one workspace's rate limit overrides, with inherited org_limit",
    )
    ad.add_argument(
        "--claude-code-usage-report",
        action="store_true",
        dest="claude_code_usage_report",
        help="Print daily per-user Claude Code productivity metrics (v1.24.0)",
    )
    ad.add_argument(
        "--claude-code-usage-report-start",
        metavar="DATE",
        dest="claude_code_usage_report_start",
        default="",
        help="Date (YYYY-MM-DD) for --claude-code-usage-report, default: yesterday",
    )
    ad.add_argument(
        "--cmek-list",
        action="store_true",
        dest="cmek_list",
        help="List registered CMEK external keys (v1.25.0; unverified endpoint "
        "shape, see docs/37_upgrade_v1.25.0_audit_and_impl.md)",
    )
    ad.add_argument(
        "--cmek-workspace",
        metavar="WORKSPACE_ID",
        dest="cmek_workspace",
        default="",
        help="Filter --cmek-list to one workspace",
    )

    ce = p.add_argument_group("Claude Enterprise User Management (v1.38.0, beta)")
    ce.add_argument(
        "--members-list",
        action="store_true",
        dest="members_list",
        help="List organization members (Members/Invites take no beta header)",
    )
    ce.add_argument(
        "--members-email",
        metavar="EMAIL",
        dest="members_email",
        default="",
        help="Filter --members-list to one email address",
    )
    ce.add_argument("--member-get", metavar="USER_ID", dest="member_get", help="Show one organization member")
    ce.add_argument(
        "--member-role-set",
        metavar=("USER_ID", "ROLE"),
        nargs=2,
        dest="member_role_set",
        help='Set a member\'s role to "user" or "managed" ' "(administrative roles are Console-only)",
    )
    ce.add_argument(
        "--member-remove",
        metavar="USER_ID",
        dest="member_remove",
        help="Remove a member from the organization",
    )
    ce.add_argument(
        "--invite-create",
        metavar=("EMAIL", "ROLE"),
        nargs=2,
        dest="invite_create",
        help="Invite someone by email with role " '"user" or "managed"',
    )
    ce.add_argument(
        "--invite-rbac-groups",
        metavar="ID,ID",
        dest="invite_rbac_groups",
        default="",
        help="Comma-separated rbac_group_ids to assign on " "--invite-create acceptance",
    )
    ce.add_argument(
        "--invites-list",
        action="store_true",
        dest="invites_list",
        help="List pending/accepted/expired invites",
    )
    ce.add_argument(
        "--invite-withdraw", metavar="INVITE_ID", dest="invite_withdraw", help="Withdraw a pending invite"
    )
    ce.add_argument(
        "--groups-list",
        action="store_true",
        dest="groups_list",
        help="List Enterprise groups (requires ce-user-management beta)",
    )
    ce.add_argument("--group-create", metavar="NAME", dest="group_create", help="Create an Enterprise group")
    ce.add_argument(
        "--group-delete",
        metavar="GROUP_ID",
        dest="group_delete",
        help="Delete an Enterprise group (not SCIM-provisioned ones)",
    )
    ce.add_argument(
        "--group-members-list", metavar="GROUP_ID", dest="group_members_list", help="List a group's members"
    )
    ce.add_argument(
        "--group-member-add",
        metavar=("GROUP_ID", "USER_ID"),
        nargs=2,
        dest="group_member_add",
        help="Add an existing organization member to a group",
    )
    ce.add_argument(
        "--group-member-remove",
        metavar=("GROUP_ID", "USER_ID"),
        nargs=2,
        dest="group_member_remove",
        help="Remove a member from a group",
    )
    ce.add_argument(
        "--roles-list",
        action="store_true",
        dest="roles_list",
        help="List custom roles (read-only through the API)",
    )
    ce.add_argument(
        "--role-permissions",
        metavar="ROLE_ID",
        dest="role_permissions",
        help="List one custom role's permissions",
    )

    wf = p.add_argument_group("Workload Identity Federation (v1.23.0)")
    wf.add_argument(
        "--wif-exchange-token",
        action="store_true",
        dest="wif_exchange_token",
        help="Exchange the JWT found via env vars for a short-lived Claude " "API access token",
    )
    wf.add_argument(
        "--wif-status",
        action="store_true",
        dest="wif_status",
        help="Show which of the 5 WIF env vars are set/missing (never their values)",
    )
    wf.add_argument(
        "--org-admin-token",
        metavar="TOKEN",
        dest="org_admin_token",
        default="",
        help="org:admin OAuth bearer token, for --wif-create-*/--wif-list-* "
        "(distinct from --admin-api-key). Falls back to "
        "ANTHROPIC_ORG_ADMIN_TOKEN.",
    )
    wf.add_argument("--wif-create-service-account", metavar="NAME", dest="wif_create_service_account")
    wf.add_argument("--wif-list-service-accounts", action="store_true", dest="wif_list_service_accounts")
    wf.add_argument("--wif-create-issuer", metavar="NAME", dest="wif_create_issuer")
    wf.add_argument("--wif-issuer-url", metavar="URL", dest="wif_issuer_url", default="")
    wf.add_argument("--wif-list-issuers", action="store_true", dest="wif_list_issuers")
    wf.add_argument("--wif-create-rule", metavar="NAME", dest="wif_create_rule")
    wf.add_argument("--wif-rule-issuer", metavar="ID", dest="wif_rule_issuer", default="")
    wf.add_argument("--wif-rule-service-account", metavar="ID", dest="wif_rule_service_account", default="")
    wf.add_argument("--wif-rule-subject-prefix", metavar="PREFIX", dest="wif_rule_subject_prefix", default="")
    wf.add_argument("--wif-list-rules", action="store_true", dest="wif_list_rules")

    cp = p.add_argument_group("Compliance API (Activity Feed + chats/files/projects + directory)")
    cp.add_argument(
        "--compliance-api-key",
        metavar="KEY",
        dest="compliance_api_key",
        help="Compliance Access Key (sk-ant-api01-...) or Admin API key "
        "(sk-ant-admin01-..., Activity Feed only). Falls back to "
        "ANTHROPIC_COMPLIANCE_API_KEY, then --admin-api-key/"
        "ANTHROPIC_ADMIN_API_KEY, if not given.",
    )
    cp.add_argument(
        "--compliance-activities",
        action="store_true",
        dest="compliance_activities",
        help="Print recent Activity Feed entries",
    )
    cp.add_argument(
        "--compliance-activities-since",
        metavar="DATETIME",
        dest="compliance_activities_since",
        help="created_at.gte filter, RFC 3339 (e.g. 2026-06-01T00:00:00Z)",
    )
    cp.add_argument(
        "--compliance-activities-until",
        metavar="DATETIME",
        dest="compliance_activities_until",
        help="created_at.lte filter, RFC 3339",
    )
    cp.add_argument(
        "--compliance-activity-types",
        metavar="T1,T2",
        dest="compliance_activity_types",
        help="Comma-separated activity_types[] filter, e.g. claude_chat_created,claude_file_uploaded",
    )
    cp.add_argument(
        "--compliance-activities-limit",
        type=int,
        default=100,
        metavar="N",
        dest="compliance_activities_limit",
        help="Page size, 1-5000 (default: 100)",
    )
    cp.add_argument(
        "--compliance-activities-all",
        action="store_true",
        dest="compliance_activities_all",
        help="Page through the entire matching feed instead of just one page",
    )
    cp.add_argument(
        "--compliance-chats-list",
        action="store_true",
        dest="compliance_chats_list",
        help="List chats for --compliance-user-ids (Compliance Access Key required)",
    )
    cp.add_argument(
        "--compliance-user-ids",
        metavar="ID1,ID2",
        dest="compliance_user_ids",
        help="Comma-separated user IDs, required with --compliance-chats-list (max 10)",
    )
    cp.add_argument(
        "--compliance-chat-messages",
        metavar="CHAT_ID",
        dest="compliance_chat_messages",
        help="Print one chat's full message content",
    )
    cp.add_argument(
        "--compliance-chat-delete",
        metavar="CHAT_ID",
        dest="compliance_chat_delete",
        help="Hard-delete a chat — permanent, needs --compliance-yes to actually run",
    )
    cp.add_argument(
        "--compliance-file-download",
        metavar="FILE_ID",
        dest="compliance_file_download",
        help="Download a file's original bytes (use --compliance-output to set the path)",
    )
    cp.add_argument(
        "--compliance-file-delete",
        metavar="FILE_ID",
        dest="compliance_file_delete",
        help="Hard-delete a file — permanent, needs --compliance-yes to actually run",
    )
    cp.add_argument(
        "--compliance-projects-list",
        action="store_true",
        dest="compliance_projects_list",
        help="List projects",
    )
    cp.add_argument(
        "--compliance-project-info",
        metavar="PROJECT_ID",
        dest="compliance_project_info",
        help="Show one project's details",
    )
    cp.add_argument(
        "--compliance-project-attachments",
        metavar="PROJECT_ID",
        dest="compliance_project_attachments",
        help="List a project's attachments (files and documents)",
    )
    cp.add_argument(
        "--compliance-project-delete",
        metavar="PROJECT_ID",
        dest="compliance_project_delete",
        help="Hard-delete a project — permanent, needs --compliance-yes; "
        "fails clearly if chats are still attached",
    )
    cp.add_argument(
        "--compliance-orgs-list",
        action="store_true",
        dest="compliance_orgs_list",
        help="List every linked organization",
    )
    cp.add_argument(
        "--compliance-org-users",
        metavar="ORG_UUID",
        dest="compliance_org_users",
        help="List an organization's users",
    )
    cp.add_argument(
        "--compliance-org-roles",
        metavar="ORG_UUID",
        dest="compliance_org_roles",
        help="List an organization's RBAC roles",
    )
    cp.add_argument(
        "--compliance-org-settings",
        metavar="ORG_UUID",
        dest="compliance_org_settings",
        help="Show the effective settings (retention, redaction, IP allowlist, ...) in force for an organization",
    )
    cp.add_argument(
        "--compliance-groups-list",
        action="store_true",
        dest="compliance_groups_list",
        help="List RBAC/SCIM groups",
    )
    cp.add_argument(
        "--compliance-group-members",
        metavar="GROUP_ID",
        dest="compliance_group_members",
        help="List a group's members",
    )
    cp.add_argument(
        "--compliance-yes",
        action="store_true",
        dest="compliance_yes",
        help="Actually execute a --compliance-*-delete (default: dry-run preview only)",
    )
    cp.add_argument(
        "--compliance-output",
        metavar="PATH",
        dest="compliance_output",
        help="Output path for --compliance-file-download (default: the original filename)",
    )
    cp.add_argument(
        "--compliance-local-sessions-list",
        action="store_true",
        dest="compliance_local_sessions_list",
        help="List Cowork (Claude Desktop) / Claude Code sessions captured on users' "
        "machines (Enterprise beta; read:compliance_user_data)",
    )
    cp.add_argument(
        "--compliance-local-session-get",
        metavar="SESSION_ID",
        dest="compliance_local_session_get",
        help="Show one local session's metadata (id prefix clls_)",
    )
    cp.add_argument(
        "--compliance-local-session-messages",
        metavar="SESSION_ID",
        dest="compliance_local_session_messages",
        help="Print one local session's reconstructed transcript",
    )
    cp.add_argument(
        "--compliance-remote-sessions-list",
        action="store_true",
        dest="compliance_remote_sessions_list",
        help="List Cowork sessions started on claude.ai web/mobile, running in "
        "Anthropic-managed cloud environments (Enterprise beta)",
    )
    cp.add_argument(
        "--compliance-remote-session-messages",
        metavar="SESSION_ID",
        dest="compliance_remote_session_messages",
        help="Print one remote session's transcript (id prefix cse_)",
    )
    cp.add_argument(
        "--compliance-sessions-since",
        metavar="DATETIME",
        dest="compliance_sessions_since",
        help="created_at.gte filter (RFC 3339) for --compliance-*-sessions-list",
    )
    cp.add_argument(
        "--compliance-sessions-until",
        metavar="DATETIME",
        dest="compliance_sessions_until",
        help="created_at.lt filter (RFC 3339) for --compliance-*-sessions-list",
    )
    cp.add_argument(
        "--compliance-sessions-limit",
        type=int,
        default=100,
        metavar="N",
        dest="compliance_sessions_limit",
        help="Page size for --compliance-*-sessions-list, 1-500 (default 100)",
    )

    sk = p.add_argument_group("Agent Skills API (platform, skill_id-based)")
    sk.add_argument(
        "--skills-list",
        action="store_true",
        dest="skills_list",
        help="List Anthropic-provided pre-built Skills (pptx/xlsx/docx/pdf)",
    )
    sk.add_argument(
        "--skills-info",
        metavar="ID",
        dest="skills_info",
        help="Show details for one skill_id (info-only, no API call)",
    )

    cu = p.add_argument_group("Computer Use")
    cu.add_argument("--computer-use", metavar="TASK", dest="computer_use")

    ag = p.add_argument_group("Agent SDK")
    ag.add_argument("--agent-session", metavar="ID", dest="agent_session")
    ag.add_argument("--agent-orchestrate", action="store_true", dest="agent_orchestrate")
    ag.add_argument(
        "--agent-managed-run",
        metavar="TASK",
        dest="agent_managed_run",
        help="Run TASK on the real hosted Claude Managed Agents API "
        "(creates a throwaway agent/environment/session)",
    )
    ag.add_argument(
        "--agent-memory-store",
        metavar="NAME",
        dest="agent_memory_store",
        default="",
        help="With --agent-managed-run: create/reuse a persistent "
        "Managed Agents memory store NAME and mount it into the "
        "session (agent-memory-2026-07-22 beta, opt-in). Without "
        "--agent-managed-run: use with --agent-memory-store-create "
        "to create a standalone store.",
    )
    ag.add_argument(
        "--agent-memory-store-create",
        action="store_true",
        dest="agent_memory_store_create",
        help="Create a Managed Agents memory store (named via "
        "--agent-memory-store) without also running a task",
    )
    ag.add_argument(
        "--agent-memory-list",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_list",
        help="List the memory entries inside a memory store (v1.24.0)",
    )
    ag.add_argument(
        "--agent-memory-path-prefix",
        metavar="PREFIX",
        dest="agent_memory_path_prefix",
        default="",
        help="With --agent-memory-list: filter to entries under this path " "prefix (must end with '/')",
    )
    ag.add_argument(
        "--agent-memory-depth",
        metavar="N",
        dest="agent_memory_depth",
        default="",
        help="With --agent-memory-list: 0, 1, or omitted",
    )
    ag.add_argument(
        "--agent-memory-stores-list",
        action="store_true",
        dest="agent_memory_stores_list",
        help="List memory stores in the workspace (v1.27.0)",
    )
    ag.add_argument(
        "--agent-memory-stores-include-archived",
        action="store_true",
        dest="agent_memory_stores_include_archived",
        help="With --agent-memory-stores-list: include archived stores",
    )
    ag.add_argument(
        "--agent-memory-store-archive",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_store_archive",
        help="Archive a memory store (v1.27.0) -- one-way, no unarchive",
    )
    ag.add_argument(
        "--agent-memory-store-delete",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_store_delete",
        help="Permanently delete a memory store and everything in it "
        "(v1.27.0) -- dry-run unless --agent-memory-store-delete-yes",
    )
    ag.add_argument(
        "--agent-memory-store-delete-yes",
        action="store_true",
        dest="agent_memory_store_delete_yes",
        help="Confirm --agent-memory-store-delete instead of dry-running it",
    )
    ag.add_argument(
        "--agent-memory-get",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_get",
        help="Retrieve a memory's full content (v1.27.0); pair with " "--agent-memory-id",
    )
    ag.add_argument(
        "--agent-memory-create",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_create",
        help="Create a memory (v1.27.0); pair with --agent-memory-path " "and --agent-memory-content",
    )
    ag.add_argument(
        "--agent-memory-update",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_update",
        help="Update a memory's content/path (v1.27.0); pair with "
        "--agent-memory-id and --agent-memory-content and/or "
        "--agent-memory-path",
    )
    ag.add_argument(
        "--agent-memory-delete",
        metavar="MEMORY_STORE_ID",
        dest="agent_memory_delete",
        help="Delete a memory (v1.27.0); pair with --agent-memory-id -- "
        "dry-run unless --agent-memory-delete-yes",
    )
    ag.add_argument(
        "--agent-memory-delete-yes",
        action="store_true",
        dest="agent_memory_delete_yes",
        help="Confirm --agent-memory-delete instead of dry-running it",
    )
    ag.add_argument(
        "--agent-memory-id",
        metavar="MEMORY_ID",
        dest="agent_memory_id",
        default="",
        help="Memory ID for --agent-memory-get/update/delete",
    )
    ag.add_argument(
        "--agent-memory-path",
        metavar="PATH",
        dest="agent_memory_path",
        default="",
        help="Memory path for --agent-memory-create/update",
    )
    ag.add_argument(
        "--agent-memory-content",
        metavar="TEXT",
        dest="agent_memory_content",
        default="",
        help="Memory content for --agent-memory-create/update",
    )
    ag.add_argument("--agent-list-sessions", action="store_true", dest="agent_list_sessions")
    ag.add_argument("--list-tool-presets", action="store_true", dest="list_tool_presets")

    ag.add_argument(
        "--agent-dream",
        metavar="STORE_ID",
        dest="agent_dream",
        help="Run a Dreaming pass (research preview, dreaming-2026-04-21 "
        "beta) over memory store STORE_ID, producing a new curated "
        "output store. Async — returns a pending dream id.",
    )
    ag.add_argument(
        "--agent-dream-sessions",
        metavar="IDS",
        dest="agent_dream_sessions",
        default="",
        help="Comma-separated session IDs to fold into " "--agent-dream, alongside the memory store",
    )
    ag.add_argument(
        "--agent-dream-instructions",
        metavar="TEXT",
        dest="agent_dream_instructions",
        default="",
        help="Optional steering text for --agent-dream",
    )
    ag.add_argument(
        "--agent-dream-list",
        action="store_true",
        dest="agent_dream_list",
        help="List dreams in the workspace (newest first)",
    )
    ag.add_argument(
        "--agent-dream-list-include-archived",
        action="store_true",
        dest="agent_dream_list_include_archived",
        help="With --agent-dream-list, also include archived dreams",
    )
    ag.add_argument(
        "--agent-dream-list-limit",
        type=int,
        default=20,
        dest="agent_dream_list_limit",
        help="With --agent-dream-list, max results per page (default 20, max 100)",
    )
    ag.add_argument(
        "--agent-dream-list-page",
        metavar="CURSOR",
        dest="agent_dream_list_page",
        default="",
        help="With --agent-dream-list, page cursor from a previous call",
    )
    ag.add_argument(
        "--agent-dream-get",
        metavar="DREAM_ID",
        dest="agent_dream_get",
        help="Retrieve one dream's status, usage, session_id, and output_store_id",
    )
    ag.add_argument(
        "--agent-dream-cancel",
        metavar="DREAM_ID",
        dest="agent_dream_cancel",
        help="Cancel a pending/running dream immediately",
    )
    ag.add_argument(
        "--agent-dream-archive",
        metavar="DREAM_ID",
        dest="agent_dream_archive",
        help="Archive a completed/failed/canceled dream (excludes it from "
        "--agent-dream-list without deleting it)",
    )

    ag.add_argument(
        "--agent-outcome",
        metavar="DESC",
        dest="agent_outcome",
        default="",
        help="With --agent-managed-run: define an outcome (rubric-graded "
        "self-correction loop, public beta) instead of a plain task. "
        "Requires --agent-outcome-rubric.",
    )
    ag.add_argument(
        "--agent-outcome-rubric",
        metavar="FILE",
        dest="agent_outcome_rubric",
        default="",
        help="Markdown rubric file for --agent-outcome",
    )
    ag.add_argument(
        "--agent-outcome-max-iter",
        type=int,
        default=3,
        dest="agent_outcome_max_iter",
        help="max_iterations for --agent-outcome (default 3, max 20)",
    )

    ag.add_argument(
        "--agent-webhook-register",
        metavar="URL",
        dest="agent_webhook_register",
        help="Register a webhook URL for Managed Agents session/outcome/" "dream events (public beta)",
    )
    ag.add_argument(
        "--agent-webhook-events",
        metavar="LIST",
        dest="agent_webhook_events",
        default="",
        help="Comma-separated event types for " "--agent-webhook-register (default: all supported types)",
    )

    ag.add_argument(
        "--agent-vault-create",
        metavar="NAME",
        dest="agent_vault_create",
        help="Create a vault (v1.21.0, public beta) for third-party "
        "credentials (MCP OAuth, static bearer, or env-var secrets)",
    )
    ag.add_argument(
        "--agent-vault-external-user",
        metavar="ID",
        dest="agent_vault_external_user",
        default="",
        help="Optional external_user_id metadata for --agent-vault-create",
    )
    ag.add_argument(
        "--agent-vault-add-credential",
        metavar="VAULT_ID",
        dest="agent_vault_add_credential",
        help="Add a credential to VAULT_ID",
    )
    ag.add_argument(
        "--agent-vault-cred-type",
        metavar="TYPE",
        dest="agent_vault_cred_type",
        default="",
        choices=["mcp_oauth", "static_bearer", "environment_variable"],
        help="Credential type for --agent-vault-add-credential",
    )
    ag.add_argument(
        "--agent-vault-mcp-url",
        metavar="URL",
        dest="agent_vault_mcp_url",
        default="",
        help="MCP server URL (mcp_oauth/static_bearer credentials)",
    )
    ag.add_argument(
        "--agent-vault-secret-name",
        metavar="NAME",
        dest="agent_vault_secret_name",
        default="",
        help="Environment variable name (environment_variable credentials)",
    )
    ag.add_argument(
        "--agent-vault-secret",
        metavar="VALUE",
        dest="agent_vault_secret",
        default="",
        help="The credential's secret value (write-only, never logged)",
    )
    ag.add_argument(
        "--agent-vault-allowed-domains",
        metavar="LIST",
        dest="agent_vault_allowed_domains",
        default="",
        help="Comma-separated allow-listed domains (environment_variable credentials)",
    )
    ag.add_argument(
        "--agent-vault-injection-location",
        metavar="LOCATION",
        dest="agent_vault_injection_location",
        default="",
        choices=["", "headers", "body", "both"],
        help="Where the resolved secret is substituted at egress "
        "(environment_variable credentials only, v1.22.0)",
    )
    ag.add_argument(
        "--agent-vault-list",
        action="store_true",
        dest="agent_vault_list",
        help="List vaults in the workspace",
    )
    ag.add_argument(
        "--agent-vault",
        metavar="VAULT_ID",
        dest="agent_vault",
        default="",
        help="With --agent-managed-run: mount a vault's credentials into the session",
    )

    ag.add_argument(
        "--agent-override-json",
        metavar="FILE",
        dest="agent_override_json",
        default="",
        help="With --agent-managed-run: JSON file containing an "
        "agent_with_overrides dict (any of version, model, system, tools, "
        "mcp_servers, skills) for a session-level override (v1.22.0, public beta)",
    )
    ag.add_argument(
        "--agent-override-model",
        metavar="MODEL",
        dest="agent_override_model",
        default="",
        help="With --agent-managed-run: override just the model "
        "for this session (shortcut for --agent-override-json)",
    )
    ag.add_argument(
        "--agent-override-system",
        metavar="TEXT",
        dest="agent_override_system",
        default="",
        help="With --agent-managed-run: override just the system "
        "prompt for this session (shortcut for --agent-override-json)",
    )
    ag.add_argument(
        "--agent-stream-deltas",
        action="store_true",
        dest="agent_stream_deltas",
        help="With --agent-managed-run: live-print text as it's generated "
        "(v1.22.0, public beta), instead of waiting for each full turn",
    )

    ag.add_argument(
        "--agent-schedule-create",
        metavar="AGENT_ID",
        dest="agent_schedule_create",
        help="Attach a cron schedule (v1.21.0, public beta) to AGENT_ID",
    )
    ag.add_argument(
        "--agent-schedule-env",
        metavar="ENV_ID",
        dest="agent_schedule_env",
        default="",
        help="Environment id (with --agent-schedule-create)",
    )
    ag.add_argument(
        "--agent-schedule-cron",
        metavar="EXPR",
        dest="agent_schedule_cron",
        default="",
        help="Cron expression (with --agent-schedule-create)",
    )
    ag.add_argument(
        "--agent-schedule-tz",
        metavar="TZ",
        dest="agent_schedule_tz",
        default="UTC",
        help="IANA timezone (with --agent-schedule-create, default UTC)",
    )
    ag.add_argument(
        "--agent-schedule-task",
        metavar="TEXT",
        dest="agent_schedule_task",
        default="",
        help="Initial task text for the scheduled session",
    )
    ag.add_argument(
        "--agent-schedule-list",
        action="store_true",
        dest="agent_schedule_list",
        help="List scheduled deployments",
    )
    ag.add_argument(
        "--agent-schedule-cancel",
        metavar="DEPLOYMENT_ID",
        dest="agent_schedule_cancel",
        help="Archive a scheduled deployment",
    )

    ag.add_argument(
        "--agent-review-multiagent",
        metavar="PATH",
        dest="agent_review_multiagent",
        help="Native Multiagent orchestration (v1.21.0): parallel specialist "
        "code review of PATH over one shared sandbox",
    )
    ag.add_argument(
        "--agent-review-specialists",
        metavar="LIST",
        dest="agent_review_specialists",
        default="security,style,test-coverage",
        help="Comma-separated specialists for --agent-review-multiagent " "(security, style, test-coverage)",
    )

    ag.add_argument(
        "--agent-outcome-rubric-upload",
        metavar="FILE",
        dest="agent_outcome_rubric_upload",
        help="Upload a rubric once via the Files API and print its file_id (v1.21.0)",
    )
    ag.add_argument(
        "--agent-outcome-rubric-file",
        metavar="FILE_ID",
        dest="agent_outcome_rubric_file",
        default="",
        help="Reuse an uploaded rubric's file_id with --agent-outcome, "
        "instead of --agent-outcome-rubric FILE",
    )

    ag.add_argument(
        "--agent-env-self-hosted",
        metavar="NAME",
        dest="agent_env_self_hosted",
        help="Create a self-hosted sandbox environment NAME (public beta, "
        "v1.26.0) — tool execution runs on infrastructure you control "
        "(your own worker, or a managed provider like Cloudflare/Daytona/"
        "Modal/Vercel) instead of Anthropic's cloud sandbox. Prints the "
        "remaining manual steps (environment key generation is Console-"
        "only; running a worker is a separate long-lived process).",
    )
    ag.add_argument(
        "--agent-env-work-stats",
        metavar="ENVIRONMENT_ID",
        dest="agent_env_work_stats",
        help="Read a self-hosted environment's work queue state: how many "
        "sessions are waiting (depth), being processed (pending), and "
        "whether a worker is actually connected (workers_polling)",
    )

    ag.add_argument(
        "--agent-create",
        metavar="NAME",
        dest="agent_create",
        help="Create a persisted, versioned Managed Agent NAME (v1.38.0, "
        "public beta) -- pair with --model and --agent-system",
    )
    ag.add_argument(
        "--agent-system",
        metavar="TEXT",
        dest="agent_system",
        default="You are a helpful coding assistant.",
        help="System prompt for --agent-create/--agent-update",
    )
    ag.add_argument(
        "--agent-effort",
        metavar="LEVEL",
        dest="agent_effort",
        default="",
        help="Effort level for --agent-create/--agent-update " "(v1.38.0, public beta)",
    )
    ag.add_argument(
        "--agent-get",
        metavar="AGENT_ID",
        dest="agent_get",
        help="Retrieve a Managed Agent's stored config (v1.38.0, public beta)",
    )
    ag.add_argument(
        "--agent-get-version",
        type=int,
        metavar="N",
        dest="agent_get_version",
        help="With --agent-get: read a specific prior version instead of current",
    )
    ag.add_argument(
        "--agent-list",
        action="store_true",
        dest="agent_list",
        help="List Managed Agents in the workspace (v1.38.0, public beta)",
    )
    ag.add_argument(
        "--agent-list-limit",
        type=int,
        default=50,
        dest="agent_list_limit",
        help="With --agent-list: max results (default 50)",
    )
    ag.add_argument(
        "--agent-update",
        metavar="AGENT_ID",
        dest="agent_update",
        help="Update a persisted agent, creating a new version (v1.38.0, "
        "public beta) -- pair with --model/--agent-system/--agent-effort",
    )
    ag.add_argument(
        "--agent-inference-geo",
        metavar="GEO",
        dest="agent_inference_geo",
        default="",
        choices=["", "us", "global"],
        help="With --agent-create/--agent-update: pin the Managed Agent's "
        "model.inference_geo (v1.39.0, public beta). 'us' keeps "
        "inference US-only at a 1.1x price multiplier; 'global' runs "
        "wherever there's capacity at the standard rate. Distinct from "
        "the top-level --inference-geo flag, which is the Messages API "
        "field (different request shape).",
    )

    ag.add_argument(
        "--agent-session-budget-usd",
        type=float,
        metavar="DOLLARS",
        dest="agent_session_budget_usd",
        help="With --agent-managed-run: set a hard USD spend cap on the "
        "throwaway session (v1.39.0, public beta). The session pauses "
        "with stop_reason=budget_reached instead of terminating once "
        "reached -- see --agent-session-budget-set/--agent-session-get "
        "to change or inspect it afterward. Not the same as "
        "--task-budget (an advisory token budget for the Advisor "
        "Tool's agentic loop) or --thinking-budget.",
    )
    ag.add_argument(
        "--agent-session-get",
        metavar="SESSION_ID",
        dest="agent_session_get",
        help="Inspect a Managed Agents session's status, stop_reason, "
        "budget, and consumed spend (v1.39.0, public beta)",
    )
    ag.add_argument(
        "--agent-session-budget-set",
        metavar="SESSION_ID",
        dest="agent_session_budget_set",
        help="Replace SESSION_ID's spend budget -- pair with "
        "--agent-session-budget-usd for the new cap. Resumes the "
        "session automatically if it was paused at budget_reached.",
    )
    ag.add_argument(
        "--agent-session-budget-remove",
        metavar="SESSION_ID",
        dest="agent_session_budget_remove",
        help="Remove SESSION_ID's spend budget entirely (one-way -- the "
        "session can never be given a new budget afterward). Resumes "
        "the session automatically if it was paused at budget_reached.",
    )

    cw = p.add_argument_group("Cowork")
    cw.add_argument("--cowork", metavar="TYPE")
    cw.add_argument("--cowork-prompt", metavar="TEXT", dest="cowork_prompt")
    cw.add_argument("--cowork-files", nargs="+", dest="cowork_files")
    cw.add_argument("--cowork-depth", type=int, default=3, dest="cowork_depth")
    cw.add_argument(
        "--cowork-format",
        default="markdown",
        dest="cowork_format",
        choices=["markdown", "json", "outline", "bullets"],
    )
    cw.add_argument("--cowork-list", action="store_true", dest="cowork_list")

    xl = p.add_argument_group("Excel / Data Chat")
    xl.add_argument(
        "--excel",
        nargs="?",
        const="",
        metavar="FILE",
        dest="excel",
        help="Start a conversational spreadsheet session — build financial "
        "models, clean messy data, and create tables and charts, applied "
        "directly to a live .xlsx workbook. Optionally load an existing "
        ".xlsx/.csv as the starting data.",
    )
    xl.add_argument(
        "--excel-output",
        metavar="FILE",
        dest="excel_output",
        help="Workbook path to write after every turn " "(default: <input>.xlsx or excel_session.xlsx)",
    )
    xl.add_argument(
        "--excel-sheet",
        metavar="NAME",
        dest="excel_sheet",
        help="Which sheet to load from a multi-sheet --excel input file",
    )
    xl.add_argument(
        "--excel-native",
        action="store_true",
        dest="excel_native",
        help="Route --excel through Anthropic's own xlsx Skill (server-side, "
        "code-execution container) instead of the built-in pandas/openpyxl "
        "path. Requires Skills access on the account; no local pandas/"
        "openpyxl dependency needed for this mode. Falls back to the "
        "regular --excel path's behavior if omitted.",
    )

    pp = p.add_argument_group("PowerPoint / Slide Chat")
    pp.add_argument(
        "--pptx",
        nargs="?",
        const="",
        metavar="FILE",
        dest="pptx",
        help="Start a conversational slide-deck session — add/edit slides, "
        "tables, and charts, applied directly to a live .pptx deck. "
        "Optionally load an existing .pptx as the starting deck.",
    )
    pp.add_argument(
        "--pptx-output",
        metavar="FILE",
        dest="pptx_output",
        help="Deck path to write after every turn " "(default: <input>.pptx or pptx_session.pptx)",
    )
    pp.add_argument(
        "--pptx-native",
        action="store_true",
        dest="pptx_native",
        help="Route --pptx through Anthropic's own pptx Skill (server-side, "
        "code-execution container) instead of the built-in python-pptx "
        "path. Requires Skills access on the account; no local python-pptx "
        "dependency needed for this mode. Falls back to the regular --pptx "
        "path's behavior if omitted.",
    )

    br = p.add_argument_group("Browse (Claude in Chrome analog)")
    br.add_argument(
        "--browse",
        metavar="URL",
        dest="browse",
        help="Start a headless browsing-agent session at URL. Not the "
        "Claude in Chrome extension — a fetch/decide/navigate loop for "
        "CLI and CI use. Requires --browse-task.",
    )
    br.add_argument(
        "--browse-task", metavar="TEXT", dest="browse_task", help="What to find or do, required with --browse"
    )
    br.add_argument(
        "--browse-max-steps",
        type=int,
        default=6,
        dest="browse_max_steps",
        help="Max fetch/decide iterations (default: 6)",
    )
    br.add_argument(
        "--browse-allow-domain",
        action="append",
        default=None,
        dest="browse_allow_domains",
        metavar="DOMAIN",
        help="Restrict navigation to this domain (repeatable)",
    )

    # Claude Code
    cc = p.add_argument_group("Claude Code")
    cc.add_argument("--code-agent", action="store_true", dest="code_agent")
    cc.add_argument("--code-agent-cwd", default=".", dest="code_agent_cwd")
    cc.add_argument("--code-agent-tools", default="all", dest="code_agent_tools")
    cc.add_argument("--code-agent-permission", default="askPermission", dest="code_agent_permission")
    cc.add_argument("--code-agent-session", metavar="ID", dest="code_agent_session")
    cc.add_argument("--code-agent-resume", metavar="ID", dest="code_agent_resume")
    cc.add_argument("--code-agent-system", metavar="TEXT", dest="code_agent_system")
    cc.add_argument("--code-agent-mcp", nargs="+", metavar="URL", dest="code_agent_mcp")
    cc.add_argument(
        "--code-agent-mcp-tunnel",
        type=int,
        metavar="PORT",
        dest="code_agent_mcp_tunnel",
        help="Open an MCP tunnel to a local MCP server on PORT and print "
        "its public URL (research preview)",
    )
    cc.add_argument("--code-agent-list-sessions", action="store_true", dest="code_agent_list_sessions")
    cc.add_argument("--code-agent-list-tools", action="store_true", dest="code_agent_list_tools")
    cc.add_argument("--code-agent-hooks", metavar="FILE", dest="code_agent_hooks")
    cc.add_argument("--code-agent-checkpoint", action="store_true", dest="code_agent_checkpoint")
    cc.add_argument("--code-agent-subagent", metavar="PROMPT", dest="code_agent_subagent")
    cc.add_argument("--code-agent-todo", metavar="PROMPT", dest="code_agent_todo")
    cc.add_argument("--code-agent-slash", metavar="CMD", dest="code_agent_slash")
    cc.add_argument("--code-agent-cost", action="store_true", dest="code_agent_cost")
    cc.add_argument(
        "--code-agent-output", default="stream", dest="code_agent_output", choices=["stream", "json", "text"]
    )
    cc.add_argument(
        "--code-agent-headless",
        action="store_true",
        dest="code_agent_headless",
        help="Non-interactive print mode: run one prompt, print plain text, exit (like `claude -p`)",
    )
    cc.add_argument(
        "--code-agent-output-style",
        metavar="NAME",
        dest="code_agent_output_style",
        help="Apply a named output style (default, explanatory, concise, learning, or custom)",
    )
    cc.add_argument("--list-output-styles", action="store_true", dest="list_output_styles")
    cc.add_argument(
        "--code-agent-sandbox",
        action="store_true",
        dest="code_agent_sandbox",
        help="Run Bash tool calls inside a filesystem+network sandbox",
    )
    cc.add_argument(
        "--code-agent-sandbox-allow-net",
        action="store_true",
        dest="code_agent_sandbox_allow_net",
        help="Allow network access inside the sandbox (default: blocked)",
    )
    cc.add_argument(
        "--code-agent-sandbox-roots",
        nargs="+",
        metavar="PATH",
        dest="code_agent_sandbox_roots",
        help="Extra filesystem roots the sandbox may read/write besides cwd",
    )
    cc.add_argument(
        "--agent-context-editing",
        action="store_true",
        dest="agent_context_editing",
        help="Opt-in context editing (clear_tool_uses) for this agent loop, "
        "complementary to Compaction — clearing drops stale tool results, "
        "Compaction summarizes the whole conversation. Useful for long "
        "--code-agent sessions.",
    )

    pl = p.add_argument_group("Plugins & Marketplaces")
    pl.add_argument("--plugin-marketplace-add", metavar="PATH_OR_URL", dest="plugin_marketplace_add")
    pl.add_argument("--plugin-marketplace-name", metavar="NAME", dest="plugin_marketplace_name")
    pl.add_argument("--plugin-marketplace-list", action="store_true", dest="plugin_marketplace_list")
    pl.add_argument("--plugin-marketplace-remove", metavar="NAME", dest="plugin_marketplace_remove")
    pl.add_argument("--plugin-install", metavar="NAME[@MARKETPLACE]", dest="plugin_install")
    pl.add_argument(
        "--plugin-dir",
        metavar="PATH",
        dest="plugin_dir",
        help="Install a plugin directly from a local directory or .zip",
    )
    pl.add_argument("--plugin-uninstall", metavar="NAME", dest="plugin_uninstall")
    pl.add_argument("--plugin-list", action="store_true", dest="plugin_list")
    pl.add_argument("--plugin-info", metavar="NAME", dest="plugin_info")
    pl.add_argument("--plugin-enable", metavar="NAME", dest="plugin_enable")
    pl.add_argument("--plugin-disable", metavar="NAME", dest="plugin_disable")
    pl.add_argument("--plugin-validate", metavar="PATH", dest="plugin_validate")

    mem = p.add_argument_group("Memory")
    mem.add_argument("--memory-add", metavar="TEXT", dest="memory_add")
    mem.add_argument(
        "--memory-type", default="fact", choices=["fact", "preference", "event", "task"], dest="memory_type"
    )
    mem.add_argument("--memory-tags", default="", dest="memory_tags")
    mem.add_argument("--memory-importance", type=int, default=5, dest="memory_importance")
    mem.add_argument("--memory-recall", metavar="QUERY", dest="memory_recall")
    mem.add_argument("--memory-forget", metavar="ID", dest="memory_forget")
    mem.add_argument("--memory-stats", action="store_true", dest="memory_stats")
    mem.add_argument("--memory-retention", action="store_true", dest="memory_retention")
    mem.add_argument("--memory-ns", default="default", dest="memory_ns")

    ses = p.add_argument_group("Sessions & Checkpoints")
    ses.add_argument("--sessions-list", action="store_true", dest="sessions_list")
    ses.add_argument("--session-show", metavar="ID", dest="session_show")
    ses.add_argument("--checkpoint-list", metavar="SESSION_ID", dest="checkpoint_list")
    ses.add_argument("--away-summary", metavar="SESSION_ID", dest="away_summary")

    lv = p.add_argument_group("zcoder-live")
    lv.add_argument("--live", action="store_true", dest="live")

    rs = p.add_argument_group("Deep Research")
    rs.add_argument("--research", metavar="TOPIC", dest="research")
    rs.add_argument("--research-depth", type=int, default=4, dest="research_depth")
    rs.add_argument("--research-urls", nargs="*", default=None, dest="research_urls")

    rag = p.add_argument_group("RAG")
    rag.add_argument("--rag-index", metavar="NAME", dest="rag_index")
    rag.add_argument("--rag-folder", metavar="PATH", dest="rag_folder")
    rag.add_argument("--rag-query", metavar="TEXT", dest="rag_query")
    rag.add_argument("--rag-index-name", default="default", dest="rag_index_name")
    rag.add_argument("--rag-list", action="store_true", dest="rag_list")
    rag.add_argument("--rag-k", type=int, default=5, dest="rag_k")

    ev = p.add_argument_group("Evaluation")
    ev.add_argument("--eval-run", metavar="SUITE_JSON", dest="eval_run")
    ev.add_argument("--eval-compare", nargs=2, metavar=("MODEL_A", "MODEL_B"), dest="eval_compare")
    ev.add_argument("--eval-list", action="store_true", dest="eval_list")
    ev.add_argument("--eval-scaffold", metavar="PATH", dest="eval_scaffold")
    ev.add_argument("--eval-threshold", type=float, default=0.7, dest="eval_threshold")

    gt = p.add_argument_group("Git Integration")
    gt.add_argument("--git-commit", action="store_true", dest="git_commit")
    gt.add_argument(
        "--git-commit-style",
        default="conventional",
        choices=["conventional", "imperative", "detailed"],
        dest="git_commit_style",
    )
    gt.add_argument("--git-commit-write", action="store_true", dest="git_commit_write")
    gt.add_argument("--git-pr", nargs=2, metavar=("BASE", "HEAD"), dest="git_pr")
    gt.add_argument("--git-changelog", metavar="SINCE_TAG", dest="git_changelog")
    gt.add_argument("--git-review", action="store_true", dest="git_review")
    gt.add_argument(
        "--git-blame-explain", nargs=3, metavar=("FILE", "START", "END"), dest="git_blame_explain"
    )

    gh = p.add_argument_group("GitHub Integration")
    gh.add_argument(
        "--gh-review-pr",
        metavar="REPO/NUMBER",
        dest="gh_review_pr",
        help="AI review of a pull request diff, e.g. anthropics/claude-code/42",
    )
    gh.add_argument(
        "--gh-triage-issues",
        metavar="REPO",
        dest="gh_triage_issues",
        help="Triage open issues and suggest labels/owners",
    )
    gh.add_argument(
        "--gh-summarise-commits",
        metavar="REPO",
        dest="gh_summarise_commits",
        help="Summarise recent commit history",
    )
    gh.add_argument(
        "--gh-pr-description",
        metavar="REPO/NUMBER",
        dest="gh_pr_description",
        help="Generate a PR description from a pull request's diff",
    )
    gh.add_argument(
        "--gh-token",
        default="",
        dest="gh_token",
        help="GitHub personal access token (or GITHUB_TOKEN env var)",
    )
    gh.add_argument(
        "--gh-max-items",
        type=int,
        default=20,
        dest="gh_max_items",
        help="Max issues/commits to process for --gh-triage-issues / " "--gh-summarise-commits (default: 20)",
    )

    ro = p.add_argument_group("Multi-Agent Router")
    ro.add_argument(
        "--route", metavar="PROMPT", dest="route", help="Auto-route PROMPT to the best specialist agent"
    )
    ro.add_argument(
        "--route-explain",
        action="store_true",
        dest="route_explain",
        help="With --route: print which agent was chosen and why",
    )
    ro.add_argument(
        "--route-parallel",
        action="store_true",
        dest="route_parallel",
        help="With --route: fan out to ALL agents and synthesise the best answer",
    )
    ro.add_argument(
        "--route-list", action="store_true", dest="route_list", help="List all agents in the routing table"
    )

    co = p.add_argument_group("Cost Optimizer")
    co.add_argument("--optimized", metavar="PROMPT", dest="optimized")
    co.add_argument("--force-model", default=None, dest="force_model")
    co.add_argument("--cost-summary", action="store_true", dest="cost_summary")
    co.add_argument("--cost-reset", action="store_true", dest="cost_reset")

    po = p.add_argument_group("Prompt Optimizer")
    po.add_argument(
        "--optimize",
        metavar="PROMPT",
        dest="prompt_optimize",
        help="Rewrite a prompt to be clearer and more effective",
    )
    po.add_argument(
        "--score-prompt",
        metavar="PROMPT",
        dest="score_prompt",
        help="Score a prompt 0-100 for clarity, specificity, and completeness",
    )
    po.add_argument(
        "--ab-test",
        action="store_true",
        dest="ab_test",
        help="With --prompt and --ab-prompt-b: A/B test two prompt variants " "against --ab-task",
    )
    po.add_argument(
        "--ab-prompt-b",
        metavar="PROMPT_B",
        default="",
        dest="ab_prompt_b",
        help="Second prompt variant for --ab-test (first variant is --prompt)",
    )
    po.add_argument(
        "--ab-task",
        metavar="TASK",
        default="",
        dest="ab_task",
        help="Task description to judge both --ab-test variants against",
    )
    po.add_argument(
        "--prompt-lib-add",
        action="store_true",
        dest="prompt_lib_add",
        help="Save --prompt to the library under --tag",
    )
    po.add_argument(
        "--prompt-lib-list", action="store_true", dest="prompt_lib_list", help="List saved prompts"
    )
    po.add_argument(
        "--prompt-lib-get", metavar="TAG", dest="prompt_lib_get", help="Print a saved prompt by tag"
    )

    ob = p.add_argument_group("Observability")
    ob.add_argument("--obs-latency", action="store_true", dest="obs_latency")
    ob.add_argument("--obs-errors", action="store_true", dest="obs_errors")
    ob.add_argument("--obs-tail", type=int, nargs="?", const=20, default=None, dest="obs_tail")
    ob.add_argument("--obs-clear", action="store_true", dest="obs_clear")
    ob.add_argument("--obs-hours", type=int, default=24, dest="obs_hours")

    mt = p.add_argument_group("Metrics (local usage log)")
    mt.add_argument(
        "--metrics-show",
        action="store_true",
        dest="metrics_show",
        help="Show usage summary (calls, cost, tokens) across all logged calls",
    )
    mt.add_argument(
        "--metrics-today",
        action="store_true",
        dest="metrics_today",
        help="With --metrics-show: limit to today's calls",
    )
    mt.add_argument(
        "--metrics-model",
        default="",
        dest="metrics_model",
        help="With --metrics-show: filter summary to one model",
    )
    mt.add_argument(
        "--metrics-clear", action="store_true", dest="metrics_clear", help="Clear the local metrics log"
    )
    mt.add_argument(
        "--metrics-export",
        metavar="FILE",
        dest="metrics_export",
        help="Export the full metrics log to FILE as JSON",
    )

    wf = p.add_argument_group("Workflows")
    wf.add_argument("--workflow-run", metavar="PATH", dest="workflow_run")
    wf.add_argument("--workflow-input", default="", dest="workflow_input")
    wf.add_argument("--workflow-scaffold", metavar="PATH", dest="workflow_scaffold")

    hk = p.add_argument_group("Hooks")
    hk.add_argument("--hooks-add", nargs=2, metavar=("EVENT", "COMMAND"), dest="hooks_add")
    hk.add_argument("--hook-tool-match", default=None, dest="hook_tool_match")
    hk.add_argument("--hooks-list", action="store_true", dest="hooks_list")
    hk.add_argument("--hooks-remove", type=int, metavar="INDEX", dest="hooks_remove")

    pm = p.add_argument_group("Permissions")
    pm.add_argument("--perms-list", action="store_true", dest="perms_list")
    pm.add_argument("--perms-add", nargs=2, metavar=("PATTERN", "DECISION"), dest="perms_add")
    pm.add_argument("--perms-reason", default="", dest="perms_reason")

    pln = p.add_argument_group("Plan Mode")
    pln.add_argument("--plan", metavar="TASK", dest="plan")
    pln.add_argument("--plan-context", default="", dest="plan_context")
    pln.add_argument("--plan-execute", action="store_true", dest="plan_execute")

    se = p.add_argument_group("Settings")
    se.add_argument("--settings-show", action="store_true", dest="settings_show")
    se.add_argument("--status-line", action="store_true", dest="status_line")

    return p
