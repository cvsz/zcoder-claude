# Contributing

## Setup

```bash
git clone <repo>
cd zcoder
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Before opening a PR

```bash
ruff check .
black --check .
mypy . --ignore-missing-imports   # best-effort; not all modules are fully typed yet
pytest
```

CI (`.github/workflows/ci.yml`) runs pytest, pyflakes, ruff, black, and
mypy on Python 3.14. A PR won't merge if any of these fail.

## Conventions

- **New API calls that hit the network** belong in an
  `infrastructure/` gateway and should raise `exceptions.py`
  types (`TransientAPIError`, `RateLimitError`, `APIError`, ...), not bare
  `Exception`, so `retry()` can classify them correctly. Wrap
  the call in `@retry(...)` from
  `infrastructure.anthropic_api.http_client` rather than hand-rolling a retry
  loop. **Exception:** the admin and compliance gateways
  (`infrastructure/anthropic_api/admin_gateway.py`,
  `compliance_gateway.py`)
  implement their own retry/backoff directly, because Anthropic documents
  a specific retry contract for those endpoint families independently of
  the general API's; reusing `http_client.retry()` there would couple two
  contracts that happen to look similar today but aren't guaranteed to
  stay that way. Don't follow this as a general pattern — it's specific
  to those two modules.
- **New user-supplied paths/names** go through `security.safe_resolve()` /
  `security.validate_name()` before touching the filesystem.
- **New logging** uses `logging_config.get_logger(__name__)`, not bare
  `print()` for anything other than direct CLI output the user asked for.
  Structured fields go in `extra={...}`, not string-interpolated into the
  message (keeps JSON log output queryable).
- **New tests** mirror the layer of the code they cover —
  `tests/unit/domain/` and `tests/unit/application/` for pure logic and
  use cases, `tests/integration/infrastructure/` for gateways/stores,
  `tests/e2e/cli/` for CLI wiring — one file per module, and must not
  make real network calls; see any existing unit test for the mocking
  pattern.
- Every module in `interfaces/cli/commands/`, `application/`, and
  `infrastructure/` carries a docstring stating its bounded context,
  what it delegates to, and (for command modules) which CLI flags it
  backs (existing convention — keep it going).

## Versioning

`CHANGELOG.md` is the source of truth for what shipped in each version;
`docs/*_upgrade_*.md` holds the detailed per-release notes for anything
non-trivial. Bump `VERSION` in `version.py` (the single source the
parser, dispatcher, TUI, and webapp all read) and `version` in
`pyproject.toml` together.
