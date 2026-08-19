"""
infrastructure/anthropic_api/rag_gateway.py — RAG answer generation (the
Anthropic Messages API call at the end of the retrieve-then-generate
pipeline)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_rag.py's generate() function. The
retrieval half (RAGIndex, tokenize/chunk/score — pure) is in
domain/tools.py; the local-disk index persistence half (build_index,
save/load) is in infrastructure/local_storage/rag_index_store.py — this
file is only the part that's a real HTTP call to Anthropic.
"""

from typing import List

import anthropic

from utils import sampling_kwargs
from domain.tools import Chunk


def generate(query: str, chunks: List[Chunk], api_key: str, model: str = "claude-sonnet-5") -> str:
    client = anthropic.Anthropic(api_key=api_key)
    ctx = "\n\n".join(f"[{c.source}]\n{c.content}" for c in chunks)
    system = ("Answer based on the provided context. Cite sources using the "
              "[filename] format. If the context doesn't contain the answer, "
              "say so clearly rather than guessing.")
    resp = client.messages.create(
        model=model, max_tokens=2048,
        **sampling_kwargs(model, temperature=0.2),
        system=system,
        messages=[{"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {query}"}])
    return resp.content[0].text
