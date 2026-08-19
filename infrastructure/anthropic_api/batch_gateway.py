"""
infrastructure/anthropic_api/batch_gateway.py — Messages Batch API gateway
AI Model Coder CLI v1.52.0 (Clean Architecture refactor, Phase C, Context #4)

Real calls to the Anthropic SDK's batches endpoints — zero print().
Extracted 2026-08-18 from claude_batch.py's BatchCoder class.

The original had two direct print() calls buried in this class: an
OUTPUT_300K_MODELS eligibility warning in __init__, and a live
'\\r...end=""' progress line in wait()'s polling loop. Both are now
on_warning/on_progress callbacks (Callable[[str], None] = _NOOP
default), matching the exact convention established in
infrastructure/local_storage/code_agent_store.py's HooksEngine/
McpConnector/SubagentRegistry — not a special case for this module.
interfaces/cli/commands/batch_commands.py supplies the real printers.
"""

import json
import time
from pathlib import Path
from typing import Callable
import anthropic

from domain.batch import OUTPUT_300K_BETA, OUTPUT_300K_MODELS
from infrastructure.local_storage.batch_store import ensure_store_dir, save_batch_meta

_NOOP = lambda *a, **k: None  # noqa: E731


class BatchCoder:
    """Claude Batch API client."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-5",
                 use_300k_output: bool = False,
                 on_warning: Callable[[str], None] = _NOOP):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model  = model
        # Opt-in per-instance rather than per-request: the beta header is
        # sent on the whole batches.create() call, so mixing 300k-output and
        # normal requests in one batch isn't meaningful — pick one per batch.
        self.use_300k_output = use_300k_output
        if use_300k_output and model not in OUTPUT_300K_MODELS:
            on_warning(
                f"{model} isn't in OUTPUT_300K_MODELS — "
                f"output-300k-2026-03-24 may not apply; proceeding anyway "
                f"since the API is the source of truth."
            )
        ensure_store_dir()

    def _create_batch(self, requests: list):
        """Submit requests as a batch, adding the 300k-output beta header
        when opted in via use_300k_output."""
        if self.use_300k_output:
            return self.client.beta.messages.batches.create(
                requests=requests, betas=[OUTPUT_300K_BETA])
        return self.client.messages.batches.create(requests=requests)

    # ── Submit ────────────────────────────────────────────────────────────

    def submit_from_jsonl(self, jsonl_path: str, system: str = None) -> str:
        """Read a JSONL file and submit as a batch. Returns batch_id."""
        import uuid
        requests = []
        with open(jsonl_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj   = json.loads(line)
                rid   = obj.get("id") or str(uuid.uuid4())[:8]
                prompt = obj.get("prompt") or obj.get("content") or str(obj)
                msgs  = obj.get("messages") or [{"role": "user", "content": prompt}]
                req   = {
                    "custom_id": rid,
                    "params": {
                        "model":      self.model,
                        "max_tokens": obj.get("max_tokens", 4096),
                        "messages":   msgs,
                    }
                }
                if system or obj.get("system"):
                    req["params"]["system"] = system or obj["system"]
                requests.append(req)

        batch = self._create_batch(requests)
        save_batch_meta(batch.id, {
            "id":          batch.id,
            "source":      jsonl_path,
            "model":       self.model,
            "count":       len(requests),
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return batch.id

    def submit_prompts(self, prompts: list, system: str = None,
                       max_tokens: int = 4096) -> str:
        """Submit a list of prompt strings as a batch."""
        requests = []
        for i, prompt in enumerate(prompts):
            req = {
                "custom_id": f"req-{i:04d}",
                "params": {
                    "model":      self.model,
                    "max_tokens": max_tokens,
                    "messages":   [{"role": "user", "content": prompt}],
                }
            }
            if system:
                req["params"]["system"] = system
            requests.append(req)

        batch = self._create_batch(requests)
        save_batch_meta(batch.id, {
            "id":          batch.id,
            "source":      "inline",
            "model":       self.model,
            "count":       len(prompts),
            "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        return batch.id

    # ── Status ────────────────────────────────────────────────────────────

    def status(self, batch_id: str) -> dict:
        batch = self.client.messages.batches.retrieve(batch_id)
        return {
            "id":           batch.id,
            "status":       batch.processing_status,
            "request_counts": batch.request_counts.model_dump()
                              if hasattr(batch.request_counts, "model_dump")
                              else vars(batch.request_counts),
            "created_at":   str(batch.created_at),
            "expires_at":   str(batch.expires_at),
        }

    # ── Results ───────────────────────────────────────────────────────────

    def results(self, batch_id: str, save_to: str = None) -> list:
        """Stream results once batch is complete. Returns list of result dicts."""
        items = []
        for result in self.client.messages.batches.results(batch_id):
            entry = {
                "custom_id": result.custom_id,
                "type":      result.result.type,
            }
            if result.result.type == "succeeded":
                msg    = result.result.message
                entry["text"] = msg.content[0].text if msg.content else ""
                entry["usage"] = {
                    "input":  msg.usage.input_tokens,
                    "output": msg.usage.output_tokens,
                }
            else:
                entry["error"] = str(result.result.error)
            items.append(entry)

        if save_to:
            Path(save_to).write_text(
                "\n".join(json.dumps(item) for item in items)
            )
        return items

    # ── Cancel / List ─────────────────────────────────────────────────────

    def cancel(self, batch_id: str) -> bool:
        self.client.messages.batches.cancel(batch_id)
        return True

    def list_batches(self, limit: int = 20) -> list:
        batches = self.client.messages.batches.list(limit=limit)
        return [
            {
                "id":     b.id,
                "status": b.processing_status,
                "counts": b.request_counts.model_dump()
                          if hasattr(b.request_counts, "model_dump")
                          else vars(b.request_counts),
                "created": str(b.created_at)[:19],
            }
            for b in batches.data
        ]

    # ── Wait for completion ───────────────────────────────────────────────

    def wait(self, batch_id: str, poll_interval: int = 15,
             max_wait: int = 3600,
             on_progress: Callable[[str, dict, int], None] = _NOOP) -> dict:
        """Poll until batch is done or max_wait seconds elapsed.
        on_progress(batch_id, status_dict, waited_seconds) fires once per
        poll — the original's live '\\r...' progress line, now a
        callback; interfaces/cli/commands/batch_commands.py reproduces
        the exact original formatting, carriage-return-in-place
        included."""
        waited = 0
        while waited < max_wait:
            s = self.status(batch_id)
            st = s.get("status", "")
            on_progress(batch_id, s, waited)
            if st in ("ended",):
                return s
            time.sleep(poll_interval)
            waited += poll_interval
        return self.status(batch_id)
