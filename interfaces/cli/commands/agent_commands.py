"""
# mypy: ignore-errors
interfaces/cli/commands/agent_commands.py — CLI presentation for the Agent SDK / Managed Agents
AI Model Coder CLI v1.45.0 (Clean Architecture refactor, Phase A complete)

Presentation layer only: every cmd_* function formats and print()s output.
All actual HTTP calls / orchestration now go through
application/agents_service.py (not the gateway directly — Phase A,
exec-planing.md, now closed for all 4 originally-migrated modules).
"""

import application.agents_service as svc
from domain.agents.agent_config import TOOL_PRESETS


def cmd_mcp_tunnel_open(api_key: str, local_port: int, name: str | None = None):
    """CLI entry: open a tunnel and print the public URL."""
    result = svc.open_mcp_tunnel(api_key, local_port, name=name)
    if result.get("error"):
        print(f"\033[91m✗ Failed to open tunnel: {result['error']}\033[0m")
        return result
    tunnel = result["_tunnel"]
    print(f"\033[92m✓ Tunnel open: {tunnel.public_url}  (id={tunnel.tunnel_id})\033[0m")
    print(
        f"  Forwarding to local port {local_port}. Use this URL with "
        f"McpServerConfig.sse()/http() as an mcp_servers entry."
    )
    return result


def cmd_managed_agent_run(
    task: str,
    api_key: str,
    model: str = "claude-opus-4-8",
    memory_store: str | None = None,
    outcome_description: str | None = None,
    outcome_rubric: str | None = None,
    outcome_rubric_file_id: str | None = None,
    outcome_max_iterations: int = 3,
    vault_id: str | None = None,
    agent_overrides: dict | None = None,
    stream_deltas: bool = False,
    budget_usd_cents: int | None = None,
):
    """End-to-end convenience: create a throwaway agent + environment +
    session, run one task, print the result. See
    application.agents_service.run_managed_agent_task for the full
    parameter docs (outcome loops, vaults, agent_overrides, streaming,
    budgets) — unchanged from before this refactor, just relocated."""
    print("\033[94mℹ Creating Managed Agent, environment, and session…\033[0m")

    def on_step(event, data):
        if event == "memory_store_created":
            print(f"\033[94mℹ memory store '{data['name']}' -> {data['store_id']}\033[0m")
        elif event == "session_created":
            print(f"\033[92m✓ session {data['session']['id']}\033[0m — running task…\n")
            if data.get("budget_usd_cents") is not None:
                print(f"\033[90m[session budget: ${data['budget_usd_cents'] / 100:.2f} USD]\033[0m")
        elif event == "delta":
            print(data["text"], end="", flush=True)

    result = svc.run_managed_agent_task(
        task,
        api_key,
        model=model,
        memory_store=memory_store,
        outcome_description=outcome_description,
        outcome_rubric=outcome_rubric,
        outcome_rubric_file_id=outcome_rubric_file_id,
        outcome_max_iterations=outcome_max_iterations,
        vault_id=vault_id,
        agent_overrides=agent_overrides,
        stream_deltas=stream_deltas,
        budget_usd_cents=budget_usd_cents,
        on_step=on_step,
    )

    if result.get("_mode") == "outcome":
        print(result["text"])
        print(f"\n\033[90m[outcome result: {result['result']}]\033[0m")
    else:
        print(result["text"])
        if result.get("tool_calls"):
            print(f"\n\033[90m[tools used: {', '.join(t['name'] for t in result['tool_calls'])}]\033[0m")
    return result


def cmd_agent_memory_store_create(name: str, api_key: str) -> dict:
    """Standalone helper: create a Managed Agents memory store without
    also spinning up an agent/environment/session, so it can be created
    once and reused across many `--agent-managed-run` invocations via
    `--agent-memory-store`."""
    store = svc.create_memory_store(api_key, name)
    print(f"\033[92m✓ memory store created\033[0m  id={store['id']}  name={store['name']}")
    return store


def cmd_agent_memory_list(
    memory_store_id: str,
    api_key: str,
    path_prefix: str | None = None,
    depth: int | None = None,
    limit: int = 50,
) -> dict:
    """List the memory entries inside a memory store (v1.24.0)."""
    result = svc.list_memories(api_key, memory_store_id, path_prefix=path_prefix, depth=depth, limit=limit)
    raw = result["raw"]
    entries = raw.get("data", []) if isinstance(raw, dict) else list(raw)
    print(
        f"\n\033[94mMemories in {memory_store_id}\033[0m"
        f"{f' (path_prefix={path_prefix!r})' if path_prefix else ''}\n"
    )
    for entry in entries:
        path = entry.get("path", "?") if isinstance(entry, dict) else getattr(entry, "path", "?")
        print(f"  {path}")
    if not entries:
        print("  (no memories found)")
    print()
    return result


def cmd_agent_memory_stores_list(api_key: str, include_archived: bool = False) -> dict:
    """List memory stores in the workspace (v1.27.0)."""
    result = svc.list_memory_stores(api_key, include_archived=include_archived)
    raw = result["raw"]
    entries = raw.get("data", []) if isinstance(raw, dict) else list(raw)
    print(f"\n\033[94mMemory stores\033[0m{' (including archived)' if include_archived else ''}\n")
    for entry in entries:
        _entry = entry
        get = (
            (lambda k, d="?", e=_entry: e.get(k, d))
            if isinstance(entry, dict)
            else (lambda k, d="?", e=_entry: getattr(e, k, d))
        )
        print(f"  {get('id')}  {get('name')}" f"{'  [archived]' if get('archived', False) else ''}")
    if not entries:
        print("  (no memory stores found)")
    print()
    return result


def cmd_agent_memory_store_archive(memory_store_id: str, api_key: str) -> dict:
    """Archive a memory store (v1.27.0) — one-way, no unarchive."""
    result = svc.archive_memory_store(api_key, memory_store_id)
    print(f"\033[92m✓ memory store archived\033[0m  id={memory_store_id}")
    return result


def cmd_agent_memory_store_delete(memory_store_id: str, api_key: str, confirm: bool = False) -> dict | None:
    """Permanently delete a memory store and everything in it (v1.27.0).
    Requires --agent-memory-store-delete-yes (confirm=True) — dry-run by
    default."""
    if not confirm:
        print(
            f"\033[93m[DRY RUN]\033[0m would permanently delete memory store "
            f"{memory_store_id} and all memories/versions in it. "
            f"Re-run with --agent-memory-store-delete-yes to actually delete."
        )
        return None
    result = svc.delete_memory_store(api_key, memory_store_id)
    print(f"\033[92m✓ memory store deleted\033[0m  id={memory_store_id}")
    return result


def cmd_agent_memory_get(memory_store_id: str, memory_id: str, api_key: str) -> dict:
    """Retrieve a single memory's full content (v1.27.0)."""
    result = svc.get_memory(api_key, memory_store_id, memory_id)
    raw = result["raw"]
    get = (
        (lambda k, d=None: raw.get(k, d)) if isinstance(raw, dict) else (lambda k, d=None: getattr(raw, k, d))
    )
    print(f"\n\033[94mMemory {memory_id}\033[0m  path={get('path')}\n")
    print(get("content", "(no content)"))
    print()
    return result


def cmd_agent_memory_create(memory_store_id: str, path: str, content: str, api_key: str) -> dict:
    """Create a memory at `path` inside a store (v1.27.0). Does not
    overwrite an existing memory at that path — use
    --agent-memory-update for that."""
    result = svc.create_memory(api_key, memory_store_id, path, content)
    print(f"\033[92m✓ memory created\033[0m  id={result['id']}  path={path}")
    return result


def cmd_agent_memory_update(
    memory_store_id: str,
    memory_id: str,
    api_key: str,
    content: str | None = None,
    path: str | None = None,
) -> dict:
    """Update an existing memory's content and/or path (v1.27.0)."""
    result = svc.update_memory(api_key, memory_store_id, memory_id, content=content, path=path)
    print(f"\033[92m✓ memory updated\033[0m  id={memory_id}")
    return result


def cmd_agent_memory_delete(
    memory_store_id: str, memory_id: str, api_key: str, confirm: bool = False
) -> dict | None:
    """Delete a single memory (v1.27.0). Requires
    --agent-memory-delete-yes (confirm=True) — dry-run by default. The
    memory's version history survives the deletion."""
    if not confirm:
        print(
            f"\033[93m[DRY RUN]\033[0m would delete memory {memory_id} from "
            f"store {memory_store_id}. Re-run with --agent-memory-delete-yes "
            f"to actually delete."
        )
        return None
    result = svc.delete_memory(api_key, memory_store_id, memory_id)
    print(f"\033[92m✓ memory deleted\033[0m  id={memory_id}")
    return result


def cmd_agent_vault_create(display_name: str, api_key: str, external_user_id: str | None = None) -> dict:
    """Create a vault (v1.21.0, public beta)."""
    vault = svc.create_vault(api_key, display_name, external_user_id=external_user_id)
    print(f"\033[92m✓ vault created\033[0m  id={vault['id']}  display_name={display_name}")
    print(
        f"  Add a credential: zcoder --agent-vault-add-credential {vault['id']} "
        f"--agent-vault-cred-type static_bearer --agent-vault-mcp-url URL --agent-vault-secret TOKEN"
    )
    return vault


def cmd_agent_vault_add_credential(
    vault_id: str,
    credential_type: str,
    api_key: str,
    mcp_server_url: str | None = None,
    secret_name: str | None = None,
    secret_value: str = "",
    allowed_domains: list | None = None,
    injection_location: str | None = None,
) -> dict:
    """Add a credential to an existing vault. Never prints secret_value —
    it's write-only."""
    cred = svc.add_vault_credential(
        api_key,
        vault_id,
        credential_type,
        mcp_server_url=mcp_server_url,
        secret_name=secret_name,
        secret_value=secret_value,
        allowed_domains=allowed_domains,
        injection_location=injection_location,
    )
    print(
        f"\033[92m✓ credential added\033[0m  id={cred['id']}  vault_id={vault_id}  " f"type={credential_type}"
    )
    return cred


def cmd_agent_vault_list(api_key: str) -> list:
    vaults = svc.list_vaults(api_key)
    for v in vaults:
        print(f"  {v['id']}  {v['display_name']}")
    if not vaults:
        print("  (no vaults found)")
    return vaults


def cmd_agent_dream(
    store_id: str,
    api_key: str,
    model: str = "claude-opus-4-8",
    session_ids: list | None = None,
    instructions: str | None = None,
) -> dict:
    """Start a Dreaming pass over a memory store (research preview)."""
    from domain.agents.agent_config import validate_dreaming_instructions, validate_dreaming_model

    model_warning = validate_dreaming_model(model)
    if model_warning:
        print(f"\033[93m⚠ {model_warning}\033[0m")
    instructions_warning = validate_dreaming_instructions(instructions)
    if instructions_warning:
        print(f"\033[93m⚠ {instructions_warning}\033[0m")
    dream = svc.create_dream(
        api_key, store_id, model=model, session_ids=session_ids, instructions=instructions
    )
    print(f"\033[92m✓ dream started\033[0m  id={dream['id']}  status={dream['status']}")
    print(f"\033[90m  Poll: zcoder --agent-dream-get {dream['id']}\033[0m")
    return dream


def cmd_agent_dream_get(dream_id: str, api_key: str) -> dict:
    """Retrieve one dream's status and print it."""
    dream = svc.get_dream(api_key, dream_id)
    print(f"dream {dream['id']}: status={dream['status']}")
    if dream.get("output_store_id"):
        print(f"  output_store_id={dream['output_store_id']}")
    if dream.get("session_id"):
        print(f"  session_id={dream['session_id']}  (stream its events to watch the dream run)")
    usage = dream.get("usage")
    if usage:
        print(
            f"  usage: input={usage['input_tokens']} output={usage['output_tokens']} "
            f"cache_creation={usage['cache_creation_input_tokens']} "
            f"cache_read={usage['cache_read_input_tokens']}"
        )
    if dream.get("archived_at"):
        print(f"  archived_at={dream['archived_at']}")
    if dream.get("error"):
        print(f"  \033[91merror: {dream['error']}\033[0m")
    return dream


def cmd_agent_dream_list(
    api_key: str, include_archived: bool = False, limit: int = 20, page: str | None = None
) -> list:
    """List dreams, newest first."""
    dreams = svc.list_dreams(api_key, include_archived=include_archived, limit=limit, page=page)
    for d in dreams:
        print(f"  {d['id']}  status={d['status']}")
    if not dreams:
        print("  (no dreams found)")
    return dreams


def cmd_agent_dream_cancel(dream_id: str, api_key: str) -> dict:
    """Cancel a pending/running dream (v1.35.0)."""
    dream = svc.cancel_dream(api_key, dream_id)
    print(f"\033[93m⚠ dream canceled\033[0m  id={dream['id']}  status={dream['status']}")
    return dream


def cmd_agent_dream_archive(dream_id: str, api_key: str) -> dict:
    """Archive a terminal-state dream (v1.35.0)."""
    dream = svc.archive_dream(api_key, dream_id)
    print(f"\033[92m✓ dream archived\033[0m  id={dream['id']}  archived_at={dream['archived_at']}")
    return dream


def cmd_agent_schedule_create(
    agent_id: str,
    environment_id: str,
    cron_expression: str,
    api_key: str,
    timezone: str = "UTC",
    task: str = "",
) -> dict:
    """Attach a cron schedule (v1.21.0, public beta) to an existing agent + environment."""
    dep = svc.create_scheduled_deployment(
        api_key, agent_id, environment_id, cron_expression, timezone=timezone, task=task
    )
    print(
        f"\033[92m✓ scheduled deployment created\033[0m  id={dep['id']}  "
        f"cron='{cron_expression}' tz={timezone}"
    )
    return dep


def cmd_agent_schedule_list(api_key: str) -> list:
    deployments = svc.list_scheduled_deployments(api_key)
    for d in deployments:
        print(f"  {d['id']}  status={d['status']}")
    if not deployments:
        print("  (no scheduled deployments found)")
    return deployments


def cmd_agent_schedule_cancel(deployment_id: str, api_key: str) -> dict:
    dep = svc.cancel_scheduled_deployment(api_key, deployment_id)
    print(f"\033[92m✓ scheduled deployment archived\033[0m  id={dep['id']}")
    return dep


def cmd_agent_env_self_hosted_create(name: str, api_key: str) -> dict:
    """Create a self-hosted sandbox environment (public beta, v1.26.0)."""
    env = svc.create_self_hosted_environment(api_key, name)
    print(f"\033[92m✓ self-hosted environment created\033[0m  id={env['id']}")
    print("  Next steps (not done by this command):")
    print(f"    1. In the Console, open environment {env['id']} and click " f"'Generate environment key'")
    print(
        f"    2. Run a worker with ANTHROPIC_ENVIRONMENT_ID={env['id']} and "
        f"ANTHROPIC_ENVIRONMENT_KEY set — e.g. `ant beta:worker poll` or the "
        f"EnvironmentWorker SDK helper"
    )
    print(
        f"    3. Check --agent-env-work-stats {env['id']} for "
        f"workers_polling > 0 before pointing a session at it"
    )
    return env


def cmd_agent_env_work_stats(environment_id: str, api_key: str) -> dict:
    """Print the self-hosted work queue's state for `environment_id`."""
    stats = svc.get_environment_work_stats(api_key, environment_id)
    print(f"\033[94mℹ work queue stats for {environment_id}\033[0m")
    print(
        f"  depth={stats['depth']}  pending={stats['pending']}  "
        f"workers_polling={stats['workers_polling']}  "
        f"oldest_queued_at={stats['oldest_queued_at']}"
    )
    if stats["workers_polling"] == 0:
        print(
            "  \033[93m⚠ no worker has polled in the last 30s — sessions "
            "routed here will queue, not fail\033[0m"
        )
    return stats


def cmd_agent_webhook_register(url: str, api_key: str, events: list | None = None) -> dict:
    webhook = svc.register_agent_webhook(api_key, url, events=events)
    print(f"\033[92m✓ webhook registered\033[0m  id={webhook['id']}  url={url}")
    if events:
        print(f"  events: {', '.join(events)}")
    return webhook


def cmd_agent_create(
    name: str,
    api_key: str,
    model: str = "claude-opus-4-8",
    system: str = "You are a helpful coding assistant.",
    effort: str | None = None,
    inference_geo: str | None = None,
) -> dict:
    agent = svc.create_agent(
        api_key, name, model=model, system=system, effort=effort, inference_geo=inference_geo
    )
    print(
        f"\033[92m✓ agent created\033[0m  id={agent['id']}  name={name}  model={model}"
        + (f"  effort={effort}" if effort else "")
        + (f"  inference_geo={inference_geo}" if inference_geo else "")
    )
    return agent


def cmd_agent_get(agent_id: str, api_key: str, version: int | None = None) -> dict:
    agent = svc.get_agent(api_key, agent_id, version=version)
    print(f"\033[92m✓ agent\033[0m  id={agent_id}" + (f"  version={version}" if version else ""))
    print(f"  {agent['raw']}")
    return agent


def cmd_agent_list(api_key: str, limit: int = 50) -> dict:
    result = svc.list_agents(api_key, limit=limit)
    print("\033[92m✓ agents\033[0m")
    for a in result["raw"]:
        print(f"  id={getattr(a, 'id', '?')}  name={getattr(a, 'name', '?')}")
    return result


def cmd_agent_update(
    agent_id: str,
    api_key: str,
    name: str | None = None,
    model: str | None = None,
    effort: str | None = None,
    system: str | None = None,
    version: int | None = None,
    inference_geo: str | None = None,
) -> dict:
    agent = svc.update_agent(
        api_key,
        agent_id,
        name=name,
        model=model,
        effort=effort,
        system=system,
        version=version,
        inference_geo=inference_geo,
    )
    print(f"\033[92m✓ agent updated\033[0m  id={agent_id}  new_version={agent['version']}")
    return agent


def cmd_agent_review_multiagent(
    path: str, specialists: list, api_key: str, model: str = "claude-opus-4-8"
) -> dict:
    """Native Multiagent orchestration (v1.21.0): run named specialist
    code reviewers as parallel subagents sharing one sandbox filesystem
    and one event stream, with a coordinator synthesizing one report."""

    def on_step(event, data):
        if event == "specialist_created":
            print(f"  {data['name']} -> {data['agent']['id']}")
        elif event == "session_created":
            print(f"\033[92m✓ session {data['session']['id']}\033[0m — running review…\n")
        elif event == "delta":
            print(data["text"], end="", flush=True)

    print(f"\033[94mℹ Creating {len(specialists)} specialist agent(s)…\033[0m")
    result = svc.run_multiagent_review(path, specialists, api_key, model=model, on_step=on_step)
    print(result["text"])
    return result


def cmd_agent_outcome_rubric_upload(file_path: str, api_key: str, model: str) -> str:
    """Upload a local rubric markdown file once via the Files API and
    print its file_id, for reuse across --agent-outcome invocations."""
    print(f"\033[94mℹ Uploading rubric {file_path}…\033[0m")
    result = svc.upload_outcome_rubric(api_key, file_path, model)
    print(f"\033[92m✓ rubric uploaded\033[0m  file_id={result['id']}")
    print(
        f'  Reuse with: zcoder --agent-managed-run "..." --agent-outcome "..." '
        f"--agent-outcome-rubric-file {result['id']}"
    )
    return result["id"]


# ── CLI entry points (local, non-Managed-Agents chat/orchestrate) ───────


def cmd_agent_chat(prompt: str, api_key: str, model: str, session_id: str = None, new: bool = False):
    outcome = svc.local_agent_chat(prompt, api_key, model, session_id=session_id, new=new)
    session, result, status = outcome["session"], outcome["result"], outcome["status"]
    if status == "resumed":
        print(f"\033[94mℹ Resumed session: {session.name} ({len(session.history)} turns)\033[0m\n")
    elif status == "created_with_id":
        print(f"\033[94mℹ Created new session: {session.id}\033[0m\n")
    else:
        print(f"\033[94mℹ New session: {session.id}\033[0m\n")
    print(result)
    print(f"\n\033[90m[session: {session.id}  turns: {len(session.history)//2}]\033[0m")
    print(f'\033[90m  Resume: zcoder --agent-session {session.id} -p "follow-up"\033[0m')
    return result


def cmd_agent_orchestrate(goal: str, api_key: str, model: str, session_id: str = None):
    def on_step(event, data):
        if event == "orchestrating":
            print(f"\033[94mℹ Orchestrating: {data['goal'][:60]}\033[0m")
        elif event == "decomposed":
            print(f"  Decomposed into {data['step_count']} steps")
        elif event == "step_start":
            print(f"  → Step {data['step']}: {data['task'][:60]}")

    result = svc.local_agent_orchestrate(goal, api_key, model, session_id=session_id, on_step=on_step)
    print("\n\033[92m✓ Orchestration complete\033[0m\n")
    print(result["final"])
    return result


def cmd_agent_list_sessions():
    sessions = svc.list_local_sessions(max_results=20)
    if not sessions:
        print("No saved sessions.")
        return
    print(f"\n{'ID':<16}{'NAME':<25}{'TURNS':<8}{'UPDATED'}")
    print("─" * 60)
    for d in sessions:
        try:
            turns = len(d.get("history", [])) // 2
            print(f"{d['id']:<16}{d.get('name','')[:24]:<25}{turns:<8}{d.get('updated_at','')[:10]}")
        except Exception:
            pass


def cmd_agent_session_get(session_id: str, api_key: str) -> dict:
    """Inspect a Managed Agents session's status, stop_reason, budget,
    and consumed list cost (v1.39.0, public beta)."""
    info = svc.get_agent_session(api_key, session_id)
    print(
        f"\033[92m✓ session {session_id}\033[0m  status={info['status']}"
        + (f"  stop_reason={info['stop_reason']}" if info["stop_reason"] else "")
    )
    if info["budget"]:
        cap = info["budget"].get("max_list_cost", {}).get("amount")
        spent = info["list_cost_usd_cents"]
        cap_str = f"${int(cap) / 100:.2f}" if cap is not None else "?"
        spent_str = f"${spent / 100:.2f}" if spent is not None else "?"
        print(f"  budget: {spent_str} / {cap_str} USD")
    else:
        print("  budget: none")
    return info


def cmd_agent_session_budget_set(session_id: str, api_key: str, usd_cents: int) -> dict:
    """Replace a session's spend budget with a new cap, in whole US cents."""
    result = svc.set_session_budget(api_key, session_id, usd_cents)
    print(f"\033[92m✓ session {session_id}\033[0m budget set to ${usd_cents / 100:.2f} USD")
    return result


def cmd_agent_session_budget_remove(session_id: str, api_key: str) -> dict:
    """Remove a session's spend budget entirely (one-way)."""
    result = svc.remove_session_budget(api_key, session_id)
    print(f"\033[92m✓ session {session_id}\033[0m budget removed")
    return result


def cmd_list_tool_presets():
    print("\nAgent tool presets:")
    for name, tools in TOOL_PRESETS.items():
        print(f"  {name:<14} — {', '.join(tools)}")
