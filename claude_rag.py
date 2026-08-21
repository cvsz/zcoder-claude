"""
claude_rag.py — Retrieval-Augmented Generation pipeline (compatibility shim)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - Chunk, RAGIndex, SUPPORTED_EXTS (was SUPPORTED_EXTS, now
    SUPPORTED_RAG_EXTS in domain/tools.py — re-exported under both names
    here), tokenize (was _tokenize), chunk_text (was _chunk_text),
    retrieve → domain/tools.py
  - build_index, load_index → infrastructure/local_storage/rag_index_store.py
  - generate → infrastructure/anthropic_api/rag_gateway.py
  - cmd_rag_index, cmd_rag_query, cmd_rag_list →
    interfaces/cli/commands/tools_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.tools import (
    SUPPORTED_RAG_EXTS,
    Chunk,
    RAGIndex,
    chunk_text,
    retrieve,
    tokenize,
)
from domain.tools import (
    SUPPORTED_RAG_EXTS as SUPPORTED_EXTS,
)
from infrastructure.anthropic_api.rag_gateway import generate
from infrastructure.local_storage.rag_index_store import INDEX_DIR, build_index, load_index
from interfaces.cli.commands.tools_commands import cmd_rag_index, cmd_rag_list, cmd_rag_query

__all__ = [
    "Chunk",
    "RAGIndex",
    "SUPPORTED_EXTS",
    "SUPPORTED_RAG_EXTS",
    "INDEX_DIR",
    "tokenize",
    "chunk_text",
    "retrieve",
    "build_index",
    "load_index",
    "generate",
    "cmd_rag_index",
    "cmd_rag_query",
    "cmd_rag_list",
]
