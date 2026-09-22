# External corpus: Amb2rZhou / ai-frontier-insight

**Origin:** https://github.com/Amb2rZhou/ai-frontier-insight (public)

This directory holds a **third-party** historical copy of daily briefs and weekly
reports from that project. Content is imported as-is (JSON + companion Markdown)
for **internal trend reference and AI context**, not as native AI News Radar
output.

## Scope of this import

| Kind | Source path (upstream) | Local path |
| --- | --- | --- |
| Daily brief JSON | `data/daily/YYYY-MM-DD/brief.json` | `daily/YYYY-MM-DD/brief.json` |
| Daily Markdown (optional) | `data/daily/YYYY-MM-DD/YYYY-MM-DD_daily.md` | same basename under `daily/YYYY-MM-DD/` |
| Weekly JSON + Markdown | `data/weekly/YYYY-Www.json` / `.md` | `weekly/YYYY-Www.json` / `.md` |

Upstream `.docx` binaries were not imported.

See `manifest.json` for the exact date/week lists and byte totals for this copy.

**Parse note:** upstream `data/weekly/2026-W11.json` is not valid JSON (unescaped
quotes inside string fields). It is kept **verbatim** here; use `2026-W11.md`
for that week. Listed under `manifest.json` → `parse_notes.weekly_invalid_json`.

## Attribution and product rules

- Analyst prose belongs to the upstream project; do **not** rewrite or paraphrase
  it in this tree.
- Do **not** surface these files in the public UI as Lea’s native 「竞争概览」
  (or equivalent) judgments. They are archive-only reference material.
- Prefer reading `brief.json` / weekly `.json` for machine use; Markdown essays
  are optional human-readable companions.

## How this relates to radar’s own archives

Radar’s first-party story archives live under:

- `data/archive/daily/YYYY-MM-DD.json`
- `data/archive/weekly/YYYY-Www.json`

Those are produced by `scripts/story_archive.py` from the live radar pipeline.
This `external/frontier-insight/` tree is a separate corpus with different
schema and authorship. Trend jobs may join them by calendar date / ISO week, but
must keep provenance distinct.
