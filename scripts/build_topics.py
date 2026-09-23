#!/usr/bin/env python3
"""Build static Topics payloads from topic definitions + existing news JSON.

Matching is a keyword/alias heuristic on title, summary, source and tags — not a
classifier. An item may appear in multiple topics. See config/topics.json.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "topics.json"
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_PAGES_DIR = ROOT / "topics"

TOPIC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
CURATED_SITE_IDS = {"official_ai", "aihot", "curated_media", "aibreakfast"}
MAX_SUMMARY_CHARS = 280
DEFAULT_MAX_ITEMS = 80

TEXT_FIELDS = (
    "title",
    "title_zh",
    "title_en",
    "title_original",
    "summary",
    "source",
    "source_name",
    "site_name",
    "category",
    "aihot_category",
    "tags",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_topic_config(path: Path) -> dict[str, Any]:
    config = load_json(path)
    if not config:
        raise FileNotFoundError(f"Topic config not found or invalid: {path}")
    topics = config.get("topics")
    if not isinstance(topics, list) or not topics:
        raise ValueError(f"{path} must define a non-empty topics array")
    seen: set[str] = set()
    for topic in topics:
        if not isinstance(topic, dict):
            raise ValueError("Each topic must be an object")
        topic_id = str(topic.get("id") or "").strip()
        if not TOPIC_ID_RE.match(topic_id):
            raise ValueError(f"Invalid topic id {topic_id!r}; use lowercase kebab-case")
        if topic_id in seen:
            raise ValueError(f"Duplicate topic id: {topic_id}")
        seen.add(topic_id)
        if not str(topic.get("name") or "").strip():
            raise ValueError(f"Topic {topic_id} needs a name")
        if not str(topic.get("description") or "").strip():
            raise ValueError(f"Topic {topic_id} needs a description")
        if not str(topic.get("group") or "").strip():
            raise ValueError(f"Topic {topic_id} needs a group")
    groups = config.get("groups") or []
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"{path} must define a non-empty groups array")
    return config


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return " ".join(_flatten_text(part) for part in value if part)
    if isinstance(value, dict):
        return " ".join(_flatten_text(part) for part in value.values() if part)
    return str(value)


def haystack_text(record: dict[str, Any]) -> str:
    """Join the fields a maintainer can reasonably expect to match against."""
    chunks: list[str] = []
    for key in TEXT_FIELDS:
        text = _flatten_text(record.get(key)).strip()
        if text:
            chunks.append(text)
    primary = record.get("primary_item")
    if isinstance(primary, dict):
        chunks.append(haystack_text(primary))
    for nested_key in ("items", "sources"):
        nested = record.get(nested_key)
        if isinstance(nested, list):
            for child in nested:
                if isinstance(child, dict):
                    chunks.append(haystack_text(child))
    return "\n".join(chunk for chunk in chunks if chunk)


def term_matches(term: str, text: str) -> bool:
    needle = (term or "").strip()
    if not needle or not text:
        return False
    if CJK_RE.search(needle):
        return needle.casefold() in text.casefold()
    pattern = r"(?<![A-Za-z0-9])" + re.escape(needle) + r"(?![A-Za-z0-9])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def record_matches_topic(record: dict[str, Any], topic: dict[str, Any]) -> bool:
    text = haystack_text(record)
    if not text:
        return False
    excludes = [str(item) for item in (topic.get("exclude") or []) if str(item).strip()]
    if any(term_matches(term, text) for term in excludes):
        return False
    keywords = [str(item) for item in (topic.get("keywords") or []) if str(item).strip()]
    if any(term_matches(term, text) for term in keywords):
        return True
    patterns = [str(item) for item in (topic.get("patterns") or []) if str(item).strip()]
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        except re.error:
            continue
    return False


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def record_time_iso(record: dict[str, Any]) -> str:
    for key in ("latest_at", "published_at", "earliest_at", "first_seen_at", "last_seen_at"):
        value = record.get(key)
        if value:
            return str(value)
    primary = record.get("primary_item")
    if isinstance(primary, dict):
        return record_time_iso(primary)
    return ""


def canonicalize_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except ValueError:
        return raw
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    if path.endswith("/") and path != "/":
        path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), host, path, "", "", ""))


def record_identity(record: dict[str, Any]) -> str:
    url = canonicalize_url(str(record.get("url") or record.get("primary_url") or ""))
    if not url:
        primary = record.get("primary_item")
        if isinstance(primary, dict):
            url = canonicalize_url(str(primary.get("url") or ""))
    if url:
        return f"url:{url}"
    story_id = str(record.get("story_id") or "").strip()
    if story_id:
        return f"story:{story_id}"
    item_id = str(record.get("id") or "").strip()
    if item_id:
        return f"id:{item_id}"
    return f"title:{(record.get('title') or '').strip().casefold()}"


def is_curated_record(record: dict[str, Any], curated_ids: set[str]) -> bool:
    story_id = str(record.get("story_id") or "").strip()
    if story_id and story_id in curated_ids:
        return True
    site_id = str(record.get("site_id") or "").strip()
    if site_id in CURATED_SITE_IDS:
        return True
    primary = record.get("primary_item")
    if isinstance(primary, dict) and str(primary.get("site_id") or "") in CURATED_SITE_IDS:
        return True
    if int(record.get("source_count") or 0) >= 2:
        return True
    if record.get("_pool") == "brief":
        return True
    return False


def richer_record(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Prefer clustered stories / curated rows over raw archive items."""
    def score(record: dict[str, Any]) -> tuple[int, int, int]:
        is_story = 1 if record.get("story_id") else 0
        curated = 1 if record.get("curated") else 0
        extras = sum(
            1
            for key in ("summary", "title_zh", "recommend_reason_zh", "source_count")
            if record.get(key)
        )
        return (is_story, curated, extras)

    return left if score(left) >= score(right) else right


def truncate(text: str, limit: int = MAX_SUMMARY_CHARS) -> str:
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def slim_item(record: dict[str, Any], curated_ids: set[str]) -> dict[str, Any]:
    primary = record.get("primary_item") if isinstance(record.get("primary_item"), dict) else {}
    title = (
        record.get("title")
        or primary.get("title_zh")
        or primary.get("title")
        or ""
    )
    title_en = record.get("title_en") or primary.get("title_en") or ""
    url = record.get("primary_url") or record.get("url") or primary.get("url") or ""
    summary = (
        record.get("summary")
        or primary.get("summary")
        or primary.get("recommend_reason_zh")
        or ""
    )
    source = record.get("source") or primary.get("source") or ""
    source_name = record.get("source_name") or primary.get("source_name") or source
    site_id = record.get("site_id") or primary.get("site_id") or ""
    recommend = record.get("recommend_reason_zh") or primary.get("recommend_reason_zh") or ""
    source_count = int(record.get("source_count") or (len(record.get("sources") or []) if record.get("sources") else 1) or 1)
    item = {
        "id": record.get("story_id") or record.get("id") or "",
        "story_id": record.get("story_id") or None,
        "title": str(title).strip(),
        "title_en": str(title_en).strip() or None,
        "url": str(url).strip(),
        "summary": truncate(str(summary)),
        "recommend_reason_zh": truncate(str(recommend)) or None,
        "source": str(source).strip(),
        "source_name": str(source_name).strip(),
        "site_id": str(site_id).strip(),
        "published_at": record_time_iso(record),
        "source_count": source_count,
        "curated": is_curated_record(record, curated_ids),
    }
    return item


def _load_list(payload: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def collect_pools(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    stories_payload = load_json(data_dir / "stories-merged.json")
    brief_payload = load_json(data_dir / "daily-brief.json")
    latest_payload = load_json(data_dir / "latest-24h.json")
    archive_payload = load_json(data_dir / "archive.json")

    stories = _load_list(stories_payload, "stories")
    brief = _load_list(brief_payload, "items")
    latest = _load_list(latest_payload, "items", "items_ai")
    archive = _load_list(archive_payload, "items")

    for record in stories:
        record["_pool"] = "stories"
    for record in brief:
        record["_pool"] = "brief"
    for record in latest:
        record["_pool"] = "latest"
    for record in archive:
        record["_pool"] = "archive"

    return {
        "stories": stories,
        "brief": brief,
        "latest": latest,
        "archive": archive,
        "generated_at": (
            stories_payload.get("generated_at")
            or brief_payload.get("generated_at")
            or latest_payload.get("generated_at")
            or archive_payload.get("generated_at")
            or utc_now_iso()
        ),
    }


def curated_story_ids(brief_items: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for record in brief_items:
        story_id = str(record.get("story_id") or "").strip()
        if story_id:
            ids.add(story_id)
    return ids


def match_topic_items(
    topic: dict[str, Any],
    pools: dict[str, list[dict[str, Any]]],
    curated_ids: set[str],
    max_items: int,
) -> tuple[list[dict[str, Any]], int]:
    wanted_pools = topic.get("pools") or ["stories", "brief", "latest"]
    merged: dict[str, dict[str, Any]] = {}
    for pool_name in wanted_pools:
        for record in pools.get(pool_name, []):
            if not record_matches_topic(record, topic):
                continue
            slim = slim_item(record, curated_ids)
            if not slim.get("title"):
                continue
            identity = record_identity(record) or record_identity(slim)
            existing = merged.get(identity)
            merged[identity] = slim if existing is None else richer_record(existing, slim)

    items = list(merged.values())
    total = len(items)

    def sort_key(item: dict[str, Any]) -> tuple[int, datetime]:
        ts = parse_time(item.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc)
        return (1 if item.get("curated") else 0, ts)

    items.sort(key=sort_key, reverse=True)
    if max_items > 0:
        items = items[:max_items]
    items.sort(
        key=lambda item: parse_time(item.get("published_at")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return items, total


def build_topics_payload(
    config: dict[str, Any],
    pools: dict[str, list[dict[str, Any]]],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    max_items = int(config.get("max_items_per_topic") or DEFAULT_MAX_ITEMS)
    curated_ids = curated_story_ids(pools.get("brief") or [])
    topic_rows: list[dict[str, Any]] = []
    detail_by_id: dict[str, dict[str, Any]] = {}

    # Hub cards follow this array order within each group. Do not sort by name or count.
    for topic in config.get("topics") or []:
        items, total = match_topic_items(topic, pools, curated_ids, max_items)
        latest = items[0] if items else {}
        summary = {
            "id": topic["id"],
            "name": topic["name"],
            "description": topic["description"],
            "group": topic["group"],
            "item_count": total,
            "listed_count": len(items),
            "latest_title": latest.get("title") or "",
            "latest_published_at": latest.get("published_at") or "",
            "items_url": f"data/topics/{topic['id']}.json",
        }
        if topic.get("filter"):
            summary["filter"] = topic["filter"]
        topic_rows.append(summary)
        detail_by_id[topic["id"]] = {
            **summary,
            "generated_at": generated_at or pools.get("generated_at") or utc_now_iso(),
            "items": items,
        }

    return {
        "generated_at": generated_at or pools.get("generated_at") or utc_now_iso(),
        "config_version": config.get("version"),
        "matching": {
            "method": "keyword_alias_heuristic",
            "fields": list(TEXT_FIELDS),
            "limitations": (
                "主题用维护者配置的关键词/别名（以及可选正则）去匹配标题、摘要、来源和标签，"
                "不是语义分类。短英文词走词边界，中文走子串；同一条新闻可以出现在多个主题里。"
                "公司主题还会扫描 archive.json 做更长窗口；较宽的技术主题默认只用 24 小时故事池，减少误伤。"
            ),
        },
        "groups": config.get("groups") or [],
        "topic_count": len(topic_rows),
        "topics": topic_rows,
        "_details": detail_by_id,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_topics_payload(
    data_dir: Path,
    *,
    config_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    config = load_topic_config(config_path or DEFAULT_CONFIG)
    pools = collect_pools(data_dir)
    payload = build_topics_payload(config, pools, generated_at=generated_at or pools.get("generated_at"))
    details = payload.pop("_details", {})
    write_json(data_dir / "topics.json", payload)
    topics_dir = data_dir / "topics"
    if topics_dir.exists():
        for stale in topics_dir.glob("*.json"):
            if stale.stem not in details:
                stale.unlink()
    for topic_id, detail in details.items():
        write_json(topics_dir / f"{topic_id}.json", detail)
    payload["_details"] = details
    return payload


PAGE_TEMPLATE = """<!doctype html>
<html lang="zh-CN" data-radar-surface="topics"{topic_attr} data-root="{root}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <meta name="description" content="{description}" />
    <link rel="icon" href="{root}assets/logo.svg" type="image/svg+xml" />
    <link rel="stylesheet" href="{root}assets/styles.css?v=ui20260923a" />
    <link rel="stylesheet" href="{root}assets/topics.css?v=ui20260923a" />
    <link rel="stylesheet" href="{root}assets/sidebar.css?v=ui20260923a" />
    <script src="{root}assets/sidebar.js?v=ui20260923a"></script>
  </head>
  <body>
    <a class="skip-link" href="#topicsMain">跳到主题内容</a>
    <main class="shell topics-shell">
      <header class="hero topics-hero">
        <div class="hero-main">
          <div class="hero-headline">
            <a class="topics-home-logo" href="{home_href}" aria-label="返回 AI News Radar">
              <img class="hero-logo" src="{root}assets/logo.svg" alt="" />
            </a>
            <div>
              <p class="topics-kicker"><a href="{hub_href}">主题</a> · AI News Radar</p>
              <h1 id="topicsTitle">{heading}</h1>
              <p class="topics-lead" id="topicsLead">{lead}</p>
              <div class="hero-updated">
                <span class="updated-label">更新时间</span>
                <span class="updated" id="updatedAt">加载中...</span>
              </div>
            </div>
          </div>
        </div>
        <div class="hero-meta">
          <nav class="hero-links" aria-label="页面入口">
            <a class="hero-link" href="{home_href}">返回雷达</a>
            <a class="hero-link" href="{classic_href}">经典版</a>
            <a class="hero-link" href="{hub_href}" aria-current="{topics_current}">全部主题</a>
          </nav>
        </div>
      </header>
      <nav class="topics-filter" id="topicsFilter" aria-label="按组别筛选" hidden></nav>
      <section id="topicsMain" class="topics-main" aria-live="polite">
        <p class="topics-status" id="topicsStatus">正在加载主题…</p>
      </section>
    </main>
    <template id="itemTpl">
      <article class="news-card">
        <div class="news-card-body">
          <div class="meta-row">
            <span class="curated-badge" hidden>精选</span>
            <span class="site"></span>
            <span class="source"></span>
          </div>
          <a class="title" target="_blank" rel="noopener noreferrer"></a>
          <p class="news-summary"></p>
          <div class="why-box" hidden>
            <span class="why-label">推荐理由：</span>
            <span class="why-text"></span>
          </div>
        </div>
      </article>
    </template>
    <script src="{root}assets/topics.js?v=topics-5" defer></script>
  </body>
</html>
"""


def render_topic_page(*, topic_id: str = "", name: str = "", description: str = "", depth: int) -> str:
    root = "../" * depth
    home_href = root
    classic_href = f"{root}classic/"
    hub_href = "./" if depth == 1 else "../"
    if topic_id:
        title = f"{name} · 主题 · AI News Radar"
        heading = name or topic_id
        lead = description or "正在加载该主题下的条目…"
        topic_attr = f' data-topic-id="{topic_id}"'
        topics_current = "false"
    else:
        title = "主题 · AI News Radar"
        heading = "按主题看 AI"
        lead = "按产业透镜、公司与模型、技术方向浏览主题。顶部可筛选要看的主题。"
        topic_attr = ""
        topics_current = "page"
    return PAGE_TEMPLATE.format(
        topic_attr=topic_attr,
        root=root,
        title=title,
        description=lead,
        heading=heading,
        lead=lead,
        home_href=home_href,
        classic_href=classic_href,
        hub_href=hub_href,
        topics_current=topics_current,
    )


def write_topic_pages(
    config: dict[str, Any],
    pages_dir: Path = DEFAULT_PAGES_DIR,
) -> list[Path]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    hub = pages_dir / "index.html"
    hub.write_text(
        render_topic_page(depth=1),
        encoding="utf-8",
    )
    written.append(hub)

    wanted_ids = {str(topic["id"]) for topic in config.get("topics") or []}
    for child in pages_dir.iterdir():
        if child.is_dir() and child.name not in wanted_ids and (child / "index.html").exists():
            (child / "index.html").unlink()
            try:
                child.rmdir()
            except OSError:
                pass

    for topic in config.get("topics") or []:
        topic_dir = pages_dir / topic["id"]
        topic_dir.mkdir(parents=True, exist_ok=True)
        path = topic_dir / "index.html"
        path.write_text(
            render_topic_page(
                topic_id=topic["id"],
                name=topic["name"],
                description=topic["description"],
                depth=2,
            ),
            encoding="utf-8",
        )
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Topics JSON (and optional static pages)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Topic definitions JSON")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory with news JSON")
    parser.add_argument("--pages-dir", default=str(DEFAULT_PAGES_DIR), help="Directory for static topic HTML")
    parser.add_argument(
        "--write-pages",
        action="store_true",
        help="Also write topics/index.html and topics/<id>/index.html stubs",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    data_dir = Path(args.data_dir)
    payload = write_topics_payload(data_dir, config_path=config_path)
    print(f"Wrote: {data_dir / 'topics.json'} ({payload.get('topic_count', 0)} topics)")
    details = payload.get("_details") or {}
    nonempty = sum(1 for detail in details.values() if detail.get("item_count"))
    print(f"Wrote: {data_dir / 'topics'} ({nonempty} topics with items)")
    if args.write_pages:
        config = load_topic_config(config_path)
        written = write_topic_pages(config, Path(args.pages_dir))
        print(f"Wrote: {len(written)} topic HTML pages under {args.pages_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
