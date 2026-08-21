# v1.40.0 — Anthropic release gate (2026-08-14)

Ground truth: live-fetched `platform.claude.com/docs/en/release-notes/overview`
and `.../manage-claude/compliance-sessions` on 2026-08-14, not training-data
memory or the repo's own prior audit docs.

Baseline: `docs/52_upgrade_v1.39.0_managed_agents_session_budgets.md`, whose
own §7 lists what it did *not* check: Admin API, Compliance API, WIF,
Enterprise inference hooks, models-table pull. Its "sources checked" date
(2026-08-14) matches this session's date but only covered the Aug 7, 2026
release-notes entry (budgets/advisor/inference_geo/GitHub skills — already
implemented, re-confirmed clean, no changes needed). Everything below is
newer or was flagged-but-unchecked in that doc.

## Per-item disposition (every release-note entry newer than doc 52's coverage)

| Date | Item | Disposition | Action taken |
|---|---|---|---|
| Aug 11 | Compliance API — local session transcripts (`/apps/sessions/local`) | **MISSING_IMPLEMENTABLE → FIXED** | Implemented `list_local_sessions`, `get_local_session`, `get_local_session_messages`, `iterate_local_session_messages` + 3 CLI flags + 6 tests |
| Aug 11 | `anthropic-workspace-id` response header | **MISSING_IMPLEMENTABLE → FIXED** | Added `resilience.urlopen_json_with_headers()`; new `claude_response_metadata.py` module + `--whoami` CLI flag + 6 tests. Systemic root cause noted below. |
| Aug 10 | Sonnet 5 pricing: scheduled $3/$15 increase cancelled, $2/$10 now permanent | **PRICING_ONLY, program logic depends on it → FIXED** | Corrected `claude_models.py`, `claude_cost_optimizer.py`, `claude_metrics.py`, `claude_sonnet5.py` (4 files, one bug pattern) |
| Aug 7 | Managed Agents budgets / advisor / `inference_geo` / GitHub skills | **IMPLEMENTED_AND_VERIFIED** | Already correct per doc 52; re-confirmed against live docs, no changes |
| Aug 5 | Inference hooks (Enterprise beta, AI security server gate) | **PRIVATE_OR_LIMITED_PREVIEW / NOT_APPLICABLE** | Server-side org policy configured in Console against the customer's own security server; nothing in the Messages/Managed-Agents request or response shape for a CLI client to send or read. Denials surface through the Compliance Activity Feed, which `claude_compliance_api.py` already covers (`cmd_compliance_activities`). No code gap identified; flagged here so it isn't silently skipped. |
| Aug 5 | Opus 4.1 (`claude-opus-4-1-20250805`) retirement | **MODEL_DEPRECATION → FIXED** | Was still in `DEPRECATED_MODELS` with a past-due `retirement_scheduled` of 2026-08-05 — moved to `RETIRED_MODELS`. (A prior session, visible only in a shared-chat transcript, claimed this fix; it was **not** present in this uploaded zip. Re-verified live and re-applied.) |
| Aug 3 | Compliance API — remote session transcripts (`/apps/sessions/remote`) | **MISSING_IMPLEMENTABLE → FIXED** | Implemented `list_remote_sessions`, `get_remote_session_messages`, `iterate_remote_session_messages` + 3 CLI flags + 6 tests |

## Re-checked, no gaps found

- **Models API / model aliases**: `claude_models.py` MODEL_CATALOG, RETIRED_MODELS, MODEL_ID_ALIASES cross-checked against the live release notes back through the June 15 and Aug 5 retirements — no other stale entries found.
- **Beta headers**: `managed-agents-2026-04-01`, `agent-memory-2026-07-22`, `advisor-tool-2026-03-01` usages in `claude_agents_sdk.py`/`claude_advisor.py` spot-checked against the current header list — no stale headers found (the `agent-memory-2026-07-22` migration from doc 52 is correctly in place).
- **Agent SDK / Managed Agents**: no new SDK-shape items in the Aug 3–11 window beyond what's covered above.
- **Claude Code**: no Claude API-surface changes in this window that ZCoder (a `/v1/messages`-based CLI, not a Claude Code wrapper) needs to react to.
- **Admin API**: no new endpoints in this window; existing `claude_admin_api.py` User Management coverage (v1.38.0) unaffected.
- **Data residency / ZDR**: `inference_geo` gating unchanged this window; local-session Compliance endpoints correctly documented as excluding ZDR sessions (I did not add client-side ZDR filtering — the API itself 404s/excludes them, so there's nothing to duplicate client-side).

## Systemic root cause flagged (not fully remediated — scoping note)

`resilience.urlopen_json()` discards HTTP response headers everywhere it's
used (~30 call sites across `claude_*.py`), which is *why* the
`anthropic-workspace-id` header (and the older `anthropic-organization-id`,
live since 2025-02-10) was unreachable from any existing code path, not just
missing from one module. I added the header-preserving variant and one
concrete consumer (`--whoami`) rather than retrofitting all ~30 call sites:
that's a much larger, higher-regression-risk change that deserves its own
audit pass with its own test coverage per call site, not a bundled fix
inside a release-gate pass. Flagging explicitly so it isn't mistaken for
"done everywhere."

## Test weaknesses found and fixed

- `tests/test_claude_models_deprecation.py` encoded the pre-retirement state
  of `claude-opus-4-1-20250805` as correct (asserted `check_deprecated(...)`
  returned a record and that `cmd_check_deprecated` reported it as
  "deprecated" — both now false after the move to `RETIRED_MODELS`). Rewrote
  6 of 8 tests in that file to assert the retired state instead of deleting
  coverage.
- `tests/test_claude_sonnet5.py` had two tests (`..._on_promo_end_date_itself`,
  `..._well_before_end_date`) that hard-asserted `promo_active is True` — now
  structurally false since there's no more promo/standard split. Replaced
  with a single parametrized-style flat-rate assertion across three dates
  spanning the old cliff-edge.
- `claude_cost_optimizer.py` and `claude_metrics.py` — confirmed **no test
  file existed for either module** as of the first pass of this gate. Both
  contained the same stale Sonnet 5 pricing bug found in `claude_sonnet5.py`
  and `claude_models.py`, and neither had a test that would have caught it.
  **Backfilled in this session**: `tests/test_claude_cost_optimizer.py` (14
  tests — pricing table, long-context surcharge, inference_geo multiplier,
  complexity routing) and `tests/test_claude_metrics.py` (12 tests —
  pricing, the v1.11.0 refusal/not_billed logic, log filtering,
  aggregation, export). Both explicitly assert the corrected $2/$10 Sonnet
  5 rate so this exact bug class can't silently regress again.

## Fixes applied — file list

- `claude_models.py` — Sonnet 5 pricing note + price; Opus 4.1 moved
  DEPRECATED→RETIRED
- `claude_cost_optimizer.py` — Sonnet 5 `PRICE` entry, `SONNET5_INTRO_PRICE`
  comment
- `claude_metrics.py` — Sonnet 5 `PRICE_TABLE` entry (third instance of the
  same bug, previously unflagged)
- `claude_sonnet5.py` — removed the now-false promo/standard cliff-edge
  logic in `current_pricing()`/`estimate_cost_usd()`/`cmd_sonnet5_info`/
  `cmd_sonnet5_cost`
- `main.py` — Sonnet 5 help text; 8 new `--compliance-*-session*` flags +
  dispatch; `--whoami` flag + dispatch
- `claude_compliance_api.py` — 7 new client methods (local + remote
  sessions), 8 new `cmd_*` CLI entry points
- `resilience.py` — new `urlopen_json_with_headers()`
- `claude_response_metadata.py` — new module (`--whoami`)
- `tests/test_claude_compliance_api.py` — 12 new tests
- `tests/test_claude_response_metadata.py` — new file, 6 tests
- `tests/test_claude_models_deprecation.py` — 6 tests rewritten for the
  retired (not deprecated) state
- `tests/test_claude_sonnet5.py` — 2 stale-cliff-edge tests replaced with 1
  flat-rate test
- `tests/test_claude_cost_optimizer.py` — new file, 14 tests (previously
  zero coverage)
- `tests/test_claude_metrics.py` — new file, 12 tests (previously zero
  coverage)
- `claude_metrics.py` — unrelated hardening: replaced deprecated
  `datetime.utcnow()` with a timezone-aware equivalent (surfaced by the new
  test run; not an Anthropic-compatibility item, fixed as a drive-by since
  it was a one-line, zero-risk change)

## Final test results

```
python -m pytest        → 572 passed, 1 warning (StarletteDeprecationWarning, unrelated pre-existing dep)
git diff --check        → repo has no .git metadata (zip extraction, no VCS history);
                           manually verified: no conflict markers, no trailing whitespace,
                           no CRLF/LF inconsistencies in any file touched this session
python main.py --help   → exits 0, all new flags present and correctly grouped
ruff check .            → 904 pre-existing style errors repo-wide (427 in the 8 files touched
                           this session — same UP037/quoted-annotation style already used
                           throughout the codebase before this pass); 0 new errors introduced
                           by this session's edits beyond matching existing style
black --check           → repo is not black-formatted (pre-existing; 2 of the files touched
                           this session "would be reformatted", consistent with every other
                           file in the tree)
mypy .                  → pyproject.toml targets Python 3.9, unsupported by the installed
                           mypy (pre-existing config issue, not introduced this session);
                           targeted run on resilience.py shows 3 "Missing return statement"
                           notes, all on functions whose control flow is guaranteed by
                           raise_for_http_error() always raising — pre-existing pattern,
                           reproduced (not introduced) by the new urlopen_json_with_headers()
```

## Coverage verdict

**Denominator**: the 7 release-note entries dated after 2026-08-07 (doc 52's
last fully-covered date) through 2026-08-11 (today's newest entry) — the
scope this release-gate prompt asked for, not the full 20-category audit
list from the earlier adversarial-review session (Admin API deep-dive, WIF,
tokenizer accounting, event streaming, etc. remain out of scope here as they
had no *new* release-note items in this window).

**7 / 7 items have an explicit, evidence-backed disposition.** 5 were real
gaps and are now fixed with tests; 1 (inference hooks) is correctly
NOT_APPLICABLE for this client; 1 (Aug 7 batch) was already correct.

## Release gate: **PASS**

No P0/P1 Anthropic compatibility defect remains open. The one explicitly
scoped-out item (retrofitting all `urlopen_json` call sites to preserve
headers) is a enhancement/hardening item, not a compatibility defect — no
existing behavior regresses without it, and the new capability is available
via the header-preserving variant for any call site that adopts it.

---

## v1.41.0 Phase F completion (2026-08-21)

This section records what happened *after* the v1.40.0 release gate passed.

**Phase F — Enterprise/production-readiness hardening** completed 2026-08-21.
All items from `exec-planning.md` §4 are now checked:

| Item | Disposition |
|---|---|
| `ruff`/`black`/`mypy` | **COMPLETE** — ruff 0 errors, black formatted, mypy 0 errors |
| mypy Python version bump | **COMPLETE** — pyproject.toml: 3.9 → 3.14 |
| CI wiring | **COMPLETE** — `.github/workflows/ci.yml` |
| `interfaces/web/` wiring | **COMPLETE** — server.py imports from dispatcher, not main |
| Dependency floor audit | **COMPLETE** — all pins verified; web deps in `webapp/requirements-web.txt` |
| Final docs pass | **COMPLETE** — this file + exec-planning.md + CHANGELOG.md updated |
| Git tag v1.41.0 | **COMPLETE** — signed tag created |

**Test suite**: 1053/1053 passing (572 at v1.40.0 baseline + 481 from Clean
Architecture migration Phases A–E).
