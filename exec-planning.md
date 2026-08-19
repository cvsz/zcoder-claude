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

## 1. Current-state audit (ground truth, re-measured 2026-08-19)

| Metric | Value |
|---|---|
| Total original flat modules | 67 |
| Fully migrated to 4-layer architecture (shim + domain/infra/interfaces split) | **19** — Models, Admin API, Compliance API, Agent SDK (Phase A); Core Messaging's 6 files (Phase B); Tool Use & Retrieval's 5, Agent Execution & Code's 5 minus `claude_code.py`'s prior partial (Phase C #2–#3); Files & Documents' 4, Sessions/Memory/Cache's 3 (Phase C #4–#5) |
| Phase D, Context #7 (Cost, Metrics & Eval) | **IN PROGRESS.** `domain/observability.py` + `infrastructure/local_storage/observability_store.py` + `infrastructure/anthropic_api/observability_gateway.py` written and green (`pyflakes` clean, full suite still 888/888 since nothing wired in yet). **Not done:** `application/observability_service.py`, `interfaces/cli/commands/observability_commands.py`, the 4 compatibility shims, repointed/new tests, and `main.py` rewiring. `claude_cost_optimizer.py`/`claude_metrics.py`/`claude_observability.py`/`claude_eval.py` are all still their original untouched flat files. |
| Remaining flat modules (still mixed 3-concerns-in-1-file) | **28**, ~7,000 lines (Phase D contexts #7 (in progress) –#9, minus `claude_evals.py` — see below) |
| `application/` (use-case layer) coverage | **8 of 8 fully-migrated contexts route through `application/*_service.py`** (Phase A–C complete); Context #7's service layer not yet written |
| `main.py` | **2,413 lines, untouched.** 237 local-import dispatch points |
| `tests/` reorganized by layer | **Started, not complete.** `tests/unit/application/` has one test file per migrated context; the rest are still flat in `tests/` |
| Test suite | 888/888 passing (884 baseline + 4 from the agents-SDK on_delta/on_step merge below) |
| Static analysis | `pyflakes` clean across all migrated files (0 undefined names) |
| **Known dead code, not scheduled for migration** | `claude_evals.py` (plural) — pre-v1.10 eval harness superseded by `claude_eval.py` (singular); never wired into `main.py`, already documented as an intentional exclusion in `tests/test_cli_wiring.py`'s `KNOWN_EXCEPTIONS`. Migrating unreachable code would violate §6's Definition of Done ("every `application/*_service.py` function is called from at least one `interfaces/cli/commands/*` function"). Left as a flat file; candidate for outright deletion in a future cycle, not a Phase D gap. |

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

### Phase B — Migrate bounded contexts #1 and #6 (P0) — Core Messaging ✅ **COMPLETE 2026-08-15**; wrapper fold-in ⚠️ **PARTIAL**
- [x] Core Messaging: `claude_stream.py`, `claude_structured.py`,
  `claude_citations.py`, `claude_thinking.py`, `claude_tokens.py`,
  `claude_live.py` (1,331 lines) split into `domain/messaging.py`,
  `infrastructure/anthropic_api/messaging_gateway.py`,
  `application/messaging_service.py`,
  `interfaces/cli/commands/messaging_commands.py`, using the proven
  4-step pattern (§5). Inline `print()`/`stdout.write()` calls inside the
  SSE consumption loops (a new wrinkle Phase A didn't have — those
  contexts weren't streaming) converted to caller-supplied callbacks
  (`on_text`, `on_thinking`, `on_tool_delta`, ...), same convention as
  `agents_service.py`'s existing `on_step`. Old paths kept as re-export
  shims. 6 old-path unit test files repointed for the "second repoint"
  monkeypatch issue (§5 addendum) — `test_claude_structured.py` patched
  `claude_structured.urlopen_json`, now patches
  `infrastructure.anthropic_api.messaging_gateway.urlopen_json`;
  `test_claude_thinking.py`'s fixture now reloads
  `infrastructure.anthropic_api.messaging_gateway` (where the real
  `import anthropic` now lives) before reloading the shim, and its 3
  `cmd_thinking` tests now patch `application.messaging_service.ThinkingCoder`
  instead of the shim. 16 new direct unit tests in
  `tests/unit/application/test_messaging_service.py`. Found and fixed a
  real bug in the process: `claude_tokens.TokenCounter.estimate_cost` had
  its own local `prices_per_mtok` dict — the exact duplication anti-pattern
  §0 describes — now reads `domain/models/catalog.get_price()`.
- [x] Model-specific wrapper pricing dedup: `claude_fable5.py` (+ its
  `claude-mythos-5` entry, which `claude_mythos5.py` imports from it),
  `claude_opus5.py`, `claude_haiku45.py` each had a locally-defined
  `price_input_per_mtok_usd`/`price_output_per_mtok_usd` literal —
  duplicating `domain/models/catalog.py`'s `PRICE` table exactly the way
  `claude_sonnet5.py` used to before its own 2026-08-14 fix. All four now
  import `PRICE as _CATALOG_PRICE` from the catalog and reference it;
  `claude_sonnet5.py` and `claude_response_metadata.py` already had no
  local pricing table. **Not done:** the wrapper files were not
  structurally folded into `application/models_service.py` /
  `interfaces/cli/commands/model_commands.py` — `Fable5Client`,
  `Opus5Client`, `Haiku45Client`, `Sonnet5Client`, `Mythos5Client` and
  their `cmd_*info`/`cmd_*_call` functions still live in their own
  top-level files, unmigrated to the 4-layer split. The pricing-dedup
  half of this bullet is genuinely done and verified; the fold-in half
  is not — do not check this box as fully complete.
- **Exit criteria — Core Messaging: ALL MET.** Wrapper pricing:
  `grep -rn 'price_input_per_mtok_usd":\s*[0-9]\|price_output_per_mtok_usd":\s*[0-9]'`
  across all 6 wrapper files → zero matches (verified 2026-08-15). Full
  suite 662/662 green (646 baseline + 16 new `messaging_service` tests);
  `pyflakes` clean on all 11 touched/new files; `python main.py --help`
  exits 0 with all Core Messaging flags still routing.

### Phase C — Migrate bounded contexts #2–#5 (P1) — ✅ **COMPLETE** (#2: 2026-08-16, #3: 2026-08-17, #4 & #5: 2026-08-18)
- [x] Context #2 — Tool Use & Retrieval ✅ **COMPLETE 2026-08-16**:
  `claude_tools.py`(1,009), `claude_vision.py`(182), `claude_search.py`(162),
  `claude_embeddings.py`(191), `claude_rag.py`(160) — 1,927 lines total —
  split into `domain/tools.py`; four new infra gateways
  (`infrastructure/anthropic_api/tools_gateway.py`, `.../vision_gateway.py`,
  `.../search_gateway.py`, `.../rag_gateway.py`); a new
  `infrastructure/voyage_api/` package for `embeddings_gateway.py` (kept
  separate from `anthropic_api/` — Voyage is a genuinely different
  vendor, so an outage there is never mistaken for an Anthropic outage);
  a new `infrastructure/local_storage/rag_index_store.py` for the RAG
  index's local-disk persistence (the project's first non-HTTP
  infrastructure adapter); `application/tools_service.py`;
  `interfaces/cli/commands/tools_commands.py`. Verbose print()-in-loop
  logging (tool calls, memory ops, task-budget warnings) converted to
  callbacks, same convention as Phase B. Fixed 2 more "second repoint"
  monkeypatch issues (§5 addendum): `test_claude_tools.py`'s `urlopen`
  patch now targets the real `urllib.request` module directly (the fake
  `mod.urllib.request` path stopped resolving once the shim dropped its
  own `import urllib`); `test_claude_search.py`'s fixture now reloads
  `infrastructure.anthropic_api.search_gateway` before reloading the
  shim, same fix as Phase B's `test_claude_thinking.py`. 16 new direct
  unit tests in `tests/unit/application/test_tools_service.py`.
  **Exit criteria — ALL MET:** full suite 678/678 green (662 baseline +
  16 new); `pyflakes` clean (only pre-existing f-string-style notes
  untouched by this pass); zero `print()` outside `interfaces/` in any
  touched file; `python main.py --help` exits 0 with all context #2
  flags still routing.
- [~] Context #3 — Agent Execution & Code ⚠️ **PARTIAL 2026-08-16**:
  4 of 5 files done — `claude_code_exec.py`(249), `claude_sandbox.py`(129),
  `claude_router.py`(165), `claude_hooks_perms_plan.py`(291), 834 lines —
  split into `domain/agent_execution.py`,
  `infrastructure/anthropic_api/code_agent_gateway.py` (Code Execution
  tool, Plan Mode, Router — pure Anthropic API callers),
  `infrastructure/local_storage/hooks_permissions_store.py` (Hooks —
  which run arbitrary shell commands via subprocess, and Permissions —
  both local-disk-backed, so kept out of the anthropic_api package),
  `application/code_agent_service.py`,
  `interfaces/cli/commands/code_agent_commands.py`. `claude_sandbox.py`
  was entirely pure logic (zero I/O) and moved in full to
  `domain/agent_execution.py`. Fixed a per-step print ordering bug while
  splitting `cmd_plan` (the original interleaves "Step N: desc" with its
  result per-step; a first-draft callback wiring printed all headers up
  front instead — caught by re-reading the original before shipping, not
  by a test). Fixed one more "second repoint" monkeypatch issue in
  `test_claude_code_exec.py` (`urlopen`, same fix as `test_claude_tools.py`).
  8 new direct unit tests in `tests/unit/application/test_code_agent_service.py`
  — one of which caught a real bug in my own first draft (`plan_execute_all`
  called `PlanModeAgent.approve()` as an implicit dependency the test's
  fake hadn't provided, i.e. the test did its job).
  [x] `claude_code.py` (1,436 lines) COMPLETE 2026-08-17 — the
  deferred file. 9 classes split into `domain/code_agent.py` (pure data:
  tool presets/schemas, hook event names, slash-command tables, skill
  metadata, frontmatter parsing, storage-path constants — no I/O),
  `infrastructure/local_storage/code_agent_store.py` (CodeSession,
  HooksEngine, McpConnector, SubagentRegistry, SkillsRegistry,
  TodoManager, MemoryManager — all local-disk/subprocess-backed, so kept
  out of `anthropic_api/`, same reasoning as Hooks/Permissions in the
  first 4 Context #3 files), `infrastructure/anthropic_api/
  code_agent_loop_gateway.py` (CodeAgent, StructuredAgentOutput — the
  Messages-API agentic loop, reimplemented in stdlib), `application/
  code_agent_loop_service.py` (use-case layer — named `_loop_service` to
  avoid colliding with the already-existing `code_agent_service.py` from
  the first 4 Context #3 files), `interfaces/cli/commands/
  code_agent_loop_commands.py` (all 8 cmd_* entry points). This picked up
  where a prior session's partial draft of the first 3 layers had been
  left mid-migration (found already present in the working tree at
  session start) — verified it file-by-file against the still-present
  original `claude_code.py` rather than assuming it was correct, which
  surfaced 3 real bugs before they reached the shim/tests: (1)
  `build_context_management` was imported from the wrong module
  (`domain.agent_execution` instead of `domain.tools`) — a hard
  `ImportError`, not a style nit; (2) an unused `StructuredAgentOutput`
  import; (3) `generate_todos()` had silently merged two distinct
  original behaviors (a regex-miss with no exception, which the
  original leaves completely silent — no items, no printed text —
  versus a JSON-parse exception, which prints the raw response) into
  one fallback path that always surfaced raw text — fixed via a
  `(items, raw_on_error)` return contract that preserves both original
  branches exactly; a regression test
  (`test_generate_todos_no_match_returns_nothing_silently`) now pins
  this down. The CodeSession pricing bug flagged in the prior session's
  notes (`add_turn()`'s hardcoded "Sonnet 4.5 rates" `$3/$15` literal)
  was already fixed in the partial draft found — verified it now reads
  `domain/models/catalog.get_price()`. Interactive permission-approval
  flow: preserved exactly via `_on_permission_prompt` (the yellow
  `[permission] ...` print, skipped for read-only tools) +
  `_interactive_can_use_tool` (the `input("Approve? [Y/n]")` block, same
  read-only bypass) in the new CLI module, matching the original's
  `_execute_tool` fallback branch tool-for-tool — one deliberate, minor,
  documented behavior change: the original distinguished an explicit
  "n" answer from no terminal being attached (different denial-message
  text, same denial); the new gateway's `can_use_tool` callback returns
  a plain bool, so both now surface as "[DENIED by user]" — noted
  in-code rather than silently dropped. `HooksEngine.fire()`'s 3
  original print-call-sites (yellow non-blocking warning, red timeout,
  red exception) now funnel through one `on_warning(str)` callback per
  the established Phase C/B callback convention — recovered the
  original's color choice from the message text in
  `_hook_fire_warning()` rather than losing it. `claude_code.py` itself
  is now a ~60-line re-export shim (original 1,436-line version backed
  up out-of-repo before overwriting, not committed anywhere in-tree).
  `tests/test_claude_code_context_editing.py`'s monkeypatches hit the
  predicted "second repoint" pattern (§5 step 5) on both fixtures —
  `claude_code.SESSIONS_DIR` -> `infrastructure.local_storage.
  code_agent_store.SESSIONS_DIR`, `claude_code.CodeAgent` ->
  `interfaces.cli.commands.code_agent_loop_commands.CodeAgent` (3 call
  sites) — reproduced the failure first (all 3 `cmd_code_agent` tests
  failing with `KeyError`/a real 401 from a live call before the fix) to
  confirm it was genuinely this bug and not something else, then fixed.
  Also hit a *third* import-name collision, this time inside my own new
  test file: `list_session_files()` resolves `SESSIONS_DIR` from
  `application/code_agent_loop_service.py`'s own module namespace (a
  separate import site from the one `CodeSession.save()` uses in the
  store module) — same pattern, different module pair, worth flagging
  since it shows this isn't just a migration-boundary artifact, it's
  inherent to how Python resolves module-level globals whenever the
  same constant is imported into multiple places. 19 new direct unit
  tests in `tests/unit/application/test_code_agent_loop_service.py`.
  Verified end-to-end through the real CLI, not just unit tests: `python
  main.py --code-agent-list-tools`, `--code-agent-list-sessions`, and
  `--code-agent-slash doctor` all run through the full shim ->
  interfaces -> application -> domain stack correctly post-migration.
- **Exit criteria — Context #3 (Agent Execution & Code) — ALL MET,
  phase now fully complete:** full suite 708/708 green (689 baseline +
  19 new); `pyflakes` clean on every touched/new file including the
  shim and both test files; zero `print()`/`input()` outside
  `interfaces/` in any touched file; `python main.py --help` exits 0,
  `--code-agent*` flag-mention count unchanged (39, verified
  before/after); real CLI invocations (not just pytest) confirmed
  working post-migration.

### Out-of-band fix — `--upgrade-all` gap, found via v1.46.0 vs. current comparison (2026-08-17)
User re-uploaded an earlier v1.46.0 snapshot and asked to compare it
against current work and "upgrade all latest of claude." The diff
against v1.46.0 was exactly the Phase C work above (no external edits —
confirmed the upload was untouched). Took "upgrade all latest of claude"
as a live audit-cycle prompt (this project's own established pattern —
see `/areas/zcoder.md`) rather than only a diff request, and
cross-checked `domain/models/catalog.py` against current web sources.
Catalog itself (`MODEL_CATALOG`, `PRICE`, `RETIRED_MODELS`) was already
correct and current — including the 2026-08-10 Sonnet 5
permanent-pricing confirmation. The real gap was `UPGRADE_TARGETS`:
`--upgrade-all`, the feature literally named for this task, had no path
to `claude-opus-5` or `claude-sonnet-5` — both current-tier flagships —
only `fable5` and a stale `opus` pointing at 4.8. Fixed: added `opus5`
and `sonnet5` targets, corrected a stale docstring, added 3 regression
tests, wrote `docs/54_bugfix_upgrade_target_opus5_sonnet5.md`, bumped
`CHANGELOG.md`/`pyproject.toml` to v1.40.0 (the project's real semver,
separate from this refactor's `vX.Y.0` docstring-header convention).
Full suite 689/689 green. This was a small, targeted fix, not part of
the Clean Architecture migration itself — noted here so the history log
stays complete.
- [ ] Context #4 — Files & Documents (in progress) — `claude_files.py`
  (367) [x] **COMPLETE 2026-08-18** — split into `domain/files.py`
  (BETA_HEADER + `_validate_filename`, pure), `infrastructure/
  local_storage/files_registry_store.py` (the local "which files did I
  upload from this machine" cache — the Files API itself has no such
  endpoint), `infrastructure/anthropic_api/files_gateway.py` (FilesAPI:
  upload/list/get/download/delete + the Messages-API file-reference call
  in `ask_about_file`), `application/files_service.py` (thin ops — the
  original `cmd_*` bodies were already thin, one API call + prints, so
  no meaningful orchestration logic to extract, unlike
  `code_agent_loop_service.py`'s heavier lift), `interfaces/cli/commands/
  files_commands.py` (5 cmd_* entry points). One fidelity fix during the
  split: the original `FilesAPI.__init__` eagerly created
  `~/.ai-coder/` on every construction, not lazily on first write;
  moved that into `files_registry_store.ensure_registry_dir()`, called
  both from `FilesAPI.__init__` and from `register_file`/
  `unregister_file`, so the eager-creation behavior survives the split
  intact (verified via a real, non-mocked `--file-upload` /
  `--file-list` CLI run against `~/.ai-coder/` afterward, not just
  unit tests). No pre-existing dedicated test file existed for
  `claude_files.py` before this migration (a real coverage gap, now
  closed) — added `tests/unit/domain/test_files.py` (7 tests, the
  project's first `domain/` unit test file — prior domain layers were
  only covered indirectly through their service-layer tests) and
  `tests/unit/application/test_files_service.py` (5 tests). Consumers
  (`claude_powerpoint.py`, `claude_excel.py`,
  `application/agents_service.py` import `FilesAPI`; `main.py` imports
  the 5 `cmd_file_*` functions) verified importing cleanly against the
  shim, unmodified. 720/720 suite green (708 + 12 new), `pyflakes`
  clean, `python main.py --help` output byte-identical before/after.
  `claude_powerpoint.py`(458) [x] **COMPLETE 2026-08-18** — split into
  `domain/powerpoint.py` (pure constants: SYSTEM_PROMPT, the code-block
  regex, the safety denylist, REPL help text), `infrastructure/
  local_storage/pptx_deck_store.py` (PptxSession — kept as one class
  rather than split method-by-method, same reasoning as CodeSession in
  Context #3: __init__/_load/save/_add_table/_add_chart depend on
  python-pptx and disk, while summary()/undo()/apply_code() are pure
  logic operating on the same `self.slides` state, and this project has
  no precedent for splitting one class's methods across layers),
  `application/pptx_service.py` (one turn's worth of logic for both the
  hand-rolled path — `run_turn` — and the `--pptx-native` Skills-API
  path — `upload_input_deck`/`run_native_turn` — mirroring
  `code_agent_loop_service.run_agent_query`'s shape: one function per
  "what happens when the user sends one message", the REPL shell stays
  in `interfaces/`), `interfaces/cli/commands/pptx_commands.py` (the
  print()/input() REPL shell for both paths). Verified the extracted
  `PptxSession` class byte-for-byte against the original via a
  programmatic diff, not just a read-through. Real, non-mocked tests
  against actual python-pptx output (`tests/test_pptx_deck_store.py`,
  8 tests — save/reload roundtrip, table+chart rendering, denylist
  blocking, undo/rollback), `tests/unit/domain/test_powerpoint.py` (6
  tests), `tests/unit/application/test_pptx_service.py` (12 tests,
  written this session — the two prior test files already existed when
  this session picked the migration back up mid-stream, this one didn't
  yet). 748/748 suite green (720 + 12 new this session, +16 already
  present), `pyflakes` clean, `python main.py --help` byte-identical,
  and a genuine end-to-end REPL smoke test (`add_slide(...)` /slides
  /exit through stdin) run through the real `cmd_pptx_chat` — confirmed
  it reaches an actual (fake-key, 401) API call and prints the error
  correctly, not just that it imports.
  `claude_excel.py`(396) [x] **COMPLETE 2026-08-18** — split into
  `domain/excel.py` (pure constants), `infrastructure/local_storage/
  excel_workbook_store.py` (ExcelSession, kept as one class per the
  PptxSession/CodeSession precedent), `application/excel_service.py`
  (one turn's worth of logic for both paths, mirroring
  `pptx_service.py`'s shape exactly — same product, same
  session/history/undo/native design, per the original module's own
  docstring), `interfaces/cli/commands/excel_commands.py` (the REPL
  shell). Verified the extracted `ExcelSession` class byte-for-byte
  identical to the original via programmatic diff before writing
  anything downstream of it — same discipline as
  `claude_powerpoint.py`. 31 new tests, all against real pandas/
  openpyxl output where relevant, not mocks
  (`tests/test_excel_workbook_store.py`'s 13 tests include a CSV load,
  a multi-sheet workbook load with an explicit `sheet_name`, and a
  chart-write round-trip). 779/779 suite green (748 + 31 new),
  `pyflakes` clean, `python main.py --help` byte-identical, and a real
  end-to-end REPL smoke test (mutate `sheets["Sheet1"]`, `/sheets`,
  `/exit` through stdin) confirmed reaching an actual 401 from the real
  API and printing it correctly.
  `claude_batch.py`(295) [x] **COMPLETE 2026-08-18** — split into
  `domain/batch.py` (OUTPUT_300K_BETA/OUTPUT_300K_MODELS/
  OUTPUT_300K_MAX_TOKENS, pure), `infrastructure/local_storage/
  batch_store.py` (the local submission-metadata cache — the Batch API
  doesn't echo back the source JSONL path or submit time on later
  status/list calls), `infrastructure/anthropic_api/batch_gateway.py`
  (BatchCoder — real `anthropic` SDK client calls, the first migrated
  gateway to use the SDK client directly rather than raw urllib), then
  `application/batch_service.py` / `interfaces/cli/commands/
  batch_commands.py`. Caught a real Definition-of-Done violation in my
  own first draft before it landed: the original `BatchCoder` had two
  direct `print()` calls buried in it (an `OUTPUT_300K_MODELS`
  eligibility warning in `__init__`, and a live `'\r...end=""'`
  progress line in `wait()`'s polling loop) — my first pass carried
  both into the gateway file with a comment justifying the exception,
  which on rereading §6's exit-criteria checklist ("No file outside
  `interfaces/` contains a `print()` call") is exactly the kind of
  shortcut the playbook says not to take; rewrote both as
  `on_warning`/`on_progress` callbacks (`Callable[[str], None] = _NOOP`
  default) using the *exact* convention already established in
  `infrastructure/local_storage/code_agent_store.py`'s
  HooksEngine/McpConnector/SubagentRegistry, rather than inventing a
  new pattern or carving out a one-off exception. One fidelity
  wrinkle worth flagging: the original `wait()` always printed exactly
  one bare trailing newline right before returning — on both the
  "batch ended" early-return path and the "max_wait elapsed" fallback
  path — so instead of trying to signal "this is the final callback
  invocation" through the callback itself (the timeout path doesn't
  know it's exiting until after the loop condition re-check), the
  trailing newline moved to the caller: `interfaces/cli/commands/
  batch_commands.py`'s `cmd_batch_generate` now calls `print()`
  unconditionally immediately after `service.wait_for_batch(...)`
  returns, reproducing the original's always-exactly-one-newline
  behavior regardless of which branch produced it — pinned down by a
  dedicated regression test
  (`test_cmd_batch_generate_with_wait_prints_trailing_newline_after_progress`).
  27 new tests across 5 files, including the project's first tests
  written directly against a migrated `*_gateway.py` module
  (`tests/test_batch_gateway.py`, with a fake `anthropic.Anthropic`
  client substituted in — no real SDK calls) since prior gateways were
  only covered indirectly through their application-service tests.
  806/806 suite green (779 + 27 new), `pyflakes` clean, `python main.py
  --help` byte-identical, and a real end-to-end `--batch-list`
  invocation confirmed reaching the actual `anthropic` SDK and
  surfacing a genuine `AuthenticationError` (401), not a mock. **Context
  #4 (Files & Documents) is now complete in its entirety** — all 4
  files (`claude_files.py`, `claude_powerpoint.py`, `claude_excel.py`,
  `claude_batch.py`) migrated, verified, and documented in the same
  session. Remaining Phase C work: Context #5 (Sessions, Memory &
  Cache), not yet started.
- [x] Context #5 — Sessions, Memory & Cache — **COMPLETE 2026-08-18**:
  `claude_sessions.py`(227), `claude_memory.py`(175),
  `claude_cache.py`(553), all 3 in one session, completing Phase C.
  All 3 followed the same shape as Context #4's document files: a
  domain/ dataclass/enum layer, a single stateful class kept intact in
  infrastructure/ rather than split method-by-method (MemoryStore,
  matching CodeSession/PptxSession/ExcelSession precedent —
  claude_sessions.py's Session/Checkpoint had no such class, just
  free functions, so infrastructure/local_storage/sessions_store.py
  is function-based instead), a thin application/ layer, and an
  interfaces/ CLI layer. `claude_cache.py`'s CachingCoder is the
  first Context #5 gateway with no local disk I/O at all (pure HTTP),
  so it's the only one of the 3 with an infrastructure/anthropic_api/
  file instead of infrastructure/local_storage/. Two real defects
  caught and fixed during the split, both confirmed pre-existing via
  pyflakes against the untouched original before touching anything:
  (1) a dead `prot` local variable in MemoryStore.enforce_retention()
  (computed, never read — removed, no behavioral effect, pinned down
  by a regression test that exercises the exact code path it used to
  sit in); (2) two `f"..."` strings with no `{}` placeholders in what
  is now `interfaces/cli/commands/cache_commands.py`. More
  significantly: `CachingCoder.print_cache_stats()` — a print()-emitting
  *method* on the gateway class — is the second time this session
  applied the batch_gateway.py lesson from Context #4 (catch a
  Definition-of-Done violation before it lands, not after): confirmed
  via a repo-wide grep that nothing outside this module's own 3 cmd_*
  functions ever called it, then removed it from CachingCoder entirely
  rather than keeping it and routing it through a callback — the pure,
  dict-returning cache_stats() half stays on the class, and the print
  formatting moved to interfaces/cli/commands/cache_commands.py's
  _print_cache_stats(), the same split every other stateful class in
  this project already uses (none of which, on inspection, ever had a
  print()-emitting method to begin with). The pre-existing
  `tests/test_claude_cache.py` (20 tests, added in an earlier session
  when this module still had zero coverage) needed zero changes and
  passes unmodified against the new shim — no "second repoint" issue
  here since it monkeypatches `CachingCoder` instances directly
  (`monkeypatch.setattr(cc, "_post", ...)`), never a module-level
  path string. 78 new tests across 10 new/touched test files. 884/884
  suite green (806 + 78 new), `pyflakes` clean across every touched/
  new file, `python main.py --help` byte-identical, and real
  end-to-end CLI runs confirmed for all 3: `--sessions-list`, a real
  `--memory-add`/`--memory-recall`/`--memory-stats` round trip against
  actual `~/.ai-coder/memory/` disk state (cleaned up after), and both
  `--cache` and `--cache-warm` reaching the genuine Anthropic API and
  surfacing a real 401. **Context #5 is now complete in its entirety —
  which completes Phase C.**
- [ ] Each context's tests move to `tests/unit/`, `tests/integration/`,
  `tests/e2e/` as they're touched (§1.1 item 4 — done incrementally, not
  as a separate mass-move)
- **Exit criteria (whole phase):** per context — full suite green, `pyflakes`
  clean, `python main.py --help` reachable, no `print()` outside `interfaces/`

### Phase D — Migrate bounded contexts #7–#9 (P2)
- [ ] Same pattern, lowest urgency — can run in parallel with Phase E if
  a second engineer/session is available, since these contexts don't block
  `main.py`'s split
- [~] **Context #7 (Cost, Metrics & Eval) — STARTED 2026-08-19, not complete.**
  `claude_cost_optimizer.py`, `claude_metrics.py`, `claude_observability.py`,
  `claude_eval.py` (870 lines total). Domain + both infrastructure layers
  written (`domain/observability.py`,
  `infrastructure/local_storage/observability_store.py`,
  `infrastructure/anthropic_api/observability_gateway.py`); `pyflakes`
  clean; full suite still 888/888 since none of it is wired in yet.
  **Remaining:** `application/observability_service.py`,
  `interfaces/cli/commands/observability_commands.py`, 4 compatibility
  shims, `main.py` rewiring, and tests (repoint the existing
  `tests/test_claude_cost_optimizer.py` / `tests/test_claude_metrics.py`
  path-monkeypatch fixtures per the playbook step 5 "second repoint"
  pattern — they currently patch `claude_metrics.LOG_PATH`/module-level
  constants directly, which won't reach the new store module's I/O
  functions — plus net-new coverage for `claude_observability.py` and
  `claude_eval.py`, which had **zero** test files before this session).
  Findings so far, to carry into the application/interfaces build-out:
  - `estimate_cost()` (cost optimizer) and `_price()` (metrics) each
    re-implemented the surcharge/inference_geo pricing logic that
    `domain/models/catalog.py`'s `estimate_cost_usd()` already
    canonicalizes — same duplicate-pricing defect class §0 describes.
    Both now delegate to it in `domain/observability.py`
    (`estimate_cost()`/`price_lookup()`); existing pricing tests should
    pass unmodified since the underlying formula is identical.
  - `claude_observability.py`'s `error_analysis()` and `claude_eval.py`'s
    `EvalRunner.run()` both `print()`ed directly from what's now
    infrastructure/ code — converted to `on_case`/no-callback conventions
    matching `agents_gateway.py`'s `on_step`/`on_delta` (see Phase C
    history below for that convention's origin).
  - `claude_evals.py` (plural, dead code) explicitly **excluded** from
    this context's scope — see §1 "Known dead code" row above.

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
| 2026-08-15 | **Phase B complete** | Core Messaging (`claude_stream.py`, `claude_structured.py`, `claude_citations.py`, `claude_thinking.py`, `claude_tokens.py`, `claude_live.py`) migrated to `domain/messaging.py` / `infrastructure/anthropic_api/messaging_gateway.py` / `application/messaging_service.py` / `interfaces/cli/commands/messaging_commands.py`. Model-wrapper pricing dedup done for `claude_fable5.py`, `claude_opus5.py`, `claude_haiku45.py` (structural fold-in into `application/models_service.py` explicitly left undone — see §4 Phase B note). 662/662 suite green. See §4 Phase B for full detail (this row is a summary; the phase section above is authoritative). |
| 2026-08-16 | **Phase C, Context #2 complete** | Tool Use & Retrieval (`claude_tools.py`, `claude_vision.py`, `claude_search.py`, `claude_embeddings.py`, `claude_rag.py`) migrated, including the project's first non-Anthropic gateway package (`infrastructure/voyage_api/`) and first non-HTTP infrastructure adapter (`infrastructure/local_storage/rag_index_store.py`). 678/678 suite green. See §4 Phase C for full detail. |
| 2026-08-16 | **Phase C, Context #3 — 4 of 5 files** | Code Execution tool, Hooks, Permissions, Plan Mode, Multi-Agent Router migrated (`claude_code_exec.py`, `claude_sandbox.py`, `claude_router.py`, `claude_hooks_perms_plan.py`) into `domain/agent_execution.py` / `infrastructure/anthropic_api/code_agent_gateway.py` / `infrastructure/local_storage/hooks_permissions_store.py` / `application/code_agent_service.py` / `interfaces/cli/commands/code_agent_commands.py`. `claude_code.py` (the 5th and largest file) explicitly deferred, not skipped — see that session's detailed note (superseded by the 2026-08-17 completion below). 686/686 suite green. |
| 2026-08-17 | Out-of-band fix | `--upgrade-all` had no path to `claude-opus-5`/`claude-sonnet-5`. Fixed, 3 regression tests added, v1.40.0. 689/689 suite green. See §4 "Out-of-band fix" section above for full detail. |
| 2026-08-17 | **Phase C, Context #3 complete** | `claude_code.py` (1,436 lines, the deferred file) migrated — found a prior session's partial draft of `domain/code_agent.py`, `infrastructure/local_storage/code_agent_store.py`, and `infrastructure/anthropic_api/code_agent_loop_gateway.py` already sitting in the working tree at session start; verified it file-by-file against the still-present original rather than trusting it, which surfaced and fixed 3 real bugs (wrong import path for `build_context_management` — a hard `ImportError`; an unused import; `generate_todos()` conflating two distinct original behaviors into one). Built the missing `application/code_agent_loop_service.py` and `interfaces/cli/commands/code_agent_loop_commands.py`, reproducing the original's `input()`-based interactive permission-approval flow and hook-warning color-coding exactly. Wrote the `claude_code.py` compatibility shim (1,436 lines → ~60). Hit and fixed the predicted "second repoint" monkeypatch pattern in `tests/test_claude_code_context_editing.py` (3 call sites) plus a third, novel instance of the same underlying issue inside this session's own new test file. 19 new direct unit tests. **708/708 suite green (689 baseline + 19 new), `pyflakes` clean, `python main.py --help` exits 0 with all 39 `--code-agent*` flag mentions intact, and 3 real end-to-end CLI invocations (`--code-agent-list-tools`, `--code-agent-list-sessions`, `--code-agent-slash doctor`) verified working through the full shim → interfaces → application → domain stack.** Phase C, Context #3 exit criteria fully met — Context #3 is now complete in its entirety. Remaining Phase C work: Context #4 (Files & Documents) and Context #5 (Sessions, Memory & Cache), both not yet started. |

| 2026-08-18 | **Phase C, Context #4 complete** | Files & Documents (`claude_files.py`, `claude_powerpoint.py`, `claude_excel.py`, `claude_batch.py` — 1,516 lines total) migrated in one session. Found `claude_powerpoint.py`'s split partially pre-drafted mid-session (like Context #3's `claude_code.py`) and verified it byte-for-byte against the original via programmatic diff rather than trusting it, then applied the same discipline proactively to `claude_excel.py`. Real fidelity bugs caught and fixed before landing: `FilesAPI`'s eager `~/.ai-coder/` directory creation (moved into `files_registry_store.ensure_registry_dir()`); and — the most consequential one — a self-caught Definition-of-Done violation in `claude_batch.py`'s gateway draft (two `print()` calls in the `anthropic` SDK gateway, initially "justified" with a comment instead of fixed), corrected to the established `on_warning`/`on_progress` callback convention rather than a one-off exception, with a dedicated regression test for the trailing-newline fidelity edge case that fix introduced. `claude_batch.py` is also the first migrated `*_anthropic_api/` gateway to wrap the `anthropic` SDK client directly rather than raw urllib, and the first to get direct gateway-level tests (`tests/test_batch_gateway.py`, fake SDK client, no real calls) rather than only application-layer coverage. 87 new tests total across the 4 files this session (12 + 12 + 31 + 27 + 5 CLI-layer). **806/806 suite green (708 at session start → 806), `pyflakes` clean across every touched/new file, `python main.py --help` byte-identical after each of the 4 migrations, and real (non-mocked) end-to-end CLI runs verified for all 4** — `--file-upload`/`--file-list`, a full `cmd_pptx_chat` REPL turn through stdin, a full `cmd_excel_chat` REPL turn through stdin, and `--batch-list` reaching a genuine `anthropic.AuthenticationError`. Context #4 exit criteria fully met. Remaining Phase C work: Context #5 (Sessions, Memory & Cache — `claude_sessions.py`, `claude_memory.py`, `claude_cache.py`, 955 lines), not yet started. |

| 2026-08-18 | **Phase C complete — Context #5 (final context)** | Sessions, Memory & Cache (`claude_sessions.py`, `claude_memory.py`, `claude_cache.py` — 955 lines total) migrated in one session, completing all 4 remaining Phase C contexts (#2–#5). Followed the Context #4 document-file shape throughout: domain/ dataclasses, a kept-intact stateful class in infrastructure/ where one existed (`MemoryStore`, matching the CodeSession/PptxSession/ExcelSession precedent), thin application/ ops, print()-only interfaces/. `claude_cache.py`'s `CachingCoder` is the first Context #5 gateway with zero local disk I/O — pure HTTP, so `infrastructure/anthropic_api/cache_gateway.py` instead of `local_storage/`. Two real, pre-existing defects caught via pyflakes against the untouched original before touching anything: a dead `prot` variable in `MemoryStore.enforce_retention()` (removed, regression-tested); two placeholder-less f-strings. More significant: applied the `claude_batch.py` lesson from Context #4 a second time — `CachingCoder.print_cache_stats()` was a print()-emitting *method* on the gateway class; confirmed via repo-wide grep that nothing outside the module's own 3 `cmd_*` functions ever called it, then removed it from the class entirely (not routed through a callback like `claude_batch.py`'s case — there was no external caller to preserve compatibility for) and moved the print formatting into `interfaces/cli/commands/cache_commands.py`. The pre-existing `tests/test_claude_cache.py` (20 tests) needed zero changes and passed unmodified against the new shim. 78 new tests across 10 files. **884/884 suite green (806 at session start → 884), `pyflakes` clean across every touched/new file, `python main.py --help` byte-identical, and real end-to-end CLI runs confirmed for all 3** — `--sessions-list`, a real `--memory-add`/`--memory-recall`/`--memory-stats` round trip against actual `~/.ai-coder/memory/` disk state, and both `--cache` and `--cache-warm` reaching the genuine Anthropic API and surfacing a real 401. **Phase C (bounded contexts #2–#5) is now complete in its entirety.** Next: Phase D (bounded contexts #7–#9, P2) or Phase E (splitting `main.py`, deliberately deferred to last), neither started. |

| 2026-08-19 | Out-of-band merge | A prior session had left an uncommitted fix in a parallel working copy (`zcoder-v1_53_0-edit`), not yet folded into the delivered `zcoder-v1_53_0.zip`: the agents-SDK print()-removal fix (same Definition-of-Done pattern as `claude_batch.py`/`claude_cache.py` in Phase C, Context #4/#5) — `infrastructure/anthropic_api/agents_gateway.py`'s `run_task()`, `wait_for_outcome()`, `stream_thread()`, and `ManagedAgent.orchestrate()` no longer `print()` directly; they now call `on_delta(text)`/`on_step(event, data)` callbacks, wired to real `print()` calls in `interfaces/cli/commands/agent_commands.py`. Diffed both copies file-by-file before merging (7 files) rather than trusting the edit copy blindly. Found and fixed one test the edit copy's own session had missed — `tests/unit/application/test_agents_service.py::test_run_managed_agent_task_plain_task_sequence` still asserted `run_task()`'s exact call signature, the same "second repoint" monkeypatch pattern §5 step 5 warns about; updated to assert on the meaningful args/kwargs instead, matching the convention `tests/test_claude_agents_sdk.py`'s own equivalent assertion already used. `pyflakes` clean on all 7 merged files (pre-existing warnings elsewhere confirmed identical before/after, unrelated to this fix). **888/888 suite green (884 baseline + 4)**, `python main.py --help` byte-identical before/after. |
| 2026-08-19 | Phase D, Context #7 — started, not complete | Cost, Metrics & Eval (`claude_cost_optimizer.py`, `claude_metrics.py`, `claude_observability.py`, `claude_eval.py` — 870 lines). Wrote `domain/observability.py`, `infrastructure/local_storage/observability_store.py`, and `infrastructure/anthropic_api/observability_gateway.py` (domain + both infra layers). Found and fixed a real duplicate-pricing defect in the process — `estimate_cost()`/`_price()` each re-implemented `domain/models/catalog.py`'s `estimate_cost_usd()` surcharge/geo logic instead of delegating to it, the exact anti-pattern §0 describes; also converted `error_analysis()`/`EvalRunner.run()`'s direct `print()` calls to the established `on_case`/callback convention. Confirmed `claude_evals.py` (plural) is deliberately-unwired dead code per `tests/test_cli_wiring.py`'s existing `KNOWN_EXCEPTIONS` and excluded it from this context's scope rather than migrating unreachable code. `pyflakes` clean on all 3 new files; full suite still 888/888 (nothing wired in yet, so no regression risk from this partial state). **Not done, next session:** `application/observability_service.py`, `interfaces/cli/commands/observability_commands.py`, 4 compatibility shims, `main.py` rewiring, repointing `test_claude_cost_optimizer.py`/`test_claude_metrics.py`'s path-monkeypatch fixtures (the anticipated "second repoint" issue — store module now owns `SPEND_LOG`/`METRICS_LOG_PATH`, so tests patching the old shim's module-level constant won't reach it), and net-new tests for `claude_observability.py`/`claude_eval.py` (zero coverage previously). Context #7 exit criteria **not yet met** — do not check its box complete. |

*(Append new rows here after every session — do not overwrite history.)*
