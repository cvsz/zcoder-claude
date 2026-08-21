"""
infrastructure/local_storage/rag_index_store.py — local-disk persistence
for RAG indexes
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_rag.py's build_index()/_save_index()/
load_index(). This is the project's first local-disk-only infrastructure
adapter — everything in infrastructure/anthropic_api/ and
infrastructure/voyage_api/ is an HTTP client; this one is a filesystem
adapter instead, kept in its own subpackage rather than folded into
either vendor package since it isn't a vendor call at all. Pure
retrieval math (tokenize/chunk/score/retrieve) stays in domain/tools.py;
this file is only the "touches disk" half.
"""

import json
from pathlib import Path

from domain.tools import SUPPORTED_RAG_EXTS, RAGIndex, build_idf, chunk_text, tokenize

INDEX_DIR = Path.home() / ".ai-coder" / "rag_indexes"


def build_index(name: str, folder: str, chunk_size: int = 600, overlap: int = 100) -> RAGIndex:
    idx = RAGIndex(name=name)
    total = 0
    token_sets = []
    for path in Path(folder).rglob("*"):
        if path.suffix.lower() not in SUPPORTED_RAG_EXTS:
            continue
        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue
        for chunk in chunk_text(str(path), text, chunk_size, overlap):
            idx.chunks.append(chunk)
            total += 1
            token_sets.append(set(tokenize(chunk.content)))
    idx.idf = build_idf(token_sets, total)
    save_index(idx)
    return idx


def save_index(idx: RAGIndex):
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    (INDEX_DIR / f"{idx.name}.json").write_text(json.dumps(idx.to_dict(), indent=2))


def load_index(name: str) -> RAGIndex | None:
    p = INDEX_DIR / f"{name}.json"
    if not p.exists():
        return None
    return RAGIndex.from_dict(json.loads(p.read_text()))


def list_index_files():
    if not INDEX_DIR.exists():
        return []
    return sorted(INDEX_DIR.glob("*.json"))
