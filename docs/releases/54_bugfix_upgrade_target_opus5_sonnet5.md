# Bugfix — `--upgrade-all` had no path to Claude Opus 5 or Claude Sonnet 5

## What was broken

`domain/models/catalog.py`'s `UPGRADE_TARGETS` — the lookup `--upgrade-all`
uses to decide which model ID to rewrite everything to — only had two
entries:

```python
UPGRADE_TARGETS = {
    "fable5": "claude-fable-5",
    "opus":   "claude-opus-4-8",
}
```

`MODEL_CATALOG` itself already listed `claude-opus-5` and
`claude-sonnet-5` as `"tier": "current"` — both were correctly priced,
documented, and reachable via `--model-info`/`--models` — but neither
had an `--upgrade-target` entry, so `--upgrade-all` (the feature whose
entire job is "point every model ID reference in this codebase at the
latest model") could not actually target the two most current flagship
models: Claude Opus 5 (released 2026-07-24) and Claude Sonnet 5.

The `upgrade_all()` docstring in `application/models_service.py` had
also drifted: it said the target could be `'fable5' or 'opus48'`, but
the real key was `"opus"`, not `"opus48"` — cosmetic, but a second
signal this table hadn't been revisited since Opus 5 shipped.

Found 2026-08-17 while comparing an earlier v1.46.0 snapshot against the
current tree and cross-checking the model catalog against
platform.claude.com/docs and Anthropic's own Sonnet 5 announcement page
(confirming the 2026-08-10 pricing-permanence edit was already correctly
reflected in `PRICE`/`MODEL_CATALOG` — that part of the catalog was
current; only `UPGRADE_TARGETS` had the gap).

## Fix

- `domain/models/catalog.py`: added `"opus5": "claude-opus-5"` and
  `"sonnet5": "claude-sonnet-5"` to `UPGRADE_TARGETS`. Left `"opus"`
  pointing at `claude-opus-4-8` rather than repointing it at Opus 5 —
  repointing an existing target's meaning would silently change behavior
  for any existing `--upgrade-target opus` script or CI job; `opus5` is
  the new, explicit way to reach the actual latest Opus.
- `application/models_service.py`: fixed the stale docstring.
- `main.py`: `--upgrade-target`'s `choices` already derives from
  `sorted(UPGRADE_TARGETS)` automatically, so no argparse change was
  needed — only the `--help` text listing what each choice maps to.
- Added 3 new tests in `tests/unit/application/test_models_service.py`:
  - `opus5` rewrites a model ID to `claude-opus-5` and applies for real
  - `sonnet5` rewrites a model ID to `claude-sonnet-5` and applies for real
  - `opus` is unchanged (still `claude-opus-4-8`), confirming backward
    compatibility for existing callers

## Verification

- `python main.py --help` shows `--upgrade-target {fable5,opus,opus5,sonnet5}`
- Manual dry-run against a throwaway file confirmed both new targets
  produce the correct `target_id` and rewrite text
- Full suite: 689/689 green (686 baseline + 3 new)
- `pyflakes` clean on all three edited files (pre-existing unrelated
  unused-import notes in `domain/models/catalog.py` and
  `application/models_service.py` — `os`, `json`, `MODEL_ID_ALIASES` —
  left untouched; out of scope for this fix, not introduced by it)
