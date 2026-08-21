"""
# mypy: ignore-errors
interfaces/cli/commands/messaging_commands.py — CLI presentation for
Core Messaging (streaming, structured outputs, citations/RAG, extended
thinking, token counting, zai-live REPL)
AI Model Coder CLI v1.46.0 (Clean Architecture refactor, Phase B)

Only print()/input() and CLI-facing string building live here — all real
work is delegated to application/messaging_service.py. Extracted
2026-08-15 from claude_stream.py, claude_structured.py,
claude_citations.py, claude_thinking.py, claude_tokens.py, claude_live.py.
"""

import json
import sys

from application import messaging_service as service
from domain.messaging import ThinkingModeError  # re-exported for main.py

__all__ = [
    "cmd_stream",
    "cmd_stream_tools",
    "cmd_structured",
    "cmd_structured_analyse",
    "cmd_structured_extract",
    "cmd_cite",
    "cmd_rag",
    "cmd_thinking",
    "cmd_count_tokens",
    "cmd_live",
    "ThinkingModeError",
]


# ── Streaming ────────────────────────────────────────────────────────────


def _print_text(text: str):
    sys.stdout.write(text)
    sys.stdout.flush()


def cmd_stream(
    prompt: str,
    api_key: str,
    model: str,
    system: str = None,
    file_content: str = None,
    show_thinking: bool = False,
):
    print("\033[94mℹ Streaming response…\033[0m\n")

    usage_box = {}

    def on_thinking_start():
        print("\n\033[90m[thinking] ", end="", file=sys.stderr, flush=True)

    def on_thinking(chunk):
        print(chunk, end="", file=sys.stderr, flush=True)

    def on_thinking_stop():
        print("\033[0m", file=sys.stderr)

    def on_usage(usage):
        usage_box.update(usage)

    result = service.stream_text(
        prompt,
        api_key,
        model,
        system=system,
        file_content=file_content,
        show_thinking=show_thinking,
        on_text=_print_text,
        on_thinking=on_thinking,
        on_thinking_start=on_thinking_start,
        on_thinking_stop=on_thinking_stop,
        on_usage=on_usage,
    )
    print()  # final newline
    if usage_box:
        print(
            f"\033[90m[tokens] in={usage_box.get('input_tokens', 0)}  "
            f"out={usage_box.get('output_tokens', 0)}\033[0m"
        )
    return result


def cmd_stream_tools(prompt: str, tools: list, api_key: str, model: str, system: str = None):
    """Stream a turn with fine-grained tool input streaming on."""
    print("\033[94mℹ Streaming with fine-grained tool input…\033[0m\n")

    def on_tool_start(name):
        print(f"\n\033[90m[tool_use:{name}] ", end="", file=sys.stderr, flush=True)

    def on_tool_delta(frag):
        print(frag, end="", file=sys.stderr, flush=True)

    def on_tool_stop():
        print("\033[0m", file=sys.stderr)

    def on_refusal(refusal):
        if refusal:
            print(
                f"\033[91m[refusal] category={refusal['category']} " f"{refusal['explanation']}\033[0m",
                file=sys.stderr,
            )

    result = service.stream_with_tools(
        prompt,
        tools,
        api_key,
        model,
        system=system,
        on_text=_print_text,
        on_tool_start=on_tool_start,
        on_tool_delta=on_tool_delta,
        on_tool_stop=on_tool_stop,
        on_refusal=on_refusal,
    )
    print()
    if result["tool_calls"]:
        print(f"\n\033[90m── {len(result['tool_calls'])} tool call(s) ─────\033[0m")
        for tc in result["tool_calls"]:
            print(f"  {tc['name']}: {tc['input'] if tc['input'] is not None else tc['input_raw'][:120]}")
    return result


# ── Structured outputs ──────────────────────────────────────────────────

_STRUCTURED_LABELS = {
    "schema_file": "Structured output (schema from {path})",
    "schema_inline": "Structured output (inline schema)",
    "json_object": "Structured output (JSON object mode)",
}


def cmd_structured(
    prompt: str,
    api_key: str,
    model: str,
    schema_path: str = None,
    schema_inline: str = None,
    pretty: bool = True,
) -> dict:
    outcome = service.generate_structured(
        prompt, api_key, model, schema_path=schema_path, schema_inline=schema_inline
    )
    label = _STRUCTURED_LABELS[outcome["mode"]].format(path=schema_path)
    print(f"\033[94mℹ {label}\033[0m\n")
    indent = 2 if pretty else None
    print(json.dumps(outcome["result"], indent=indent, ensure_ascii=False))
    return outcome["result"]


def cmd_structured_analyse(file_path: str, api_key: str, model: str) -> dict:
    print(f"\033[94mℹ Structured code analysis: {file_path}\033[0m\n")
    result = service.analyse_code_structured(file_path, api_key, model)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def cmd_structured_extract(content_file: str, schema_path: str, api_key: str, model: str) -> dict:
    print(f"\033[94mℹ Extracting structured data from {content_file}\033[0m\n")
    result = service.extract_structured(content_file, schema_path, api_key, model)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


# ── Citations & RAG ──────────────────────────────────────────────────────


def cmd_cite(question: str, doc_files: list, api_key: str, model: str):
    outcome = service.cite_documents(question, doc_files, api_key, model)
    for f in outcome["missing"]:
        print(f"  [WARN] Not found: {f}")

    if outcome["result"] is None:
        print("[ERROR] No valid documents found.")
        return None

    n_docs = len(doc_files) - len(outcome["missing"])
    print(f"\033[94mℹ Answering with citations from {n_docs} document(s)\033[0m\n")
    result = outcome["result"]
    print(result["answer"])
    if result["citations"]:
        print("\n\033[90m── Citations ────────────────────────────\033[0m")
        for i, c in enumerate(result["citations"], 1):
            print(f"\033[90m[{i}] {c['document']}: \"{c['text'][:80]}…\"\033[0m")
    return result


def cmd_rag(question: str, directory: str, api_key: str, model: str, pattern: str = "*.md"):
    print(f"\033[94mℹ RAG from {directory} ({pattern})\033[0m\n")
    result = service.rag_query(question, directory, api_key, model, pattern)
    print(result["answer"])
    if result["citations"]:
        print("\n\033[90m── Citations ────────────────────────────\033[0m")
        for i, c in enumerate(result["citations"], 1):
            print(f"\033[90m[{i}] {c['document']}\033[0m")
    return result


# ── Extended / adaptive thinking ─────────────────────────────────────────


def cmd_thinking(
    prompt: str,
    api_key: str,
    model: str,
    budget: int,
    effort: str,
    adaptive,
    show_thinking: bool,
    stream: bool,
    system: str = None,
    display_omitted: bool = False,
    legacy_budget: bool = False,
):
    """Called from main.py --thinking. `adaptive`: True/False forces a
    mode; None (main.py's default when --adaptive isn't passed)
    auto-selects per model. `legacy_budget` (main.py's
    --effort-legacy-budget) forces the old manual budget_tokens path, and
    raises ThinkingModeError up front on models where that's a 400."""
    mode = service.resolve_thinking_mode_label(api_key, model, adaptive, legacy_budget)
    print(
        f"\033[94mℹ Extended Thinking | mode={mode} | effort={effort or 'default'} | "
        f"budget={budget} tokens (manual mode only)\033[0m\n"
    )

    if stream:

        def on_thinking_start():
            print("\n\033[90m[thinking] ", end="", file=sys.stderr, flush=True)

        def on_thinking(chunk):
            print(chunk, end="", file=sys.stderr, flush=True)

        def on_thinking_stop():
            print("\033[0m", file=sys.stderr)

        result = service.generate_thinking(
            prompt,
            api_key,
            model,
            budget,
            effort,
            adaptive,
            show_thinking,
            stream,
            system=system,
            display_omitted=display_omitted,
            legacy_budget=legacy_budget,
            on_text=_print_text,
            on_thinking=on_thinking,
            on_thinking_start=on_thinking_start,
            on_thinking_stop=on_thinking_stop,
        )
        print()
        return result

    def on_thinking(text):
        print("\n\033[90m── THINKING ──────────────────────\033[0m", file=sys.stderr)
        print(text, file=sys.stderr)
        print("\033[90m── END THINKING ──────────────────\033[0m\n", file=sys.stderr)

    result = service.generate_thinking(
        prompt,
        api_key,
        model,
        budget,
        effort,
        adaptive,
        show_thinking,
        stream,
        system=system,
        display_omitted=display_omitted,
        legacy_budget=legacy_budget,
        on_thinking=on_thinking,
    )
    print(result["response"])
    usage = result.get("usage", {})
    if usage:
        thinking_tokens = usage.get("output_tokens_details", {}).get("thinking_tokens", 0)
        print(
            f"\n\033[90m[tokens] input={usage.get('input_tokens', 0)}  "
            f"output={usage.get('output_tokens', 0)}  "
            f"thinking={thinking_tokens}\033[0m"
        )
    return result["response"]


# ── Token counting ───────────────────────────────────────────────────────


def cmd_count_tokens(
    prompt: str, api_key: str, model: str, system: str = None, file_path: str = None, budget: int = None
):
    outcome = service.count_tokens(prompt, api_key, model, system=system, file_path=file_path, budget=budget)
    tokens = outcome["tokens"]
    est = outcome["estimate"]

    print(f"\n  Model:            {model}")
    print(f"  Input tokens:     {tokens:,}")
    print(f"  Estimated cost:   ${est['estimated_cost_usd']:.6f} (input only)")

    b = outcome["budget"]
    if b is not None:
        bar = "█" * int(b["pct"] // 5) + "░" * (20 - int(b["pct"] // 5))
        print(f"  Budget usage:     [{bar}] {b['pct']:.1f}% of {budget:,}")
        if b["over"]:
            print(f"\033[91m  ⚠ EXCEEDS BUDGET by {b['exceeded_by']:,} tokens\033[0m")
        else:
            print(f"\033[92m  ✓ Within budget ({b['remaining']:,} tokens remaining)\033[0m")


# ── zai-live REPL ─────────────────────────────────────────────────────────


def _handle_slash(cmd: str, session) -> bool:
    """Return True if handled, False to let the main loop treat it as normal input."""
    parts = cmd[1:].split(maxsplit=1)
    name = parts[0].lower() if parts else ""
    arg = parts[1] if len(parts) > 1 else ""

    if name == "help":
        print("  /ambient <note>  — push background context")
        print("  /clear-ambient   — clear ambient buffer")
        print("  /model [name]    — show or change model")
        print("  /status          — session stats")
        print("  /clear           — clear conversation history")
        print("  /exit            — end session")
        return True
    if name == "ambient" and arg:
        session.ambient.push("manual", arg)
        print("(ambient noted)")
        return True
    if name == "clear-ambient":
        session.ambient.clear()
        print("(ambient buffer cleared)")
        return True
    if name == "model":
        if arg:
            session.model = arg.strip()
            print(f"Model → {session.model}")
        else:
            print(f"Current model: {session.model}")
        return True
    if name == "status":
        print(json.dumps(session.stats(), indent=2))
        return True
    if name == "clear":
        session.history = []
        print("(history cleared)")
        return True
    if name in ("exit", "quit"):
        raise KeyboardInterrupt
    return False


def cmd_live(
    api_key: str, model: str = "claude-sonnet-5", temperature: float = 0.7, personality_prompt: str = ""
):
    session = service.create_live_session(api_key, model, temperature, personality_prompt)
    print(f"⚡ zai-live  model={model}  /help for commands  Ctrl+C to quit\n")
    while True:
        try:
            text = input("You: ").strip()
            if not text:
                continue
            if text.startswith("/"):
                if not _handle_slash(text, session):
                    print(f"Unknown: {text}")
                continue
            print("Assistant: ", end="", flush=True)
            service.live_send(session, text, on_chunk=_print_text)
            print("\n")
        except KeyboardInterrupt:
            print("\nSession ended.")
            break
        except EOFError:
            break
