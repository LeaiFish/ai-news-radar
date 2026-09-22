# Private bridge ingress

This directory is the **only** supported ingress for sanitized public post
metadata produced by an off-repo private X cookie scraper.

## Rules

- **Never** put cookies, `auth_token`, `ct0`, Playwright `storage_state`,
  browser exports, or any credentials here.
- Only commit or upload sanitized public tweet fields (id, url, username, text,
  published, likes, retweets) as `x-items.json`.
- The scraper that holds cookies lives outside this public repository.

## File

Expected path: `data/bridge/x-items.json` (`schema: x_bridge_v1`).

Operators can also set the GitHub Actions secret `X_BRIDGE_ITEMS_B64` (base64 of
the same JSON). When that secret is non-empty, the update workflow writes it to
`x-items.json` for the run and it takes precedence over any committed file.

`x-items.json` is gitignored so Actions secret material and local scrapes are
not committed by accident. A private scraper may still force-add a sanitized
file if that is the chosen transport.
