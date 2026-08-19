"""
application/agents_service.py — Use-case layer for the Agent SDK / Managed Agents
AI Model Coder CLI v1.45.0 (Clean Architecture refactor, Phase A — final module)

Same pattern as admin_service.py / compliance_service.py: plain functions,
no print(), no argparse — infrastructure.anthropic_api.agents_gateway does
the real HTTP calls, this module orchestrates it.

Two functions here have REAL orchestration logic worth centralizing (not
just thin pass-throughs), pulled out of what used to be monolithic cmd_*
bodies:

- run_managed_agent_task(): the create-agent -> create-environment ->
  (optional memory store) -> create-session -> run/outcome-loop sequence
  that used to be cmd_managed_agent_run's entire body.
- run_multiagent_review(): the specialist-fan-out -> coordinator ->
  session -> run sequence that used to be cmd_agent_review_multiagent's
  entire body. Raises ValueError on an unknown specialist name (was
  already the case before this refactor — preserved, not new behavior).

Confirmation/dry-run gating for destructive operations (memory store
delete, memory delete) deliberately STAYS in the CLI layer, matching the
convention established in compliance_commands.py: "should we ask for
confirmation" is a presentation concern, but once confirmed, the actual
delete call goes through this module the same as everything else.
"""

import json
import uuid
from typing import Optional

from domain.agents.agent_config import (
    AgentSession, SESSIONS_DIR,
    build_multiagent_config, REVIEW_SPECIALIST_PRESETS,
)
from infrastructure.anthropic_api.agents_gateway import (
    ManagedAgent, McpTunnel, ManagedAgentsClient,
)


# ── MCP tunnels ──────────────────────────────────────────────────────────

def open_mcp_tunnel(api_key: str, local_port: int, name: Optional[str] = None) -> dict:
    """Returns the McpTunnel instance's .open() result dict, plus attaches
    the tunnel object itself as result['_tunnel'] so a caller that needs
    tunnel.public_url / tunnel.tunnel_id after a successful open doesn't
    have to reconstruct a second McpTunnel."""
    tunnel = McpTunnel(api_key)
    result = tunnel.open(local_port, name=name)
    result = dict(result)
    result["_tunnel"] = tunnel
    return result


# ── Managed Agent orchestration (the "one convenience command" path) ────

def run_managed_agent_task(task: str, api_key: str, model: str = "claude-opus-4-8",
                           memory_store: Optional[str] = None,
                           outcome_description: Optional[str] = None,
                           outcome_rubric: Optional[str] = None,
                           outcome_rubric_file_id: Optional[str] = None,
                           outcome_max_iterations: int = 3,
                           vault_id: Optional[str] = None,
                           agent_overrides: Optional[dict] = None,
                           stream_deltas: bool = False,
                           budget_usd_cents: Optional[int] = None,
                           on_step: Optional[callable] = None) -> dict:
    """Create a throwaway agent + environment + (optional) session and
    run one task or outcome-loop to completion. `on_step(event, data)` is
    an optional callback for presentation-layer progress messages (event
    in "agent_created", "env_created", "memory_store_created",
    "session_created", and — when stream_deltas is True — "delta" with
    data={"text": ...} for each live text chunk from the gateway's
    on_delta) — kept optional so this stays callable headlessly (e.g.
    from a future Web job) without a CLI printer attached."""
    def _step(event, **data):
        if on_step:
            on_step(event, data)

    def _delta(text):
        _step("delta", text=text)

    mac = ManagedAgentsClient(api_key)
    agent = mac.create_agent(name=f"ai-coder-task-{uuid.uuid4().hex[:8]}", model=model)
    _step("agent_created", agent=agent)
    env = mac.create_environment(name=f"ai-coder-env-{uuid.uuid4().hex[:8]}")
    _step("env_created", env=env)

    store_id = None
    if memory_store:
        store = mac.create_memory_store(name=memory_store)
        store_id = store["id"]
        _step("memory_store_created", name=memory_store, store_id=store_id)

    title = (outcome_description or task)[:60]
    vault_ids = [vault_id] if vault_id else None
    sess = mac.create_session(agent["id"], env["id"], title=title, memory_store_id=store_id,
                              vault_ids=vault_ids, agent_overrides=agent_overrides,
                              budget_usd_cents=budget_usd_cents)
    _step("session_created", session=sess, budget_usd_cents=budget_usd_cents)

    if outcome_description and (outcome_rubric or outcome_rubric_file_id):
        mac.define_outcome(sess["id"], outcome_description,
                           rubric_text=outcome_rubric,
                           rubric_file_id=outcome_rubric_file_id,
                           max_iterations=outcome_max_iterations)
        result = mac.wait_for_outcome(sess["id"], stream_deltas=stream_deltas, on_delta=_delta)
        result["_session"] = sess
        result["_mode"] = "outcome"
        return result

    result = mac.run_task(sess["id"], task, stream_deltas=stream_deltas, on_delta=_delta)
    result["_session"] = sess
    result["_mode"] = "task"
    return result


# ── Memory stores & memories ─────────────────────────────────────────────

def create_memory_store(api_key: str, name: str) -> dict:
    return ManagedAgentsClient(api_key).create_memory_store(name=name)


def list_memories(api_key: str, memory_store_id: str, path_prefix: Optional[str] = None,
                  depth: Optional[int] = None, limit: int = 50) -> dict:
    return ManagedAgentsClient(api_key).list_memories(
        memory_store_id, path_prefix=path_prefix, depth=depth, limit=limit)


def list_memory_stores(api_key: str, include_archived: bool = False) -> dict:
    return ManagedAgentsClient(api_key).list_memory_stores(include_archived=include_archived)


def archive_memory_store(api_key: str, memory_store_id: str) -> dict:
    return ManagedAgentsClient(api_key).archive_memory_store(memory_store_id)


def delete_memory_store(api_key: str, memory_store_id: str) -> dict:
    return ManagedAgentsClient(api_key).delete_memory_store(memory_store_id)


def get_memory(api_key: str, memory_store_id: str, memory_id: str) -> dict:
    return ManagedAgentsClient(api_key).get_memory(memory_store_id, memory_id)


def create_memory(api_key: str, memory_store_id: str, path: str, content: str) -> dict:
    return ManagedAgentsClient(api_key).create_memory(memory_store_id, path=path, content=content)


def update_memory(api_key: str, memory_store_id: str, memory_id: str,
                  content: Optional[str] = None, path: Optional[str] = None) -> dict:
    return ManagedAgentsClient(api_key).update_memory(
        memory_store_id, memory_id, content=content, path=path)


def delete_memory(api_key: str, memory_store_id: str, memory_id: str) -> dict:
    return ManagedAgentsClient(api_key).delete_memory(memory_store_id, memory_id)


# ── Vaults & credentials ─────────────────────────────────────────────────

def create_vault(api_key: str, display_name: str, external_user_id: Optional[str] = None) -> dict:
    return ManagedAgentsClient(api_key).create_vault(
        display_name=display_name, external_user_id=external_user_id)


def add_vault_credential(api_key: str, vault_id: str, credential_type: str,
                         mcp_server_url: Optional[str] = None,
                         secret_name: Optional[str] = None,
                         secret_value: str = "",
                         allowed_domains: Optional[list] = None,
                         injection_location: Optional[str] = None) -> dict:
    return ManagedAgentsClient(api_key).add_credential(
        vault_id, credential_type, mcp_server_url=mcp_server_url,
        secret_name=secret_name, secret_value=secret_value,
        allowed_domains=allowed_domains, injection_location=injection_location)


def list_vaults(api_key: str) -> list:
    return ManagedAgentsClient(api_key).list_vaults()


# ── Dreaming (research preview) ──────────────────────────────────────────

def create_dream(api_key: str, store_id: str, model: str = "claude-opus-4-8",
                 session_ids: Optional[list] = None, instructions: Optional[str] = None) -> dict:
    return ManagedAgentsClient(api_key).create_dream(
        store_id, session_ids=session_ids, model=model, instructions=instructions)


def get_dream(api_key: str, dream_id: str) -> dict:
    return ManagedAgentsClient(api_key).get_dream(dream_id)


def list_dreams(api_key: str, include_archived: bool = False,
                limit: int = 20, page: Optional[str] = None) -> list:
    return ManagedAgentsClient(api_key).list_dreams(
        include_archived=include_archived, limit=limit, page=page)


def cancel_dream(api_key: str, dream_id: str) -> dict:
    return ManagedAgentsClient(api_key).cancel_dream(dream_id)


def archive_dream(api_key: str, dream_id: str) -> dict:
    return ManagedAgentsClient(api_key).archive_dream(dream_id)


# ── Scheduled deployments ────────────────────────────────────────────────

def create_scheduled_deployment(api_key: str, agent_id: str, environment_id: str,
                                cron_expression: str, timezone: str = "UTC",
                                task: str = "") -> dict:
    return ManagedAgentsClient(api_key).create_scheduled_deployment(
        agent_id, environment_id, cron_expression, timezone=timezone, task=task)


def list_scheduled_deployments(api_key: str) -> list:
    return ManagedAgentsClient(api_key).list_scheduled_deployments()


def cancel_scheduled_deployment(api_key: str, deployment_id: str) -> dict:
    return ManagedAgentsClient(api_key).cancel_scheduled_deployment(deployment_id)


# ── Self-hosted environments ──────────────────────────────────────────────

def create_self_hosted_environment(api_key: str, name: str) -> dict:
    return ManagedAgentsClient(api_key).create_environment(name=name, env_type="self_hosted")


def get_environment_work_stats(api_key: str, environment_id: str) -> dict:
    return ManagedAgentsClient(api_key).get_environment_work_stats(environment_id)


# ── Webhooks ──────────────────────────────────────────────────────────────

def register_agent_webhook(api_key: str, url: str, events: Optional[list] = None) -> dict:
    return ManagedAgentsClient(api_key).register_webhook(url, event_types=events)


# ── Agents (CRUD) ─────────────────────────────────────────────────────────

def create_agent(api_key: str, name: str, model: str = "claude-opus-4-8",
                 system: str = "You are a helpful coding assistant.",
                 effort: Optional[str] = None, inference_geo: Optional[str] = None) -> dict:
    return ManagedAgentsClient(api_key).create_agent(
        name, model=model, system=system, effort=effort, inference_geo=inference_geo)


def get_agent(api_key: str, agent_id: str, version: Optional[int] = None) -> dict:
    return ManagedAgentsClient(api_key).get_agent(agent_id, version=version)


def list_agents(api_key: str, limit: int = 50) -> dict:
    return ManagedAgentsClient(api_key).list_agents(limit=limit)


def update_agent(api_key: str, agent_id: str, name: Optional[str] = None,
                 model: Optional[str] = None, effort: Optional[str] = None,
                 system: Optional[str] = None, version: Optional[int] = None,
                 inference_geo: Optional[str] = None) -> dict:
    return ManagedAgentsClient(api_key).update_agent(
        agent_id, name=name, model=model, effort=effort,
        system=system, version=version, inference_geo=inference_geo)


# ── Multiagent code review orchestration ─────────────────────────────────

def run_multiagent_review(path: str, specialists: list, api_key: str,
                          model: str = "claude-opus-4-8",
                          on_step: Optional[callable] = None) -> dict:
    """Fan out named specialist reviewers (see REVIEW_SPECIALIST_PRESETS)
    as parallel subagents sharing one sandbox + event stream under a
    coordinator agent, run the review, return the coordinator's combined
    report. Raises ValueError for any name not in REVIEW_SPECIALIST_PRESETS
    (unchanged behavior from before this refactor)."""
    unknown = [s for s in specialists if s not in REVIEW_SPECIALIST_PRESETS]
    if unknown:
        raise ValueError(
            f"Unknown specialist(s) {unknown}: choose from "
            f"{sorted(REVIEW_SPECIALIST_PRESETS)}"
        )

    def _step(event, **data):
        if on_step:
            on_step(event, data)

    def _delta(text):
        _step("delta", text=text)

    mac = ManagedAgentsClient(api_key)
    specialist_ids = []
    for name in specialists:
        agent = mac.create_agent(
            name=f"review-{name}-{uuid.uuid4().hex[:8]}", model=model,
            system=REVIEW_SPECIALIST_PRESETS[name],
        )
        specialist_ids.append(agent["id"])
        _step("specialist_created", name=name, agent=agent)

    coordinator_system = (
        "You are the lead reviewer coordinating specialist subagents "
        f"({', '.join(specialists)}) that all share this sandbox's "
        "filesystem. Delegate the checked-out codebase to each specialist, "
        "wait for their findings, then synthesize one combined report "
        "referencing all of them, organized by severity."
    )
    coordinator = mac.create_agent(
        name=f"review-coordinator-{uuid.uuid4().hex[:8]}", model=model,
        system=coordinator_system,
        multiagent=build_multiagent_config(specialist_ids),
    )
    env = mac.create_environment(name=f"ai-coder-review-env-{uuid.uuid4().hex[:8]}")
    sess = mac.create_session(coordinator["id"], env["id"],
                              title=f"multiagent review: {path}"[:60])
    _step("session_created", session=sess)

    task = (
        f"Review the codebase checked out at {path}. Delegate to the "
        f"{', '.join(specialists)} specialist(s), then synthesize one "
        "combined report referencing all of their findings."
    )
    result = mac.run_task(sess["id"], task, on_delta=_delta)
    result["_session"] = sess
    return result


def upload_outcome_rubric(api_key: str, file_path: str, model: str) -> dict:
    """Upload a local rubric markdown file via the Files API (a different
    bounded context, claude_files.py — not yet migrated to
    infrastructure/, imported directly here as a deliberate cross-context
    call until that module's own migration)."""
    from claude_files import FilesAPI
    fa = FilesAPI(api_key=api_key, model=model)
    return fa.upload(file_path)


# ── Local (non-Managed-Agents) chat/orchestrate + local session files ───

def local_agent_chat(prompt: str, api_key: str, model: str,
                     session_id: Optional[str] = None, new: bool = False) -> dict:
    """Returns {'session': AgentSession, 'result': str, 'status': str}
    where status is one of 'resumed' (loaded an existing session_id),
    'created_with_id' (session_id given but not found on disk — a fresh
    session using that id), or 'created_new' (no session_id, or new=True).
    Uses the LOCAL ManagedAgent/AgentSession loop, not the real Managed
    Agents API — see agents_gateway.py's ManagedAgent docstring for that
    distinction."""
    if session_id and not new:
        try:
            session = AgentSession.load(session_id)
            status = "resumed"
        except FileNotFoundError:
            session = AgentSession(session_id=session_id)
            status = "created_with_id"
    else:
        session = AgentSession()
        status = "created_new"

    agent = ManagedAgent(api_key=api_key, model=model)
    result = agent.chat(prompt, session)
    return {"session": session, "result": result, "status": status}


def local_agent_orchestrate(goal: str, api_key: str, model: str,
                            session_id: Optional[str] = None,
                            on_step: Optional[callable] = None) -> dict:
    """`on_step(event, data)` is an optional callback for presentation-layer
    progress messages (event in "orchestrating", "decomposed", "step_start"
    — see ManagedAgent.orchestrate()'s own docstring for each event's data
    shape) — kept optional so this stays callable headlessly, same
    convention as run_managed_agent_task()'s on_step above."""
    def _step(event, data):
        if on_step:
            on_step(event, data)

    session = AgentSession(session_id=session_id) if session_id else AgentSession()
    agent = ManagedAgent(api_key=api_key, model=model)
    result = agent.orchestrate(goal, session, on_step=_step)
    result["_session"] = session
    return result


def list_local_sessions(max_results: int = 20) -> list:
    """Parsed dicts from the last `max_results` local session files under
    SESSIONS_DIR, newest last (matches the original glob-sort order)."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    sessions = sorted(SESSIONS_DIR.glob("*.json"))
    parsed = []
    for sf in sessions[-max_results:]:
        try:
            parsed.append(json.loads(sf.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return parsed


# ── Managed Agents sessions & budgets (v1.39.0) ──────────────────────────

def get_agent_session(api_key: str, session_id: str) -> dict:
    return ManagedAgentsClient(api_key).get_session(session_id)


def set_session_budget(api_key: str, session_id: str, usd_cents: int) -> dict:
    return ManagedAgentsClient(api_key).update_session_budget(
        session_id, budget_usd_cents=usd_cents)


def remove_session_budget(api_key: str, session_id: str) -> dict:
    return ManagedAgentsClient(api_key).update_session_budget(
        session_id, budget_usd_cents=None)