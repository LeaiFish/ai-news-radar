#!/usr/bin/env python3
"""Discover public WeChat links without a login, or verify a Pages deployment."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
from threading import Event
import time

import requests

try:
    from scripts.wechat_sources import canonical_url, targets
except ModuleNotFoundError:
    from wechat_sources import canonical_url, targets

SEARCH_URL = "https://mcp.exa.ai/mcp"
SITE_URL = "https://leaifish.github.io/ai-news-radar/"
URL_PATTERN = re.compile(r'https?://mp\.weixin\.qq\.com/s(?:/[A-Za-z0-9_-]+|\?[^\s<>"\\]+)')


def rpc_result(text):
    """Read JSON or complete SSE events, including multiline data events."""
    messages = []
    if text.lstrip().startswith("{"):
        messages.append(json.loads(text))
    else:
        for event in re.split(r"\r?\n\r?\n", text.strip()):
            data = [line[5:].lstrip(" ") for line in event.splitlines() if line.startswith("data:")]
            if data:
                messages.append(json.loads("\n".join(data)))
    for message in messages:
        if message.get("error"):
            raise ValueError("search_rpc_error")
        result = message.get("result")
        if isinstance(result, dict):
            if result.get("isError"):
                raise ValueError("search_provider_error")
            content = result.get("content")
            if not isinstance(content, list):
                raise ValueError("search_invalid_content")
            return "\n".join(c["text"] for c in content if c.get("type") == "text" and isinstance(c.get("text"), str))
    raise ValueError("search_missing_result")


def search_articles(account, now, *, broad=False, post=requests.post):
    month = "" if broad else now.strftime("%Y年%m月")
    query = f'{account} {month} 发布 更新 官方公众号 site:mp.weixin.qq.com/s/'
    response = post(SEARCH_URL, headers={"Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"}, json={"jsonrpc": "2.0", "id": 1,
        "method": "tools/call", "params": {"name": "web_search_exa", "arguments": {
            "query": query, "numResults": 5,
            "objective": f"寻找{account}官方微信公众号公开文章原文链接，优先最近30天发布或产品更新。排除媒体转载。返回原文链接；账号和日期将另行核验，不能推断或编造。"
        }}}, timeout=(5, 25))
    response.raise_for_status()
    response.encoding = "utf-8"
    content = rpc_result(response.text)
    urls = []
    for match in URL_PATTERN.finditer(content):
        try:
            url = canonical_url(html.unescape(match[0]))
        except ValueError:
            continue
        if url not in urls:
            urls.append(url)
    return urls[:5]


def discover(now, *, search=search_articles, companies=None):
    companies = targets() if companies is None else companies
    jobs = [(company, account) for company, names in companies.items() for account in names]
    unavailable = Event()
    def one(job):
        company, account = job
        if unavailable.is_set():
            return {"account_name": account, "ok": False, "error": "search_backend_unavailable"}, []
        try:
            urls = search(account, now)
            if not urls:
                urls = search(account, now, broad=True)
            return {"account_name": account, "ok": True}, [
                {"company_id": company, "account_name": account, "url": url} for url in dict.fromkeys(urls[:10])]
        except (ValueError, requests.RequestException) as exc:
            # Never persist provider text, headers, cookies, or full article bodies.
            code = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
            if isinstance(exc, requests.HTTPError) and exc.response is not None:
                code = f"search_http_{exc.response.status_code}"
                if exc.response.status_code in {401, 403, 429}:
                    unavailable.set()
            if code in {"search_provider_error", "search_rpc_error"}:
                unavailable.set()
            return {"account_name": account, "ok": False, "error": code}, []
    with ThreadPoolExecutor(max_workers=2) as pool:
        checked = list(pool.map(one, jobs))
    return {"searches": [s for s, _ in checked], "candidates": [c for _, rows in checked for c in rows]}


def aihot_candidates(now, *, companies=None, get=requests.get, max_pages=10):
    """Discover URLs only; publisher identity and dates still require original-page verification."""
    companies = targets() if companies is None else companies
    candidates, seen, counts = [], set(), {}
    cursor, pages, more = None, 0, True
    try:
        while more and pages < max_pages:
            params = {"mode": "all", "window": "7d", "by": "published", "limit": 100}
            if cursor:
                params["cursor"] = cursor
            response = get("https://aihot.news/api/v1/items", params=params,
                headers={"User-Agent": "AI-News-Radar/0.8 aihot-api/2.0.0"}, timeout=(5, 25))
            response.raise_for_status()
            data = response.json()
            if data.get("schemaVersion") != 1 or not isinstance(data.get("items"), list) or not isinstance(data.get("page"), dict):
                raise ValueError("aihot_invalid_response")
            pages += 1
            for item in data["items"]:
                if not isinstance(item, dict):
                    continue
                source = item.get("source")
                name = source.get("name", "") if isinstance(source, dict) else ""
                if not isinstance(name, str) or not name.startswith("公众号："):
                    continue
                name = name.removeprefix("公众号：").strip()
                # Parentheses in the aggregator label are descriptions, never
                # proof of account ownership. Reject merely matching prefixes.
                possible = [(company, account) for company, accounts in companies.items() for account in accounts
                            if name == account or name.startswith(account + "（") or name.startswith(account + " (")]
                if not possible:
                    continue
                company, account = max(possible, key=lambda row: len(row[1]))
                links = item.get("links") if isinstance(item.get("links"), dict) else {}
                try:
                    url = canonical_url(links.get("original"))
                except ValueError:
                    continue
                key = (company, account, url)
                if key in seen or counts.get(account, 0) >= 10:
                    continue
                seen.add(key)
                counts[account] = counts.get(account, 0) + 1
                candidates.append({"company_id": company, "account_name": account, "url": url})
            page = data["page"]
            more = bool(page.get("hasMore"))
            next_cursor = page.get("nextCursor")
            if more and (not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor):
                raise ValueError("aihot_invalid_cursor")
            cursor = next_cursor
        return {"ok": True, "pages": pages, "truncated": more, "candidates": candidates}
    except (ValueError, requests.RequestException) as exc:
        return {"ok": False, "pages": pages, "truncated": more, "candidates": candidates,
                "error": str(exc) if isinstance(exc, ValueError) else type(exc).__name__}


def verify_publication(snapshot, *, timeout=300, get=requests.get, clock=time.monotonic, sleep=time.sleep):
    expected = snapshot["last_run"]["at"]
    deadline = clock() + timeout
    while clock() < deadline:
        try:
            response = get(SITE_URL + "data/source-status.json", params={"verify": time.time_ns()}, timeout=(5, 15))
            response.raise_for_status()
            status = next((s for s in response.json().get("sites", []) if s.get("site_id") == "wechat_bridge"), None)
            if status and status.get("discovery", {}).get("at") == expected:
                # Header check avoids downloading the entire reader just to check availability.
                with get(SITE_URL, stream=True, timeout=(5, 15)) as page:
                    page.raise_for_status()
                return status
        except (requests.RequestException, ValueError):
            pass
        sleep(10)
    raise ValueError("pages_snapshot_verification_timeout")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify-deployment", type=Path)
    args = parser.parse_args()
    try:
        if args.verify_deployment:
            status = verify_publication(json.loads(args.verify_deployment.read_text(encoding="utf-8")))
            print(json.dumps({"deployed": True, "snapshot_at": status["discovery"]["at"],
                              "item_count": status["item_count"], "collection_ok": status["ok"]}))
            return 0
        if not args.output:
            parser.error("--output or --verify-deployment is required")
        now = datetime.now(timezone.utc)
        payload = discover(now)
        supplemental = aihot_candidates(now)
        # Prefer targeted search candidates, then fill the per-account budget
        # with public aggregator URLs. Neither path bypasses the verifier.
        counts, seen, combined = {}, set(), []
        for row in payload["candidates"] + supplemental["candidates"]:
            key = (row["company_id"], row["account_name"], row["url"])
            account = row["account_name"]
            if key not in seen and counts.get(account, 0) < 10:
                seen.add(key)
                counts[account] = counts.get(account, 0) + 1
                combined.append(row)
        payload["candidates"] = combined
        payload["supplemental_discovery"] = {k: v for k, v in supplemental.items() if k != "candidates"}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        failed = sum(not s["ok"] for s in payload["searches"])
        print(json.dumps({"target_accounts": len(payload["searches"]), "searched_accounts": len(payload["searches"]) - failed, "failed_searches": failed,
                          "candidates": len(payload["candidates"]), "supplemental_discovery": payload["supplemental_discovery"]}))
        return 2 if failed or not supplemental["ok"] else 0
    except (OSError, ValueError, requests.RequestException) as exc:
        print(json.dumps({"error": str(exc) if isinstance(exc, ValueError) else type(exc).__name__}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
