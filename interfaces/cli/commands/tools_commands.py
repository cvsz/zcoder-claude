"""
interfaces/cli/commands/tools_commands.py — CLI presentation for
Tool Use & Retrieval (custom/server tools, memory tool, vision, web
search/fetch, embeddings, RAG)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Only print()/sys.exit() and CLI-facing string building live here — all
real work is delegated to application/tools_service.py. Extracted
2026-08-16 from claude_tools.py, claude_vision.py, claude_search.py,
claude_embeddings.py, claude_rag.py.
"""

import sys
from pathlib import Path
from typing import List, Optional

from application import tools_service as service

__all__ = [
    "cmd_tool_agent", "cmd_server_tool", "cmd_memory_agent", "cmd_list_server_tools",
    "cmd_vision", "cmd_vision_url", "cmd_vision_pdf", "cmd_vision_compare", "cmd_vision_ocr",
    "cmd_web_search", "cmd_fetch_url",
    "cmd_embed", "cmd_embed_file", "cmd_embed_similarity",
    "cmd_rag_index", "cmd_rag_query", "cmd_rag_list",
]

SUPPORTED_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


# ── Custom / agentic tool use ────────────────────────────────────────────

def cmd_tool_agent(prompt: str, api_key: str, model: str,
                    system: str = None, max_turns: int = 10):
    """Run agentic tool loop with code tools."""
    print(f"\033[94mℹ Agentic tool runner | max_turns={max_turns}\033[0m\n")

    def on_tool_call(name, tool_input):
        import json
        print(f"\033[90m  [tool] {name}({json.dumps(tool_input)[:80]})\033[0m")

    result = service.run_tool_agent(prompt, api_key, model, system=system,
                                     max_turns=max_turns, on_tool_call=on_tool_call)
    print(result)
    return result


def cmd_server_tool(prompt: str, tools: list, api_key: str, model: str,
                     use_context_management: bool = False, use_compaction: bool = False,
                     task_budget_tokens: Optional[int] = None, use_ptc: bool = False,
                     extra_tool_defs: Optional[list] = None):
    """Call with Anthropic server tools."""
    print(f"\033[94mℹ Server tools: {', '.join(tools)}\033[0m\n")

    def on_warning(msg):
        print(f"\033[93m⚠ {msg}\033[0m")

    result = service.run_server_tools(
        prompt, tools, api_key, model, use_context_management=use_context_management,
        use_compaction=use_compaction, task_budget_tokens=task_budget_tokens,
        use_ptc=use_ptc, extra_tool_defs=extra_tool_defs, on_warning=on_warning,
    )
    print(result)
    return result


def cmd_memory_agent(prompt: str, api_key: str, model: str,
                      memory_dir: str = "~/.ai-coder/memory", max_turns: int = 10):
    """Run an agent loop backed by the native memory tool."""
    print(f"\033[94mℹ Memory-tool agent | dir={memory_dir}\033[0m\n")

    def on_memory_op(command, path):
        print(f"\033[90m  [memory:{command}] {path}\033[0m")

    result = service.run_memory_agent(prompt, api_key, model, memory_dir=memory_dir,
                                       max_turns=max_turns, on_memory_op=on_memory_op)
    print(result)
    return result


def cmd_list_server_tools():
    print("\nAvailable server tools:")
    for row in service.list_server_tools_info():
        tag = f" [beta: {row['beta']}]" if row["beta"] else ""
        if row["retired"]:
            tag += f" [note: newer version {row['retired']['replacement']} available — {row['retired']['notes']}]"
        print(f"  {row['name']:<18} — {row['description']}{tag}")
    from domain.tools import ADVANCED_TOOL_USE_BETA, COMPACTION_BETA, TASK_BUDGET_BETA, TASK_BUDGET_MODELS
    print("\n  Also available on custom tool definitions (--tool-file), not server tools:")
    print("    input_examples   — Tool Use Examples, worked examples of a correct call.")
    print(f"                       Use with_input_examples(). [beta: {ADVANCED_TOOL_USE_BETA}]")
    print("    allowed_callers  — Programmatic Tool Calling: callable from code_execution")
    print("                       instead of one round-trip per call. Use")
    print(f"                       with_allowed_callers(). [beta: {ADVANCED_TOOL_USE_BETA}]")
    print("\n  Context/budget controls, not tools but combine with any of the above:")
    print("    context_management compact edit — server-side conversation summarization.")
    print(f"                       Use build_context_management(compact=True). [beta: {COMPACTION_BETA}]")
    print("    task_budget        — advisory token countdown for a full agentic loop.")
    print(f"                       Use build_task_budget(). [beta: {TASK_BUDGET_BETA}, "
          f"models: {sorted(TASK_BUDGET_MODELS)}]")


# ── Vision ───────────────────────────────────────────────────────────────

def _validate_image(path: str):
    p = Path(path)
    if not p.exists():
        print(f"\033[91m✗ File not found: {path}\033[0m", file=sys.stderr)
        sys.exit(1)
    if p.suffix.lower() not in SUPPORTED_IMAGE_TYPES:
        print(f"\033[91m✗ Unsupported image type: {p.suffix}\033[0m", file=sys.stderr)
        sys.exit(1)


def cmd_vision(path: str, prompt: str, api_key: str, model: str,
               is_code: bool = False, language: str = "auto"):
    _validate_image(path)
    size = Path(path).stat().st_size // 1024
    print(f"\033[94mℹ Analysing image: {path} ({size} KB)\033[0m\n")
    result = service.analyse_image(path, prompt, api_key, model, is_code=is_code, language=language)
    print(result)
    return result


def cmd_vision_url(url: str, prompt: str, api_key: str, model: str):
    print(f"\033[94mℹ Analysing image URL: {url}\033[0m\n")
    result = service.analyse_image(None, prompt, api_key, model, url=url)
    print(result)
    return result


def cmd_vision_pdf(path: str, prompt: str, api_key: str, model: str):
    p = Path(path)
    if not p.exists():
        print(f"\033[91m✗ File not found: {path}\033[0m", file=sys.stderr)
        sys.exit(1)
    size = p.stat().st_size // 1024
    print(f"\033[94mℹ Analysing PDF: {path} ({size} KB)\033[0m\n")
    result = service.analyse_pdf(path, prompt, api_key, model)
    print(result)
    return result


def cmd_vision_compare(paths: List[str], prompt: str, api_key: str, model: str):
    for p in paths:
        _validate_image(p)
    print(f"\033[94mℹ Comparing {len(paths)} images\033[0m\n")
    result = service.compare_images(paths, prompt, api_key, model)
    print(result)
    return result


def cmd_vision_ocr(path: str, api_key: str, model: str):
    _validate_image(path)
    print(f"\033[94mℹ OCR: {path}\033[0m\n")
    result = service.ocr_image(path, api_key, model)
    print(result)
    return result


# ── Web search & fetch ──────────────────────────────────────────────────

def cmd_web_search(prompt: str, api_key: str, model: str, max_searches: int = 5,
                    show_citations: bool = True, web_fetch: bool = False,
                    response_inclusion: Optional[str] = None):
    print(f"\033[94mℹ Web Search enabled | max_searches={max_searches}\033[0m\n")
    result = service.web_search(prompt, api_key, model, max_searches=max_searches,
                                 show_citations=show_citations, web_fetch=web_fetch,
                                 response_inclusion=response_inclusion)
    print(result["response"])
    if show_citations and result["citations"]:
        print(f"\n\033[90m── Sources ({'─'*30})\033[0m")
        for i, c in enumerate(result["citations"], 1):
            print(f"\033[90m[{i}] {c['title']}\n    {c['url']}\033[0m")
    u = result.get("usage", {})
    searches = result.get("searches", 0)
    print(f"\n\033[90m[searches={searches}  input={u.get('input_tokens',0)}  output={u.get('output_tokens',0)}]\033[0m")
    return result["response"]


def cmd_fetch_url(url: str, instruction: str, api_key: str, model: str):
    print(f"\033[94mℹ Fetching: {url}\033[0m\n")
    result = service.fetch_url(url, instruction, api_key, model)
    print(result)
    return result


# ── Embeddings ───────────────────────────────────────────────────────────

def cmd_embed(text: str, model: str = "voyage-3.5", input_type: str = "document"):
    print(f"\033[94mℹ Embedding via Voyage AI ({model})\033[0m\n")
    try:
        vec = service.embed_text(text, model=model, input_type=input_type)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return
    print(f"  dimensions: {len(vec)}")
    print(f"  first 8:    {[round(v, 5) for v in vec[:8]]}")
    return vec


def cmd_embed_file(path: str, model: str = "voyage-3.5", input_type: str = "document"):
    print(f"\033[94mℹ Embedding lines from {path} via Voyage AI ({model})\033[0m\n")
    try:
        outcome = service.embed_lines(path, model=model, input_type=input_type)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return
    for line, vec in zip(outcome["lines"], outcome["vecs"]):
        print(f"  [{len(vec)}d] {line[:60]}{'...' if len(line) > 60 else ''}")
    return outcome["vecs"]


def cmd_embed_similarity(text_a: str, text_b: str, model: str = "voyage-3.5"):
    print(f"\033[94mℹ Cosine similarity via Voyage AI ({model})\033[0m\n")
    try:
        sim = service.embed_similarity(text_a, text_b, model=model)
    except RuntimeError as e:
        print(f"[ERROR] {e}")
        return
    print(f"  \"{text_a[:50]}\"")
    print(f"  \"{text_b[:50]}\"")
    print(f"  similarity: {sim:.4f}")
    return sim


# ── RAG ──────────────────────────────────────────────────────────────────

def cmd_rag_index(name: str, folder: str, chunk_size: int = 600):
    print(f"Building RAG index '{name}' from {folder} …")
    idx = service.rag_build_index(name, folder, chunk_size)
    print(f"✓ Indexed {len(idx.chunks)} chunks from {folder}")


def cmd_rag_query(name: str, query: str, api_key: str, model: str, k: int = 5):
    outcome = service.rag_query(name, query, api_key, model, k)
    if not outcome["found_index"]:
        print(f"Index not found: {name}\n  Run --rag-index to build it.")
        return
    if not outcome["chunks"]:
        print("No relevant chunks found.")
        return
    print(f"Retrieved {len(outcome['chunks'])} chunk(s). Generating answer …\n")
    print(outcome["answer"])


def cmd_rag_list():
    rows = service.rag_list_indexes()
    if not rows:
        print("No RAG indexes found.")
        return
    for row in rows:
        print(f"  {row['name']:<24} {row['chunk_count']} chunks")
