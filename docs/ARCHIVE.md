# Story Archives (Daily + Weekly)

Historical story snapshots for trend analysis. The live 「今日」 window is still
`data/stories-merged.json` (+ `data/daily-brief.json`); archives keep prior days
from being discarded when that rolling window refreshes.

Timezone for calendar days and ISO weeks: **Asia/Shanghai** (same convention as
WaytoAGI and other dated payloads in this repo).

## Layout

```text
data/
  stories-merged.json              # live rolling window (unchanged)
  archive.json                     # item-level rolling buffer (existing, ~21d)
  archive/
    daily/
      YYYY-MM-DD.json              # e.g. data/archive/daily/2026-09-22.json
    weekly/
      YYYY-Www.json                # e.g. data/archive/weekly/2026-W39.json
```

Example paths after a successful update on 2026-09-22 (Shanghai):

- Daily: `data/archive/daily/2026-09-22.json`
- Weekly: `data/archive/weekly/2026-W39.json`

## Daily file

Written on each successful `scripts/update_news.py` run.

| Field | Meaning |
| --- | --- |
| `archive_date` | Shanghai calendar date |
| `generated_at` | UTC timestamp of the snapshot that produced this file |
| `window_hours` | Same window as the live merge (default 24) |
| `story_count` | Number of compact stories |
| `projection` | `compact_v1` |
| `live_snapshot` | Pointer: `data/stories-merged.json` for full nested items in the live window |
| `stories[]` | Compact rows (see below) |

### Projection choice: compact (not full stories)

Full `stories-merged.json` rows nest `items` / `sources` / `primary_item` and are
~0.5–1 MB per day. Committing full copies every refresh would bloat git/Pages.
Archives therefore store a **compact** projection:

- `story_id`, `title`, `url`, `primary_url`
- `source`, `source_names`, `source_count`
- `importance_score`, `importance_label`, `category`, `reasons`
- `earliest_at`, `latest_at`
- `company_topics`, `lens_topics` (topic ids from `config/topics.json` keyword match)

Enough for trend counts and top-story lists; rebuild richer views from the live
file only while the story is still inside the window.

### Immutability

- **Same Shanghai day**: re-runs refresh that day’s file (hourly Actions).
- **Past days**: never overwritten unless `--force-archive`.
- Existing item-level `data/archive.json` is unrelated and unchanged.

## Weekly file

Idempotent rollup rebuilt from `data/archive/daily/*.json` for that ISO week
(`YYYY-Www`, ISO week-year). Safe to delete and regenerate.

Contains:

- `daily_dates`, `story_count`, `unique_story_count`
- `counts.by_company_topic` / `by_lens_topic` / `by_importance_label` / `by_source_count_bucket` (`1` / `2` / `3+`)
- `top_stories`: up to 40 unique `story_id`s ranked by importance then multi-source

## How a future trend job should read

1. Prefer **weekly** rollups for coarse charts (company/lens/importance over time).
2. Drill into **daily** files for story-level series or to rebuild a week.
3. Use `story_id` + `archive_date` as the durable key; do not assume the live
   `stories-merged.json` still holds that story.
4. Topic ids follow `config/topics.json`; recount historical dailies after big
   keyword edits if you need consistent labels.

```bash
# Normal update also writes/refreshes today + rebuilds this ISO week
python scripts/update_news.py --output-dir data --window-hours 24

# Repair / rewrite a past day (rare)
python scripts/update_news.py --output-dir data --window-hours 24 --force-archive
```

GitHub Actions (`update-news.yml`) already runs `git add data/`, so new files
under `data/archive/` commit with the live snapshot.
