# Trend History Implementation Plan

> For agentic workers: use executing-plans inline, with one final independent review. The user explicitly requested implementation of the already presented archive/history/comparison design.

**Goal:** Preserve and expose evidence-bound evolution of company judgments and homepage directions.
**Architecture:** Extend the existing versioned report pipeline with optional evolution metadata for immutable legacy compatibility, deterministic archive replay and public history snapshots, then render folded history and comparable direction signals.
**Tech Stack:** Python standard library, existing pytest, plain browser JavaScript and CSS, existing Pages.
**Spec:** docs/TREND_HISTORY.md

## Global Constraints

- Original worktree stays untouched; work only in the unique /tmp clone.
- No model API, credential reads, raw article copies or secret values.
- Old published reports are immutable; retrospective labels are dated sidecar annotations.
- No automatic semantic classification from wording, number of stories or event status.
- Unknown dates remain null; evidence gaps are not inactivity; initial/baseline remains an assistant draft.
- Preserve core homepage hierarchy; all new controls live in folded panels.

## Review Focus

- Null judgments must inherit the prior judgment and its original timestamp.
- Repeated daily/weekly evidence must not imply independent product launches.
- A new publisher must not stage unrelated files or trust local-only history metadata.
- Corrupt/missing archive parents must not silently produce plausible history.
- Delayed/missing history responses and untrusted text must not break current UI.

### Task 1: Evolution contract and immutable replay

**Files:** scripts/trend_history.py, scripts/trend_reports.py, tests/test_trend_history.py, config/trend_directions.json
**Interfaces:** validate_evolution(raw), build_history(data_dir, extra_report=None), write_history(data_dir, payload), history_context(data_dir).

- [ ] Write tests for legacy replay, retained timestamps, explicit labels, cross-company evidence, corrupt parent and no inferred strengthening.
- [ ] Run `python3 -m pytest -q tests/test_trend_history.py`; expected missing module/failing behavior.
- [ ] Implement fixed direction ids, strict public-field validation and ordered report replay with before/after and evidence.
- [ ] Integrate prepare history context and mandatory evolution for new prepared inputs; maintain legacy archive validation unchanged.
- [ ] Run `python3 -m pytest -q tests/test_trend_history.py tests/test_trend_reports.py`; expected green.
- [ ] Commit only contract, replay and tests with `git add -- scripts/trend_history.py scripts/trend_reports.py tests/test_trend_history.py config/trend_directions.json`.

### Task 2: Automatic publishing and retrospective annotations

**Files:** scripts/publish_trend_report.py, data/trends/annotations.json, .github/workflows/trend-reports.yml, docs/TREND_REPORTS.md, tests/test_trend_history.py, tests/test_trend_reports.py
**Interfaces:** history manifest/latest_report_id and history snapshot/report_id; publisher stages exactly current archive/latest/index/current history snapshot.

- [ ] Write publisher isolation and online history mismatch tests, run them and observe failure.
- [ ] Extend whitelist and verification to current history; build in remote isolated clone, not from arbitrary caller state.
- [ ] Add dated retrospective labels for four existing issues from the archived judgments/reasons only; preserve original hashes. Missing semantics remain unclassified.
- [ ] Update runbook so future tasks use prior weeks and explicit evolution labels; rebuild derived history.
- [ ] Run targeted tests and `trend_reports.py check`; expected green and unchanged original archive hashes.
- [ ] Commit scoped publisher, data, workflow and runbook changes.

### Task 3: Folded history and comparable directions

**Files:** assets/trend-history.js, assets/trend-reports.js, assets/perspective.js, assets/perspective.css, index.html, legacy-radar.html, Dockerfile, scripts/package-public-site.ts, scripts/sync-public-site.py, tests/trend-history.browser.mjs
**Interfaces:** radarTrendHistory.set(index), company(slot,id), overview(slot), snapshot lazy fetch by safe report id.

- [ ] Write browser checks for company before/after, retrospective marker, direction selection across institutions, missing data, pure text and mobile overflow.
- [ ] Implement lazy folded UI and connect index load without hiding existing judgments on history failure.
- [ ] Maintain all explicit deployment asset/data allowlists and cache versions; retain homepage core CSS.
- [ ] Run browser checks desktop/mobile and inspect screenshots; run relevant Python and syntax checks.
- [ ] Commit scoped UI and packaging changes, run final independent branch review and fix substantive findings.
- [ ] Publish authorized changes, await Actions/Pages and verify online current report id plus history and actual UI.
