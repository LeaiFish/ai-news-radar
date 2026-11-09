# 2026-11-09 publication recovery

The last online snapshot was generated at `2026-11-06T22:07:14.356495Z`.
The local weekday collector produced public metadata at
`2026-11-09T03:11:18.315340Z`, with 84 retained verified original URLs.
Its incomplete list coverage remains a separate issue.

A real dispatch of the existing free-only `update-news.yml` workflow, with
`refresh_wechat=false`, returned HTTP 422:

> Actions has been disabled for this repository.

Readbacks show repository Actions `enabled=true`, the workflow `state=active`,
and the repository neither archived nor disabled. The current account has
repository admin permission. Those settings do not establish that GitHub will
permit a workflow run. GitHub documents a separate GitHub-controlled disabled
state for which changing the ordinary settings does not restore access:
https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository

The precise reason for GitHub's disabled state remains unknown; do not label it
as billing, inactivity, a token problem or a session-save fault. Contact GitHub
Support for review. Do not evade this state by moving the workflow or changing
hosting. No account settings, spending limits or external support messages were
changed/sent by this repair.

`ensure_trend_snapshot.py` now gives a fixed, actionable error code for this
response and a safe stage name for other command failures. It does not echo
subprocess stderr or pretend an old snapshot satisfies today's freshness gate.
The separate local Xcode toolchain-selection issue was worked around only for
this run by selecting the already installed Command Line Tools; no license was
accepted or system configuration modified.

The two requested historical records are prepared with original dates:

- Claude Duet's primary David Sutton personal post: `2026-11-06T19:20:30Z`.
  The Ado quote is an alias of that same original, not another event or an
  institutional source. The first feature release date is unverified.
- IT之家's Doubao Work allowance article: `2026-11-06T08:57:38Z`.
  Removing the five-hour short window does not remove the weekly plan quota.

Their corrections, archive rows and existing company-topic projections are
prepared; offline public export contains exactly one of each original. Global
snapshot timestamps remain unchanged because this bounded historical backfill
is not a new complete news collection.

The Claude cloud-environment company original was separately read:
https://x.com/ClaudeDevs/status/2118795192090386454
It was published at `2026-11-06T19:58:33Z`. The post describes repo dependency,
network and API-key setup, then saving the environment for reuse on Pro, Max
and Ultra. Its time is the post date, not evidence of a first feature launch.
No third news record was added in this repair.

After GitHub restores Actions, use the existing workflow with
`refresh_wechat=false`; the already prepared bridge snapshot can be reused.
Wait for the news and Pages runs, then compare generation timestamps across
raw/archive/public layers and inspect the two reader cards before declaring
online acceptance. A successful code push alone is not deployment.
