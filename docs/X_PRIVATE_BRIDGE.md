# X Private Cookie Bridge

Private cookie scrapes of X/Twitter stay **off this public repository**. The only
ingress into AI News Radar is sanitized public tweet metadata.

## Ingress

1. **Committed / force-added file** (optional): `data/bridge/x-items.json`
2. **GitHub Actions secret** (preferred for operators): `X_BRIDGE_ITEMS_B64`
   — base64 of the same JSON. When non-empty, the update workflow writes it to
   `data/bridge/x-items.json` before `scripts/update_news.py` runs and
   **overwrites** any committed file for that run.

See `data/bridge/README.md` for directory rules.

## Schema (`x_bridge_v1`)

```json
{
  "schema": "x_bridge_v1",
  "generated_at": "ISO-8601 UTC",
  "source": "private_x_cookie_bridge",
  "items": [
    {
      "id": "tweet id string",
      "url": "https://x.com/{user}/status/{id}",
      "username": "handle without @",
      "text": "tweet text",
      "published": "ISO-8601",
      "likes": 0,
      "retweets": 0
    }
  ]
}
```

Only these public fields are read. Keys whose names look like cookies, tokens,
`auth`, `ct0`, or `storage_state` are stripped and never stored in radar output.

## Pipeline behavior

- Site id: `x_bridge` · display name: `X（私有桥）`
- Items pass through the same archive / 24h window / AI relevance path as other
  sources and can appear in `stories-merged.json`.
- `source-status.json` reports ok / item_count / error when the file is present.
- Missing file or unset secret: no bridge source entry; other sources unchanged.
- Official X API (`X_BEARER_TOKEN`) and SocialData remain separate, disabled
  unless their own secrets are configured.

## Do not

- Commit Playwright, cookie parsers, or credentials to this repo.
- Enable SocialData / X API by default for this path.
- Put cookies or `storage_state` under `data/bridge/`.
