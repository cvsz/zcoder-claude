"""
domain/batch.py — Messages Batch API domain layer
AI Model Coder CLI v1.52.0 (Clean Architecture refactor, Phase C, Context #4)

Pure data for the Batch API bounded context — the 300k-output beta
feature flag and its eligible-model set. No I/O, no print(). Extracted
2026-08-18 from claude_batch.py. Same convention as every other BETA_*
constant in domain/ (domain/messaging.py, domain/tools.py,
domain/files.py): the beta header string is domain-meaningful (part of
what "a 300k-output batch request" *is*), even though only
infrastructure/anthropic_api/batch_gateway.py ever puts it on the wire.
"""

# 300k output tokens on the Message Batches API. Per platform.claude.com/docs
# (checked 2026-07-02): "On the Message Batches API, Claude Opus 4.8, Opus
# 4.7, Opus 4.6, Sonnet 5, and Sonnet 4.6 support up to 300k output tokens by
# using the output-300k-2026-03-24 beta header." Batch-only — the
# synchronous Messages API max_output values are unaffected.
OUTPUT_300K_BETA = "output-300k-2026-03-24"
OUTPUT_300K_MODELS = {
    "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
    "claude-sonnet-5", "claude-sonnet-4-6",
}
OUTPUT_300K_MAX_TOKENS = 300_000
