"""
# mypy: ignore-errors
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

from core.exceptions import ZCoderError
from domain.tools import cosine_similarity
from infrastructure.anthropic_api.http_client import CircuitBreaker, retry, urlopen_json

VOYAGE_ENDPOINT = "https://api.voyageai.com/v1/embeddings"
_breaker = CircuitBreaker(failure_threshold=5, reset_timeout=30)

DEFAULT_MODEL = "voyage-3.5"
CODE_MODEL = "voyage-code-3"


def _voyage_key(explicit: str | None = None) -> str:
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
def _call(req: urllib.request.Request) -> dict:
    return urlopen_json(req, timeout=60)


def embed(
    texts: list[str],
    model: str = DEFAULT_MODEL,
    input_type: str | None = "document",
    api_key: str | None = None,
) -> list[list[float]]:
    """Embed a list of strings, return one vector per input."""
    key = _voyage_key(api_key)
    payload = {"input": texts, "model": model}
    if input_type:
        payload["input_type"] = input_type
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    req = urllib.request.Request(
        VOYAGE_ENDPOINT, data=json.dumps(payload).encode(), headers=headers, method="POST"
    )
    try:
        data = _call(req)
    except ZCoderError as e:
        raise RuntimeError(f"Voyage API error: {e.message}") from e
    return [item["embedding"] for item in data.get("data", [])]


class EmbeddingIndex:
    """Minimal in-memory semantic index: embed a corpus once, then rank
    queries against it by cosine similarity."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self.api_key = api_key
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._vecs: list[list[float]] = []

    def add(self, ids: list[str], texts: list[str], batch_size: int = 128):
        for i in range(0, len(texts), batch_size):
            batch_ids = ids[i : i + batch_size]
            batch_texts = texts[i : i + batch_size]
            vecs = embed(batch_texts, model=self.model, input_type="document", api_key=self.api_key)
            self._ids.extend(batch_ids)
            self._texts.extend(batch_texts)
            self._vecs.extend(vecs)

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        if not self._vecs:
            return []
        [qvec] = embed([query], model=self.model, input_type="query", api_key=self.api_key)
        scored = [
            {"id": i, "text": t, "score": cosine_similarity(qvec, v)}
            for i, t, v in zip(self._ids, self._texts, self._vecs, strict=False)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
