"""
infrastructure/voyage_api/embeddings_gateway.py — Voyage AI embeddings
live API adapter
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Extracted 2026-08-16 from claude_embeddings.py. In its own
infrastructure/voyage_api/ package rather than infrastructure/anthropic_api/
— this is a genuinely different vendor. Per the original module's
docstring: Anthropic does not offer its own embedding model; this wraps
Voyage AI's HTTP endpoint (an Anthropic partner, not an Anthropic-hosted
API), and needs its own VOYAGE_API_KEY, separate from ANTHROPIC_API_KEY.
Keeping it in a separate infrastructure subpackage means a future circuit
breaker / outage there is never mistaken for an Anthropic API outage.
"""

import json
import os
import urllib.request
from typing import List, Optional

from exceptions import AICoderError
from resilience import CircuitBreaker, retry, urlopen_json
from domain.tools import cosine_similarity

VOYAGE_ENDPOINT = "https://api.voyageai.com/v1/embeddings"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

DEFAULT_MODEL = "voyage-3.5"
CODE_MODEL    = "voyage-code-3"


def _voyage_key(explicit: Optional[str] = None) -> str:
    key = explicit or os.getenv("VOYAGE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "VOYAGE_API_KEY not set. Embeddings use Voyage AI, not the "
            "Anthropic API — Anthropic doesn't host its own embedding "
            "model. Get a key at https://dashboard.voyageai.com and set "
            "VOYAGE_API_KEY (separate from ANTHROPIC_API_KEY)."
        )
    return key


@retry(max_attempts=4, base_delay=1.0, max_delay=15.0, breaker=_breaker)
def _call(req: "urllib.request.Request") -> dict:
    return urlopen_json(req, timeout=60)


def embed(texts: List[str], model: str = DEFAULT_MODEL, input_type: Optional[str] = "document",
          api_key: Optional[str] = None) -> List[List[float]]:
    """Embed a list of strings, return one vector per input."""
    key = _voyage_key(api_key)
    payload = {"input": texts, "model": model}
    if input_type:
        payload["input_type"] = input_type
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    req = urllib.request.Request(VOYAGE_ENDPOINT, data=json.dumps(payload).encode(),
                                  headers=headers, method="POST")
    try:
        data = _call(req)
    except AICoderError as e:
        raise RuntimeError(f"Voyage API error: {e.message}") from e
    return [item["embedding"] for item in data.get("data", [])]


class EmbeddingIndex:
    """Minimal in-memory semantic index: embed a corpus once, then rank
    queries against it by cosine similarity."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None):
        self.model   = model
        self.api_key = api_key
        self._ids:   List[str] = []
        self._texts: List[str] = []
        self._vecs:  List[List[float]] = []

    def add(self, ids: List[str], texts: List[str], batch_size: int = 128):
        for i in range(0, len(texts), batch_size):
            batch_ids   = ids[i:i + batch_size]
            batch_texts = texts[i:i + batch_size]
            vecs = embed(batch_texts, model=self.model, input_type="document", api_key=self.api_key)
            self._ids.extend(batch_ids)
            self._texts.extend(batch_texts)
            self._vecs.extend(vecs)

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        if not self._vecs:
            return []
        [qvec] = embed([query], model=self.model, input_type="query", api_key=self.api_key)
        scored = [{"id": i, "text": t, "score": cosine_similarity(qvec, v)}
                  for i, t, v in zip(self._ids, self._texts, self._vecs)]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
