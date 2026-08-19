# ZCoder — Master Execution Plan: Clean Architecture Refactor to Production-Grade Release

**Status date:** 2026-08-15
**Target:** Enterprise-grade, production-ready final release
**Methodology:** Pragmatic Clean Architecture (4 layers), Strangler Fig migration, bounded-context grouping (DDD-lite, not full tactical DDD)

This document is the single source of truth for refactor progress. It is
meant to be updated as each phase completes — treat stale checkboxes here
as a bug in the document, not just the code.

---

## 0. Why this refactor, in one paragraph

ZCoder started as 67 flat files (~23,300 lines) using filename prefixes
(`claude_*.py`) as a substitute for real module boundaries. Each file mixed
three unrelated concerns — HTTP client, business/validation logic, and
CLI presentation (`print()`) — in one place. This was proven to cause real
bugs, not just be "untidy": Claude Sonnet 5's price was duplicated across
4 files and went stale in 3 of them simultaneously (2026-08-14 release-gate
audit). The fix is structural, not a one-off patch.

---

## 1. Current-state audit (ground truth, re-measured 2026-08-15)

| Metric | Value |
|---|---|
| Total original flat modules | 67 |
| Fully migrated to 4-layer architecture (shim + domain/infra/interfaces split) | **4** — Models, Admin API, Compliance API, Agent SDK |
| Remaining flat modules (still mixed 3-concerns-in-1-file) | **47**, ~12,971 lines |
| `application/` (use-case layer) coverage | **4 of 4 migrated modules — Phase A complete.** Models, Admin API, Compliance API, Agent SDK all route through `application/*_service.py`; zero `cmd_*` function instantiates a gateway/client directly |
| `main.py` | **2,413 lines, untouched.** 237 local-import dispatch points |
| `tests/` reorganized by layer | **Started, not complete.** `tests/unit/application/` has all 4 Phase A service test files; the other ~32 test files are still flat in `tests/` |
| Test suite | 646/646 passing |
| Static analysis | `pyflakes` clean across all migrated files (0 undefined names) |

### 1.1 Problems this plan must still solve

1. **No use-case layer for 3 of 4 migrated modules.** CLI commands call
   `infrastructure/anthropic_api/*_gateway.py` directly. Any future Web UI
   (`interfaces/web/`) would either re-implement this logic or import a
   CLI-presentation module to reach it. ~90 `cmd_*` functions across Admin
   API (31), Compliance API (21), Agent SDK (38) are affected.
2. **47 modules, ~13K lines, still 3-concerns-in-1-file.** Same anti-pattern
   as the original 4 — client class, business rules, and `print()` in one
   file, in some cases (`claude_code.py`, `claude_tools.py`) over 1,000
   lines each.
3. **`main.py` is a 2,413-line God File** with 237 import points. Highest
   blast-radius change in the whole codebase; deliberately sequenced last.
4. **Test suite not reorganized.** Flat `tests/test_claude_*.py` files
   don't distinguish unit (pure logic, fast) from integration (mocked HTTP)
   from e2e (CLI invocation) — a new contributor can't tell which tests are
   safe to run in a tight loop.
5. **Duplicated pricing/config risk exists in every un-migrated module**
   that touches models or costs, until each is folded into
   `domain/models/catalog.py`.

### 1.2 What is already solved (do not re-litigate)

- Single source of truth for model catalog/pricing: `domain/models/catalog.py`
- Proven, repeatable migration pattern (gateway extraction → CLI extraction
  → shim → test repointing → `pyflakes` → full suite) — used successfully
  4 times
- Known failure modes and their fixes are documented in §5 (Playbook) so
  they aren't rediscovered per-module

---

## 2. Target architecture (unchanged from prior proposal, restated for completeness)

```
zcoder/
├── domain/                     # Pure data + pure logic. Zero I/O except
│   │                            local-disk persistence entities (documented
│   │                            per-case, e.g. AgentSession).
│   ├── models/catalog.py        ✅ DONE — model catalog, pricing, lifecycle
│   ├── agents/agent_config.py   ✅ DONE — agent/session/tunnel config, validation
│   ├── compliance/               ⬜ TODO — session/transcript value objects
│   ├── billing/                  ⬜ TODO — cost/usage domain rules (from
│   │                                claude_cost_optimizer.py, claude_metrics.py)
│   └── tools/                    ⬜ TODO — tool-use schemas, structured-output
│                                    validation (from claude_tools.py, claude_structured.py)
│
├── application/                 # Use-case orchestration. Calls domain +
│   │                              infrastructure. Zero print(), zero argparse.
│   ├── models_service.py        ✅ DONE
│   ├── admin_service.py          ⬜ TODO — 31 operations
│   ├── compliance_service.py     ⬜ TODO — 21 operations
│   ├── agents_service.py         ⬜ TODO — 38 operations
│   └── (one per remaining bounded context, see §3)
│
├── infrastructure/anthropic_api/ # Real HTTP calls only.
│   ├── models_gateway.py        ✅ DONE
│   ├── admin_gateway.py         ✅ DONE
│   ├── compliance_gateway.py    ✅ DONE
│   ├── agents_gateway.py        ✅ DONE
│   ├── http_client.py           ✅ DONE (was resilience.py)
│   └── (one per remaining bounded context, see §3)
│
├── interfaces/
│   ├── cli/
│   │   ├── commands/             (4 done, ~9 more bounded contexts to add)
│   │   ├── parser.py              ⬜ TODO — argparse definitions, split from main.py
│   │   └── dispatcher.py          ⬜ TODO — routing, split from main.py
│   └── web/                       ⬜ TODO — reuses application/ layer, not yet started
│
└── tests/
    ├── unit/{domain,application}/  🟡 STARTED (1 file each)
    ├── integration/infrastructure/ ⬜ TODO
    └── e2e/cli/                    ⬜ TODO
```

Legend: ✅ done and test-verified · 🟡 started, incomplete · ⬜ not started

---

## 3. Bounded-context map for the remaining 47 modules

Grouping by business capability (DDD-lite bounded contexts) rather than
migrating files in size order — this keeps each `application/*_service.py`
cohesive instead of one giant grab-bag, and lets each context ship
independently.

| # | Bounded context | Source files (lines) | New application service | Priority |
|---|---|---|---|---|
| 1 | **Core Messaging** | `claude_live.py`(143), `claude_stream.py`(286), `claude_structured.py`(225), `claude_citations.py`(214), `claude_thinking.py`(342), `claude_tokens.py`(121) | `application/messaging_service.py` | **P0** — everything else calls this |
| 2 | **Tool Use & Retrieval** | `claude_tools.py`(1008), `claude_vision.py`(182), `claude_embeddings.py`(190), `claude_search.py`(162), `claude_rag.py`(160) | `application/tools_service.py` | P1 |
| 3 | **Agent Execution & Code** | `claude_code.py`(1436), `claude_code_exec.py`(249), `claude_hooks_perms_plan.py`(291), `claude_sandbox.py`(129), `claude_router.py`(165) | `application/code_agent_service.py` | P1 |
| 4 | **Files & Documents** | `claude_files.py`(367), `claude_powerpoint.py`(458), `claude_excel.py`(396), `claude_batch.py`(295) | `application/documents_service.py` | P1 |
| 5 | **Sessions, Memory & Cache** | `claude_sessions.py`(227), `claude_memory.py`(175), `claude_cache.py`(553) | `application/sessions_service.py` | P1 |
| 6 | **Model-specific wrappers** | `claude_fable5.py`(378), `claude_mythos5.py`(147), `claude_opus5.py`(264), `claude_haiku45.py`(203), `claude_sonnet5.py`(248, partial), `claude_response_metadata.py`(108) | fold into `application/models_service.py` (extend, don't duplicate) | **P0** — touches `domain/models/catalog.py` again |
| 7 | **Cost, Metrics & Eval** | `claude_cost_optimizer.py`(182), `claude_metrics.py`(152), `claude_observability.py`(144), `claude_eval.py`(198), `claude_evals.py`(194) | `application/observability_service.py` | P2 |
| 8 | **Dev-tool Integrations** | `claude_github.py`(186), `claude_git.py`(118), `claude_chrome.py`(218) | `application/devtools_service.py` | P2 |
| 9 | **Platform & Extensibility** | `claude_plugins.py`(631), `claude_skills_api.py`(292, **+Enterprise security scanning gap, found 2026-08-15 — see §9**), `claude_advisor.py`(241), `claude_workflow.py`(184), `claude_output_styles.py`(146), `claude_settings.py`(153), `claude_prompt_optimizer.py`(184), `claude_interactive.py`(116), `claude_wif.py`(368), `claude_research.py`(142) | `application/platform_service.py` | P2 |

**Why P0/P1/P2 in this order:** Core Messaging (#1) and Model wrappers (#6)
are load-bearing — almost every other context calls into message-sending
and model-catalog lookups, so migrating them first means later migrations
inherit a clean dependency rather than importing more flat files. #2–#5
(P1) are the next-largest, highest-traffic contexts. #7–#9 (P2) are
lower-risk, lower-traffic, and safe to defer without blocking anything else.

---

## 4. Phased roadmap

### Phase A — Close the application-layer gap for already-migrated modules (P0) ✅ **COMPLETE 2026-08-15**
- [x] `application/admin_service.py` (31 ops) + rewire `interfaces/cli/commands/admin_commands.py` — 19 new unit tests, 610/610 suite green
- [x] `application/compliance_service.py` (21 ops) + rewire `compliance_commands.py` — 15 new unit tests, 625/625 suite green
- [x] `application/agents_service.py` (38 ops) + rewire `agent_commands.py` — **done 2026-08-15**, 21 new unit tests, 646/646 suite green. Two functions (`run_managed_agent_task`, `run_multiagent_review`) carried real multi-step orchestration logic out of `cmd_*` bodies, not just thin wrappers — the highest-value extraction of the 3 Phase A modules.
- [x] Unit tests for each service (pattern: `tests/unit/application/test_<x>_service.py`) — 4 files now (models, admin, compliance, agents)
- **Exit criteria — ALL MET:** zero `cmd_*` function in these 3 modules instantiates a
  `*Gateway`/`*Client` class directly; full suite green (646/646); `pyflakes` clean across all 4 `application/*_service.py` + their CLI/shim files

### Phase B — Migrate bounded contexts #1 and #6 (P0)
- [ ] Core Messaging: gateway + service + CLI split, using the proven
  4-step pattern (§5)
- [ ] Model-specific wrappers: fold into existing `domain/models/catalog.py`
  / `application/models_service.py` rather than creating parallel files —
  this is where the original pricing-duplication bug lived, so extra care
  + an explicit "no second PRICE dict" check per file
- **Exit criteria:** same as Phase A, plus: `grep -rn "price_in\|PRICE"` across
  the 6 wrapper files finds zero locally-defined pricing tables

### Phase C — Migrate bounded contexts #2–#5 (P1)
- [ ] One context at a time, in the order listed in §3
- [ ] Each context's tests move to `tests/unit/`, `tests/integration/`,
  `tests/e2e/` as they're touched (§1.1 item 4 — done incrementally, not
  as a separate mass-move)
- **Exit criteria:** per context — full suite green, `pyflakes` clean,
  `python main.py --help` reachable, no `print()` outside `interfaces/`

### Phase D — Migrate bounded contexts #7–#9 (P2)
- [ ] Same pattern, lowest urgency — can run in parallel with Phase E if
  a second engineer/session is available, since these contexts don't block
  `main.py`'s split

### Phase E — Split `main.py` (last, by design)
- [ ] Extract `interfaces/cli/parser.py` — every `add_argument()` call,
  zero logic
- [ ] Extract `interfaces/cli/dispatcher.py` — routes parsed args to
  `interfaces/cli/commands/*`
- [ ] `main.py` shrinks to an entry-point stub (`if __name__ == "__main__":`)
- **Why last:** 237 import points touch every other module. Doing this
  before Phases A–D means every subsequent module migration would need to
  update `main.py` *and* the dispatcher separately — double the edits, double
  the regression surface. Sequencing it last means it's edited exactly once.
- **Exit criteria:** `python main.py --help` byte-identical output to
  pre-split; full suite green; every flag from every phase reachable

### Phase F — Enterprise/production-readiness hardening (final release gate)
- [ ] `ruff`/`black`/`mypy` — currently 904 pre-existing findings repo-wide
      (documented, not yet remediated); triage to zero P0/P1 findings
- [ ] `mypy` config fix — `pyproject.toml` currently targets Python 3.9,
      unsupported by installed mypy; bump to actual runtime version
- [ ] CI wiring — `pytest`, `pyflakes`, `ruff`, `git diff --check` as
      required checks on every PR (not yet automated — currently run
      manually per session)
- [ ] `interfaces/web/` — wire the existing `webapp/backend/` to
      `application/*` instead of its own logic (audit for drift first)
- [ ] Dependency floor audit — confirm `requirements.txt` pins match what
      every new `application/`/`infrastructure/` module actually needs
- [ ] Final `docs/` pass — update `docs/52_*`, `docs/53_*` and this file to
      reflect 100% migration; archive superseded architecture notes
- [ ] Tag final release, changelog entry

---

## 5. Migration playbook (proven 4 times — follow exactly, do not shortcut)

For each module in scope:

1. **Map boundaries.** `grep -n "^class \|^def "` for a first pass, but
   **do not trust it alone** — plain module-level constants (e.g.
   `COMPUTER_USE_BETA = "..."`) sit *between* class/def boundaries and will
   silently land in whichever block is textually adjacent. This caused 6
   real `NameError` bugs across the first 4 migrations. Manually inspect
   any constant assignment near a split boundary.
2. **Bucket each block:**
   - No I/O, no `print()` → `domain/`
   - Makes an HTTP call to `api.anthropic.com` → `infrastructure/anthropic_api/`
   - Calls `print()` / builds CLI-facing strings → `interfaces/cli/commands/`
   - Orchestrates domain + infrastructure with no I/O of its own,
     reusable business logic → `application/` (new step, not done for the
     first 4 modules until this plan — see Phase A)
3. **Extract programmatically**, not by hand-retyping — use exact line
   ranges via a small Python script, not manual copy-paste, to avoid
   transcription errors across large files.
4. **Write the compatibility shim** at the old file path, re-exporting
   every name the old file used to export (check `main.py` and `tests/`
   for the real consumer list — don't guess from memory).
5. **Fix test monkeypatches.** Any `monkeypatch.setattr("old_module.ClassName", ...)`
   or `monkeypatch.setattr(reloaded_module, "ClassName", ...)` must be
   repointed to the **module where the consuming function actually resolves
   that name** — patching the shim has no effect, since Python resolves
   names in the defining module's namespace, not the importer's. This bug
   appeared in all 4 migrations so far; expect it in every future one.
   **Phase A addendum (found 2026-08-15):** inserting an `application/`
   layer between an already-migrated CLI module and its gateway moves the
   name *again* — a test that was correctly repointed to
   `interfaces.cli.commands.X.GatewayClient` during the original module
   split now needs a *second* repoint to `application.X_service.GatewayClient`,
   since that's where the name is resolved once the CLI stops importing
   the gateway directly. Expect this for Compliance/Agent SDK too.
6. **Run `pyflakes` on all touched files before running tests.** It catches
   missing imports/undefined names in code paths tests don't exercise —
   found 6 real bugs across the first 4 migrations that the test suite
   alone missed.
7. **Run the full suite + `python main.py --help`.** Both must be green/exit-0
   before moving to the next module.
8. **Update this document's checkboxes and §1 metrics table.**

---

## 6. Definition of Done — production/enterprise-grade final release

A phase is not "complete" unless all of the following hold, not just "tests pass":

- [ ] No file outside `interfaces/` contains a `print()` call
- [ ] No file outside `infrastructure/anthropic_api/` makes an HTTP request
- [ ] No file outside `domain/` defines a model ID, price, or lifecycle
      (retired/deprecated) record — single source of truth holds everywhere
- [ ] Every `application/*_service.py` function is called from at least one
      `interfaces/cli/commands/*` function AND has direct unit test coverage
      (not only indirect coverage via a CLI test capturing stdout)
- [ ] `pytest`, `pyflakes` clean on every touched file
- [ ] `python main.py --help` exits 0 and is a superset of the pre-refactor
      flag list (nothing silently dropped)
- [ ] This document's checkboxes match the actual repo state

---

## 7. Risk log

| Risk | Mitigation |
|---|---|
| `main.py` split (Phase E) breaks a flag silently | Diff `--help` output before/after byte-for-byte; keep the shim files until Phase E is fully verified, not before |
| A remaining module has cross-file coupling not visible from `grep` (e.g. shared module-level state, singletons) | Check for `global` statements and module-level mutable state before splitting each file, not just class/def boundaries |
| Test monkeypatch drift (playbook step 5) missed in a rushed migration | Treat `pyflakes` + full-suite as blocking gates, not optional — this plan's playbook exists specifically because this happened repeatedly |
| Web UI (`interfaces/web/`) built against gateways instead of `application/` before Phase F | Explicit Phase F audit step to catch and fix before final release |

---

## 9. Anthropic product/API validation log

Periodic check that ZCoder's domain layer (model catalog, pricing,
lifecycle) and planned bounded contexts (§3) still match Anthropic's real
product surface. Re-run before starting any new phase.

### 2026-08-15 validation

**Method:** live web search + `platform.claude.com/docs/en/release-notes/overview`
(confirmed no new Developer Platform/API entries since the Aug 11, 2026
entry already reflected in this repo — 150 release notes total, "Latest
Aug 11, 2026" per Releasebot's tracker, cross-checked 2026-08-15).

| Area | Real-world state (2026-08-15) | ZCoder state | Verdict |
|---|---|---|---|
| Model catalog (Fable 5, Mythos 5, Opus 5, Opus 4.8/4.7/4.6/4.5, Sonnet 5/4.6/4.5, Haiku 4.5) | Confirmed as the current active model set | `domain/models/catalog.py` matches exactly | ✅ in sync |
| Opus 4.1 retirement (2026-08-05) | Confirmed retired, hard error on every request | `RETIRED_MODELS["claude-opus-4-1-20250805"]` | ✅ in sync |
| Sonnet 5 pricing ($2/$10 now permanent, $3/$15 increase cancelled) | Confirmed — Anthropic's own Aug 10 note says the increase "will not occur" | Fixed in `domain/models/catalog.py` + 3 other files (this session's earlier work) | ✅ in sync |
| `anthropic-workspace-id` response header (2026-08-11) | Confirmed real | `claude_response_metadata.py` / `--whoami` | ✅ in sync |
| Compliance API → Cowork + Claude Code, desktop/web/mobile/CLI (2026-08-03, -08-11) | Confirmed real, beta, Enterprise-only | `infrastructure/anthropic_api/compliance_gateway.py` local/remote session endpoints | ✅ in sync |
| **Enterprise skill/plugin security scanning (2026-08-07, new finding)** | Confirmed real — Enterprise plans can scan third-party Skills/plugins for malicious content on upload/edit. **Follow-up check (2026-08-15):** this is a **Console/organization-settings toggle** ("Turn on skill and plugin security scanning in organization settings" — support.claude.com), applied automatically by Anthropic's backend on every upload/edit. No dedicated API endpoint to trigger a scan or poll a scan result was found in the Skills API docs (`platform.claude.com/docs/en/agents-and-tools/agent-skills/enterprise`) — the existing `/v1/skills` upload/version endpoints are unchanged by this feature. | Not referenced in `claude_skills_api.py`/`claude_plugins.py` | ⬜→**CONSOLE_ONLY** (same disposition class as "Inference hooks" in the 2026-08-14 release-gate audit) — **no code change needed**; when Phase D reaches these files, add one doc comment noting the Console toggle exists, nothing to wire |
| Claude Cowork (Chrome side-panel merge, web/mobile expansion, Aug 2026) | Confirmed real, but a **consumer-app UI/product change**, not an API/CLI surface | N/A — ZCoder wraps the Messages/Admin/Compliance/Agent APIs, not the claude.ai consumer app | ✅ correctly out of scope, no action needed |
| Claude Science (new product line, launched 2026-06-30) | Confirmed real — research-vertical product, not a general API/model change | N/A | ✅ correctly out of scope |
| Claude Tag (team-collaboration surface) | Confirmed real, beta since 2026-06-23 | N/A — no dedicated ZCoder module; out of current bounded-context map | 🟡 note only — no action unless a future phase adds a Claude Tag integration |

**Conclusion:** domain layer and completed phases are accurate against
Anthropic's real, current product surface as of 2026-08-15. The one
candidate gap found (Enterprise skill/plugin scanning) turned out to be
Console-only with no API surface — confirmed **no code action required**,
just a documentation note deferred to Phase D.



| Date | Phase | What happened |
|---|---|---|
| 2026-08-14 | Pre-work | 4 modules migrated (Models, Admin API, Compliance API, Agent SDK); 591/591 tests; `application/models_service.py` created (Phase A partial) |
| 2026-08-15 | Planning | This document created; bounded-context map (§3) and phased roadmap (§4) established as the go-forward plan |
| 2026-08-15 | Phase A | `application/admin_service.py` created (31 ops), `admin_commands.py` rewired to call it instead of the gateway directly, 19 new unit tests, 6 test monkeypatches re-repointed (found the "second repoint" bug pattern — see §5 step 5 addendum). 610/610 suite green, `pyflakes` clean. Compliance API + Agent SDK application layers still pending. |
| 2026-08-15 | Validation | Live web-search validation of Anthropic's product/API surface against ZCoder's domain layer (§9). Model catalog, pricing, workspace-id header, and Compliance API session coverage all confirmed accurate. One candidate gap (Enterprise skill/plugin security scanning, Aug 7) investigated further and resolved as Console-only, no API surface, no code action needed. |
| 2026-08-15 | Phase A | `application/compliance_service.py` created (21 ops), `compliance_commands.py` rewired to call it instead of the gateway directly, 15 new unit tests, 7 test monkeypatches re-repointed (same "second repoint" pattern as Admin API — confirms this is now a predictable, expected step per module, not a one-off). 625/625 suite green, `pyflakes` clean. Agent SDK application layer still pending — last one in Phase A. |
| 2026-08-15 | **Phase A complete** | `application/agents_service.py` created (38 ops, largest of the 3) — including two functions (`run_managed_agent_task`, `run_multiagent_review`) with genuine multi-step orchestration logic extracted out of `cmd_*` bodies, not thin wrappers. `agent_commands.py` rewired. 38 test monkeypatches re-repointed (predicted pattern, confirmed again). Fixed one real regression caught by the existing test suite during rewiring (an exact-dict-equality assertion broke when `_session`/`_mode` metadata fields were added — updated the assertion, not a functional bug). 21 new unit tests. **646/646 suite green, `pyflakes` clean across every Phase A file.** Phase A exit criteria fully met — proceeding to Phase B next. |

*(Append new rows here after every session — do not overwrite history.)*
