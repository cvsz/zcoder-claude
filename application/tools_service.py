"""
application/tools_service.py — Use-case layer for Tool Use & Retrieval
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Same pattern as messaging_service.py / models_service.py / etc.: plain
functions, no print(), no argparse. Orchestrates
infrastructure/anthropic_api/{tools,vision,search,rag}_gateway.py,
infrastructure/voyage_api/embeddings_gateway.py, and
infrastructure/local_storage/rag_index_store.py.
"""

import json
from typing import Callable, List, Optional

from infrastructure.anthropic_api.tools_gateway import ToolCoder, MemoryToolHandler
from infrastructure.anthropic_api.vision_gateway import VisionCoder
from infrastructure.anthropic_api.search_gateway import SearchCoder
from infrastructure.anthropic_api.rag_gateway import generate as rag_generate
from infrastructure.voyage_api.embeddings_gateway import embed, DEFAULT_MODEL
from infrastructure.local_storage import rag_index_store
from domain.tools import (
    ToolRegistry, check_retired_tool_version, SERVER_TOOLS, SERVER_TOOL_BETAS,
    build_context_management, build_task_budget, with_allowed_callers,
    cosine_similarity, retrieve as rag_retrieve,
)

_NOOP = lambda *a, **k: None  # noqa: E731


# ── Agentic tool runner ────────────────────────────────────────────────────

def build_code_tools_registry() -> ToolRegistry:
    """Example registry with useful coding tools. Was
    claude_tools.build_code_tools_registry(); kept in the application
    layer (not domain) since its registered callables do local I/O
    (subprocess, file reads/writes) when invoked, even though the
    registry-construction call itself doesn't."""
    reg = ToolRegistry()

    def run_python(code: str) -> str:
        import subprocess
        import sys
        result = subprocess.run([sys.executable, "-c", code],
                                 capture_output=True, text=True, timeout=30)
        out = result.stdout.strip()
        err = result.stderr.strip()
        if err:
            return f"STDOUT:\n{out}\nSTDERR:\n{err}" if out else f"ERROR:\n{err}"
        return out or "(no output)"

    def read_file(path: str) -> str:
        try:
            with open(path) as f:
                return f.read()
        except Exception as e:
            return f"[ERROR] {e}"

    def write_file(path: str, content: str) -> str:
        try:
            with open(path, "w") as f:
                f.write(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"[ERROR] {e}"

    def list_files(directory: str = ".") -> str:
        import os
        try:
            return "\n".join(sorted(os.listdir(directory)))
        except Exception as e:
            return f"[ERROR] {e}"

    reg.register("run_python", "Execute Python code and return output",
        {"type": "object", "properties": {"code": {"type": "string", "description": "Python code to execute"}},
         "required": ["code"]}, run_python)
    reg.register("read_file", "Read a file from disk",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, read_file)
    reg.register("write_file", "Write content to a file",
        {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
         "required": ["path", "content"]}, write_file)
    reg.register("list_files", "List files in a directory",
        {"type": "object", "properties": {"directory": {"type": "string", "default": "."}},
         "required": []}, list_files)
    return reg


def run_tool_agent(prompt: str, api_key: str, model: str, system: Optional[str] = None,
                    max_turns: int = 10, on_tool_call: Callable = _NOOP) -> str:
    tc  = ToolCoder(api_key=api_key, model=model)
    reg = build_code_tools_registry()
    return tc.run_agent(prompt, reg, system=system, max_turns=max_turns, on_tool_call=on_tool_call)


def run_server_tools(prompt: str, tools: list, api_key: str, model: str,
                      use_context_management: bool = False, use_compaction: bool = False,
                      task_budget_tokens: Optional[int] = None, use_ptc: bool = False,
                      extra_tool_defs: Optional[list] = None,
                      response_inclusion: Optional[str] = None,
                      on_warning: Callable = _NOOP) -> str:
    """use_compaction and task_budget_tokens are independent of
    use_context_management — compaction rides inside the same
    context_management payload as clear_tool_uses, but either can be
    enabled alone. use_ptc marks any extra_tool_defs as callable from
    code_execution via allowed_callers; a no-op unless "code_execution"
    is also in tools."""
    tc = ToolCoder(api_key=api_key, model=model)
    cm = None
    if use_context_management or use_compaction:
        cm = build_context_management(clear_tool_uses=use_context_management, compact=use_compaction)
    tb = build_task_budget(task_budget_tokens) if task_budget_tokens else None

    extra_tools = []
    for t in (extra_tool_defs or []):
        if use_ptc and "code_execution" in tools:
            t = with_allowed_callers(t)
        extra_tools.append(t)

    return tc.generate_with_server_tools(
        prompt, tools, context_management=cm, task_budget=tb,
        extra_tools=extra_tools or None, response_inclusion=response_inclusion,
        on_warning=on_warning,
    )


def run_memory_agent(prompt: str, api_key: str, model: str,
                      memory_dir: str = "~/.ai-coder/memory", max_turns: int = 10,
                      on_memory_op: Callable = _NOOP) -> str:
    tc     = ToolCoder(api_key=api_key, model=model)
    memory = MemoryToolHandler(base_dir=memory_dir)
    return tc.run_agent_with_memory(prompt, memory, max_turns=max_turns, on_memory_op=on_memory_op)


def list_server_tools_info() -> list:
    """Returns [{"name", "description", "beta", "tool_type", "retired"}].
    Pure data, no print — the CLI layer formats it."""
    descs = {
        "web_search":     "Search the web for real-time information (GA)",
        "web_fetch":      "Fetch and read a specific URL (GA)",
        "code_execution": "Execute Python/bash in a secure sandbox (GA, code_execution_20260120 "
                           "— minimum version for programmatic tool calling)",
        "bash":           "Run bash commands (computer use)",
        "text_editor":    "Read and edit files (computer use)",
        "computer_use":   "Control a virtual desktop — version auto-selected per model",
        "memory":         "Persistent file-based memory across conversations (GA)",
        "tool_search":    "On-demand tool discovery for large tool libraries (beta)",
    }
    rows = []
    for name, desc in descs.items():
        beta = SERVER_TOOL_BETAS.get(name)
        tool_type = SERVER_TOOLS.get(name, {}).get("type", "")
        retired = check_retired_tool_version(tool_type)
        rows.append({"name": name, "description": desc, "beta": beta,
                     "tool_type": tool_type, "retired": retired})
    return rows


# ── Vision ───────────────────────────────────────────────────────────────

def analyse_image(path: Optional[str], prompt: str, api_key: str, model: str,
                   is_code: bool = False, language: str = "auto",
                   url: Optional[str] = None) -> str:
    vc = VisionCoder(api_key=api_key, model=model)
    if is_code:
        return vc.code_from_screenshot(path=path, url=url, language=language)
    return vc.analyse_image(path=path, url=url, prompt=prompt or "Describe this image in detail.")


def analyse_pdf(path: str, prompt: str, api_key: str, model: str) -> str:
    vc = VisionCoder(api_key=api_key, model=model)
    return vc.analyse_pdf(path=path, prompt=prompt or "Summarise this document.")


def compare_images(paths: List[str], prompt: str, api_key: str, model: str) -> str:
    vc = VisionCoder(api_key=api_key, model=model)
    return vc.compare_images(paths, prompt)


def ocr_image(path: str, api_key: str, model: str) -> str:
    vc = VisionCoder(api_key=api_key, model=model)
    return vc.extract_text(path=path)


# ── Web search & fetch ──────────────────────────────────────────────────

def web_search(prompt: str, api_key: str, model: str, max_searches: int = 5,
                show_citations: bool = True, web_fetch: bool = False,
                response_inclusion: Optional[str] = None) -> dict:
    sc = SearchCoder(api_key=api_key, model=model)
    return sc.search(prompt, web_search=True, web_fetch=web_fetch, max_searches=max_searches,
                      show_citations=show_citations, response_inclusion=response_inclusion)


def fetch_url(url: str, instruction: str, api_key: str, model: str) -> str:
    sc = SearchCoder(api_key=api_key, model=model)
    return sc.fetch_and_summarise(url, instruction)


# ── Embeddings (Voyage AI) ──────────────────────────────────────────────

def embed_text(text: str, model: str = DEFAULT_MODEL, input_type: str = "document") -> list:
    [vec] = embed([text], model=model, input_type=input_type)
    return vec


def embed_lines(path: str, model: str = DEFAULT_MODEL, input_type: str = "document") -> dict:
    """Returns {"lines": [...], "vecs": [...]}."""
    with open(path) as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    vecs = embed(lines, model=model, input_type=input_type)
    return {"lines": lines, "vecs": vecs}


def embed_similarity(text_a: str, text_b: str, model: str = DEFAULT_MODEL) -> float:
    vec_a, vec_b = embed([text_a, text_b], model=model, input_type="document")
    return cosine_similarity(vec_a, vec_b)


# ── RAG ──────────────────────────────────────────────────────────────────

def rag_build_index(name: str, folder: str, chunk_size: int = 600):
    return rag_index_store.build_index(name, folder, chunk_size)


def rag_query(name: str, query: str, api_key: str, model: str, k: int = 5) -> dict:
    """Returns {"found_index": bool, "chunks": [...], "answer": str|None}."""
    idx = rag_index_store.load_index(name)
    if not idx:
        return {"found_index": False, "chunks": [], "answer": None}
    chunks = rag_retrieve(idx, query, k)
    if not chunks:
        return {"found_index": True, "chunks": [], "answer": None}
    answer = rag_generate(query, chunks, api_key, model)
    return {"found_index": True, "chunks": chunks, "answer": answer}


def rag_list_indexes() -> list:
    """Returns [{"name": str, "chunk_count": int}, ...]."""
    rows = []
    for p in rag_index_store.list_index_files():
        try:
            d = json.loads(p.read_text())
            rows.append({"name": d["name"], "chunk_count": len(d.get("chunks", []))})
        except Exception:
            pass
    return rows
