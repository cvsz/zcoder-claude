"""
interfaces/cli/commands/batch_commands.py — CLI presentation for the
Messages Batch API bounded context
AI Model Coder CLI v1.52.0 (Clean Architecture refactor, Phase C, Context #4)

Only print() lives here — all real work delegated to
application/batch_service.py. Extracted 2026-08-18 from claude_batch.py's
cmd_batch_submit, cmd_batch_status, cmd_batch_results, cmd_batch_list,
cmd_batch_cancel, cmd_batch_generate.

Reproduces two print()s that used to be buried inside BatchCoder
(infrastructure/anthropic_api/batch_gateway.py's __init__ and wait()):
the OUTPUT_300K_MODELS eligibility warning (_on_warning, passed as
on_warning=) and the live '\\r...end=""' polling progress line
(_on_progress, passed as on_progress=). wait()'s original always
printed exactly one trailing bare newline right before returning,
regardless of which internal branch (batch ended vs. max_wait elapsed)
it took — reproduced here as an unconditional `print()` immediately
after every `service.wait_for_batch(...)` call, rather than trying to
signal "this was the last poll" through the callback itself.
"""

from application import batch_service as service

__all__ = [
    "cmd_batch_submit", "cmd_batch_status", "cmd_batch_results",
    "cmd_batch_list", "cmd_batch_cancel", "cmd_batch_generate",
]


def _on_warning(msg: str):
    print(f"\033[93m⚠ {msg}\033[0m")


def _on_progress(batch_id: str, s: dict, waited: int):
    print(f"\r\033[94mℹ [{batch_id}] {s.get('status','')}  "
          f"counts={s.get('request_counts',{})}  "
          f"(waited {waited}s)\033[0m", end="", flush=True)


def cmd_batch_submit(jsonl_path: str, api_key: str, model: str, system: str = None,
                     use_300k_output: bool = False):
    print(f"\033[94mℹ Submitting batch from {jsonl_path}…\033[0m")
    bid = service.submit_from_jsonl(jsonl_path, api_key, model, system=system,
                                     use_300k_output=use_300k_output,
                                     on_warning=_on_warning)
    print(f"\033[92m✓ Batch submitted: {bid}\033[0m")
    print(f"  Check status:   ai-coder --batch-status {bid}")
    print(f"  Get results:    ai-coder --batch-results {bid}")
    return bid


def cmd_batch_status(batch_id: str, api_key: str):
    s = service.get_status(batch_id, api_key)
    print(f"\n  ID:      {s['id']}")
    print(f"  Status:  {s['status']}")
    print(f"  Counts:  {s['request_counts']}")
    print(f"  Created: {s['created_at'][:19]}")
    print(f"  Expires: {s['expires_at'][:19]}")


def cmd_batch_results(batch_id: str, api_key: str, save_to: str = None):
    items = service.get_results(batch_id, api_key, save_to=save_to)
    ok    = sum(1 for i in items if i.get("type") == "succeeded")
    print(f"\n\033[92m✓ {ok}/{len(items)} succeeded\033[0m\n")
    for item in items:
        status = "✓" if item.get("type") == "succeeded" else "✗"
        print(f"[{status}] {item['custom_id']}")
        if item.get("text"):
            preview = item["text"][:200].replace("\n", " ")
            print(f"    {preview}…" if len(item["text"]) > 200 else f"    {preview}")
        elif item.get("error"):
            print(f"    ERROR: {item['error']}")
    if save_to:
        print(f"\n\033[92m✓ Saved to {save_to}\033[0m")


def cmd_batch_list(api_key: str):
    batches = service.list_batches(api_key)
    if not batches:
        print("No batches found."); return
    print(f"\n{'ID':<30}{'STATUS':<15}{'COUNTS':<25}{'CREATED'}")
    print("─" * 85)
    for b in batches:
        counts = str(b["counts"])
        print(f"{b['id']:<30}{b['status']:<15}{counts[:24]:<25}{b['created']}")


def cmd_batch_cancel(batch_id: str, api_key: str):
    service.cancel_batch(batch_id, api_key)
    print(f"\033[92m✓ Batch {batch_id} cancelled.\033[0m")


def cmd_batch_generate(prompt_template: str, n: int, api_key: str, model: str,
                       system: str = None, wait: bool = False):
    """Generate N variants of a prompt and batch-submit them."""
    bid = service.generate_and_submit(prompt_template, n, api_key, model, system=system)
    print(f"\033[92m✓ Batch of {n} submitted: {bid}\033[0m")
    if wait:
        service.wait_for_batch(bid, api_key, on_progress=_on_progress)
        print()
        items = service.get_results(bid, api_key)
        for item in items:
            print(f"\n── {item['custom_id']} ──")
            print(item.get("text", item.get("error", "")))
