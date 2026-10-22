# Radar daily and weekly trends implementation plan

> Execute inline against the already approved chat design. Use the existing local Codex subscription; no model API, OAuth export, paid call, or cloud login replication.

Goal: update eight company briefs and homepage judgments from verified public evidence with dated daily/weekly archives.
Architecture: existing topic snapshots → bounded candidate bundle + prior editorial baseline → Codex verifies original sources and writes a structured report → strict validator → allowlisted data-only isolated publish → existing Pages. Keep collector and public projection schemas unchanged.

Constraints: Asia/Shanghai; cloud collection starts 10:40; local editorial task starts 11:10 and requires this Mac/app online. Daily window ends at source snapshot time; weekly covers the previous completed Shanghai Monday–Sunday. Initial approved homepage sample may be published as an explicit material daily update. Undated documents and late discoveries are supplements. Report generated time never supplies publication time. No report is generated merely from title counts. All eight companies are covered or explicitly marked insufficient. Failure preserves prior prose. No Hi/email/other messages; notify only meaningful completion/change/failure.

- [x] Add candidate preparation, strict public report schema, evidence/date/ref/secret validation, deterministic report ids, immutable issue archives, stale-parent protection, atomic merge.
- [x] Add isolated data-only publisher with fixed allowlist and integration tests for races and secret rejection.
- [x] Render daily/weekly prose in existing company slots and homepage; retain static fallbacks and stale timestamps; package preview data.
- [x] Add workflow validation and deployment trigger for trend data; document operation and complete representative real-data bootstrap.
- [x] Run Python tests, browser checks for eight pages and homepage, staged secret/allowlist scan, publish and verify online ids.
- [x] Create local heartbeat using current subscription and the versioned runbook, without changing existing WeChat automation.

Validation ledger: initial full Python run 538 passed (including 22 new tests); added report and Meta/Muse tests pass; real-data homepage and eight company routes, weekly date label, citations and literal HTML injection browser checks passed. Current weekly data intentionally absent until the first completed period. Ruling: source hostname alone is not part of existing topic text matching; scoped Muse names are added without broadening generic matching. Browser first failures were missing preview public-news.json and absent remote Gemini/Meta brief mappings; both corrected.

Final independent review found two important issues, reproduced RED: overlapping daily windows counted one event new twice; a field-valid oversized report could persist an invalid merged state. Fixed with a 35-day event/ref index supplied to authoring and enforced before write, plus full merged-state validation before any archive/latest mutation. Added regressions and verified GREEN.

Post-publication: public report_id readback and production browser checks passed for homepage and all eight company pages. Active local heartbeat radar-2 runs daily at 11:10 Asia/Shanghai, with completed-week generation from 2026-W43. Docker CI exposed an omitted asset in its explicit COPY allowlist; added trend-reports.js only, preserving the source privacy boundary. Final full Python run: 546 passed.

The full-architecture gate spent its checkout phase fetching a roughly 9 GB repository history. Added the pinned checkout action's supported blob:none filter while retaining fetch-depth:0; migration commit history remains available and historical file bodies are fetched on demand. Docker regression already passed.

Completion evidence: https://github.com/LeaiFish/ai-news-radar/actions/runs/39749164753 passed check and Docker jobs on 341282d4. Test Radar and Validate Trend Reports passed. Production report_id equals 6e24abff5da1a9c584499588bb53763abd3630041ca5f83a56afcc0374cdedd6; homepage and all eight company routes passed browser checks, including citations, weekly labels and mobile width. Original user working-tree changes were not staged or published. The first timed daily run and completed weekly run are future executions, not claimed as already verified. Scoped frontend Muse aliases match the topic configuration rather than generic music/museum text.
