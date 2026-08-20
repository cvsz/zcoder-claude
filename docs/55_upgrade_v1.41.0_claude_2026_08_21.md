# v1.41.0 — Claude upgrade alignment (2026-08-21)

This implementation pass re-audited first-party Anthropic documentation and
implemented the newly confirmed gaps without weakening the existing Clean
Architecture or security boundaries.

## First-party sources revalidated

- Claude Platform Pricing: Sonnet 5 is $2/$10 per MTok through 2026-08-31 and $3/$15 starting 2026-09-01.
- Sonnet 5 migration guide: same pricing boundary plus adaptive-thinking and non-default-sampling restrictions.
- Agent Skills API: `/v1/skills` CRUD plus `/v1/skills/{skill_id}/versions` lifecycle.
- Managed Agents GitHub resources: `resources[].type=github_repository`, optional branch/commit checkout, token never echoed, runtime token rotation via session resources API.
- Claude Enterprise Analytics API: separate Analytics API key and `/v1/organizations/analytics/*` endpoint family; decimal-string fractional-cent amounts; query-bound cursors.

## Implemented

### P0 — Sonnet 5 date-effective pricing

`domain/models/catalog.py` now models the documented pricing transition with
`sonnet5_price(as_of=...)`; `get_price()` and `estimate_cost_usd()` accept an
optional effective date for deterministic historical/boundary tests.  The
runtime `PRICE` view is initialized from the price in effect on process start.

Regression coverage: `tests/unit/domain/test_model_pricing_schedule.py` pins
2026-08-30, 2026-08-31 and 2026-09-01 plus inference-geo composition.

### P1 — Agent Skills management and validation foundation

- `domain/skills.py`: SKILL.md frontmatter parsing, `allowed-tools`, package-layout validation and traversal rejection.
- `infrastructure/anthropic_api/skills_management_gateway.py`: create/list/retrieve/delete skills plus create/list/retrieve/download/delete versions through the official SDK beta surface.
- `tests/unit/domain/test_skills.py`: manifest and package security regressions.

This is intentionally separated from the pre-existing `claude_skills_api.py`
Messages/container execution path so Phase D Context #9 can compose both
surfaces through `application/platform_service.py` instead of expanding the
legacy mixed-concern module.

### P1 — Managed Agents GitHub repository session resources

- `domain/agents/session_resources.py`: validated GitHub repository resource,
  branch/commit checkout, safe credential-redacted representation.
- `infrastructure/anthropic_api/managed_session_resources_gateway.py`: create
  sessions with repository resources, list/retrieve resources, rotate GitHub
  authorization tokens, delete resources.
- `tests/unit/domain/test_managed_session_resources.py`: token redaction and
  validation coverage.

Security invariant: `authorization_token` appears only in the outbound API
payload and never in returned/safe dictionaries.

### P1 — Claude Enterprise Analytics foundation

- `domain/enterprise_analytics.py`: query validation plus exact Decimal
  conversion for fractional-cent amount fields.
- `infrastructure/anthropic_api/enterprise_analytics_gateway.py`: users,
  summaries, chat projects, skills, connectors, plugins, artifacts, cost and
  per-user cost endpoints.
- `tests/unit/domain/test_enterprise_analytics.py`: decimal and query-contract
  coverage.

The gateway deliberately does not reuse the Admin API client: Anthropic states
that Analytics API keys and Admin API keys are not interchangeable.

## Integration status / next bounded work

The implementation primitives above are intentionally additive on the
`upgrade/claude-2026-08-21` branch.  The remaining bounded integration work is:

1. Fold Skills management/validation into Phase D Context #9's planned
   `application/platform_service.py` and `interfaces/cli/commands/platform_commands.py`.
2. Compose GitHub repository resources into the already-migrated Agents
   application/interface layers while preserving the legacy `memory_store_id`
   create-session path.
3. Add an Enterprise Analytics application/interface surface during Phase F
   enterprise hardening (do not conflate it with Admin API auth).
4. Update `exec-planning.md` checkboxes/status only after those application/
   interface wiring steps and the full repository gates pass.

## Required verification before merge

- `python -m pytest -q`
- `python -m pyflakes domain infrastructure application interfaces claude_*.py`
- `python main.py --help` and byte/flag reachability checks for any newly wired CLI commands
- `git diff --check`
- existing CodeQL/security/dependency gates unchanged
- live API smoke tests only with non-production credentials and no secret output

No claim of Phase D Context #9 completion is made by this document.
