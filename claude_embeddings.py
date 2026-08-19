"""
claude_embeddings.py — Text embeddings (compatibility shim)
AI Model Coder CLI v1.47.0 (Clean Architecture refactor, Phase C)

Real implementation moved 2026-08-16:
  - embed, cosine_similarity, EmbeddingIndex, DEFAULT_MODEL, CODE_MODEL
    → infrastructure/voyage_api/embeddings_gateway.py (cosine_similarity
    re-exported from domain/tools.py, where the pure math actually lives)
  - cmd_embed, cmd_embed_file, cmd_embed_similarity →
    interfaces/cli/commands/tools_commands.py

New code should import from those locations directly rather than through
this shim.
"""

from domain.tools import cosine_similarity
from infrastructure.voyage_api.embeddings_gateway import embed, EmbeddingIndex, DEFAULT_MODEL, CODE_MODEL
from interfaces.cli.commands.tools_commands import cmd_embed, cmd_embed_file, cmd_embed_similarity

__all__ = [
    "embed", "cosine_similarity", "EmbeddingIndex", "DEFAULT_MODEL", "CODE_MODEL",
    "cmd_embed", "cmd_embed_file", "cmd_embed_similarity",
]
