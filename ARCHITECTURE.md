# Architecture

## Overview

zcoder is a single-process Python CLI that wraps the Anthropic Messages
API, organized as a Clean Architecture codebase. There are no flat
feature modules: each feature area (files, batches, agents, RAG, tools,
...) is a bounded context sliced vertically through four layers. The
only entry points are `main.py` (CLI) and `tui.py` (terminal UI);
`main.py` is a ~20-line stub that delegates entirely to the CLI layer.
A FastAPI web console (`webapp/`) sits beside the CLI as a second
front end over the same application services.

```
   entry points        interfaces/            application/         domain/
┌────────────────────────────────┐   ┌──────────────────────┐   ┌──────────────┐
│ main.py ─► cli/parser.py       │   │ *_service.py          │   │ pure data +  │
│            cli/dispatcher.py   │──►│ (use cases, one per   │──►│ logic, no    │
│ tui.py (TUI)                   │   │  bounded context;     │   │ I/O, no      │
│ webapp/backend/server.py       │   │  orchestration only)  │   │ printing     │
│   (FastAPI calls services)     │   └──────────┬───────────┘   └──────────────┘
└────────────────────────────────┘              │                      ▲
                                                │ calls                │ implements
                                                ▼                      │
                                   ┌──────────────────────────────────────┐
                                   │ infrastructure/  (all I/O)           │
                                   │  anthropic_api/*_gateway.py  HTTP    │
                                   │  github_api/github_gateway.py  HTTP  │
                                   │  voyage_api/embeddings_gateway.py    │
                                   │  local_storage/*_store.py  JSON disk │
                                   └──────────────────────────────────────┘

Shared kernels used by every layer live in the `core/` package:
  core/config.py  core/exceptions.py  core/utils.py
  core/logging_config.py  core/security.py  core/health.py
plus `interfaces/cli/tui_streaming.py` (TUI streaming helpers) and
`version.py` at the root.
```

Concrete layout:

- **`domain/`** — entities, value objects, and pure business rules, one
  module per bounded context (`batch.py`, `files.py`, `sessions.py`,
  ...), plus `domain/models/catalog.py` (the model/pricing catalog),
  `domain/agents/`, and `domain/compliance/`. No imports from any other
  layer, no I/O of any kind.
- **`application/`** — one `*_service.py` use-case service per bounded
  context. Services orchestrate domain logic and infrastructure
  gateways/stores and return plain data — no `print()`, no `argparse`,
  no direct network or filesystem access of their own.
- **`infrastructure/`** — every side effect lives here, split by
  dependency: `anthropic_api/` (one `*_gateway.py` per Anthropic API
  surface), `github_api/`, `voyage_api/`, and `local_storage/` (one
  `*_store.py` per persisted resource). Gateways translate raw
  HTTP/network failures into the typed exceptions in `core.exceptions`.
- **`interfaces/cli/`** — presentation only. `parser.py` builds
  argparse, `dispatcher.py` routes to `commands/*_commands.py`; command
  modules own every `print()`/`input()` and delegate all real work to
  the matching application service.
- **`version.py`** — single source of truth for `VERSION`; the parser,
  dispatcher, TUI, and webapp all read it from there.

## The dependency rule

Dependencies point inward, and side effects stay at the edge:

1. **`domain/` depends on nothing** outside the standard library.
2. **`application/` may import `domain/`** and call infrastructure
   gateways/stores — but infrastructure depends on *domain* types, not
   the other way around (dependency inversion: services call plain
   gateway functions, they don't own transport).
3. **`interfaces/cli/` (and `tui.py`, `webapp/`) depend on
   `application/`**, never on infrastructure directly.
4. **No `print()` outside `interfaces/cli/commands/`** (and equivalent
   TUI/webapp presentation code). Application services return data;
   front ends render it.
5. **No HTTP outside `infrastructure/`.** Only gateway modules open
   sockets; everything above them works with typed exceptions and
   returned data structures.
6. **Pricing and model-catalog data live only in
   `domain/models/catalog.py`** — cost math anywhere else reads from
   there rather than duplicating numbers.

## Cross-cutting kernels

The root keeps only entry points; shared kernels live in the `core/`
package so every bounded context gets the same behavior for free
instead of re-implementing it:

- **`core/exceptions.py`** — every deliberate error is an `ZCoderError`
  subclass with a stable `error_code` and a `RETRYABLE` flag. This is
  the contract `retry()` (see below) reads to decide what to retry.
- **`infrastructure/anthropic_api/http_client.py`** — the retry and
  circuit-breaking machinery lives next to the transport it guards:
  `retry()` (exponential backoff with full jitter), `CircuitBreaker`
  (fail-fast during an outage, one breaker per downstream so a GitHub
  outage doesn't trip the Anthropic breaker), and the shared helpers
  `raise_for_http_error()` / `urlopen_json()` / `urlopen_text()`,
  which translate raw `urllib` exceptions into the `ZCoderError`
  hierarchy. All Anthropic gateways route through it. Call sites that
  fetch an arbitrary caller-supplied URL rather than one fixed
  dependency use `retry()` without a `CircuitBreaker`, since a breaker
  keyed on "this one dependency is down" means nothing when every call
  targets a different host.
- **`core/logging_config.py`** — one structured logger per module via
  `get_logger(__name__)`, a correlation ID set once per invocation,
  and automatic secret redaction on every log record.
- **`core/security.py`** — path traversal guards (`safe_resolve()`),
  name/URL validation (`validate_name()`). Anything that turns user
  input into a filesystem path goes through here rather than
  string-concatenating paths directly.
- **`core/config.py`, `core/utils.py`, `core/health.py`,
  `interfaces/cli/tui_streaming.py`** — configuration loading, small
  shared helpers, health reporting, and the streaming plumbing shared
  by the CLI and TUI front ends.
- **`version.py`** — bump `VERSION` here once; parser banner, TUI, and
  webapp all follow.

## Admin & Compliance APIs — a deliberately separate contract

`infrastructure/anthropic_api/admin_gateway.py` and
`infrastructure/anthropic_api/compliance_gateway.py` are org-level
surfaces, not model calls, and each has its own documented retry
contract (429 + retryable 5xx back off exponentially; 400/401/403/404/
409 never retry) implemented directly in the gateway rather than
reusing `http_client.retry()` — the two contracts happen to look
similar but are specified independently in Anthropic's docs, so keeping
them separate avoids a false coupling if one changes later.

Key model, since it's easy to get wrong and the failure mode is a 403,
not a crash:
- A regular API key (`sk-ant-api03-...`) — everything else in this CLI
  — cannot call either gateway.
- An **Admin API key** (`sk-ant-admin01-...`) unlocks all of
  `admin_gateway.py`, plus *only* the Activity Feed endpoint
  (`--compliance-activities`) via `compliance_gateway.py`.
- A **Compliance Access Key** (`sk-ant-api01-...`, created in claude.ai
  with specific scopes at creation time — scopes are immutable
  afterward) unlocks the rest of `compliance_gateway.py`: reading or
  hard-deleting chats, files, and projects, plus directory endpoints.
  It cannot call `admin_gateway.py`.

`compliance_gateway.py`'s destructive operations (chat/file/project
hard-delete) are permanent with no recovery window, so every use case
that deletes something is dry-run unless the caller passes `yes=True`
(`--compliance-yes` on the CLI). Pagination in both gateways only
advances its cursor after a page is *successfully* fetched, so a failed
request never silently skips data on retry.

## State & persistence

All local state is flat JSON files under the user's home directory —
`~/.zcoder-config.json` (config), `~/.zcoder/` (projects, artifacts,
files registry, sessions) — read and written exclusively by
`infrastructure/local_storage/*_store.py`. There is no database. This
keeps the tool zero-install beyond Python + `pip install -r
requirements.txt`, at the cost of no concurrent-writer safety — two CLI
invocations writing to the same project file at once can race. Not
addressed in this pass; noted here so it isn't rediscovered as a
surprise.

## Tests

Tests mirror the layers: `tests/unit/domain/` and
`tests/unit/application/` for pure logic and use cases (no I/O, fully
mocked), `tests/integration/infrastructure/` for gateways and stores
against mocked transports/temp dirs, and `tests/e2e/cli/` for
parser → dispatcher → commands wiring. CI runs pytest plus pyflakes,
ruff, black, and mypy.

## Packaging

Two ways to run this:
1. **From source**: `scripts/setup.sh`/`scripts/setup.bat` create a venv and `.env`.
2. **Standalone binary**: `scripts/build.sh`/`scripts/build.bat` + `zcoder.spec` produce
   a PyInstaller single-file executable with no local Python required.
3. **Container**: `Dockerfile` (multi-stage, non-root, healthcheck) +
   `docker-compose.yml` for anything that wants to run this as a service
   dependency rather than a local CLI. See `docs/deployment.md`.
