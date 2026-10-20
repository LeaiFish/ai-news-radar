from datetime import datetime, timedelta, timezone
import json

import pytest
import requests

from scripts import wechat_sources as wechat
from scripts.update_news import load_wechat_bridge_items, apply_public_raw_meta, attach_select_tier

NOW = datetime(2026, 10, 20, 4, tzinfo=timezone.utc)
URL = "https://mp.weixin.qq.com/s/test-article"


def page(account="DeepSeek", published="2026-10-20 10:00", title="DeepSeek 发布新模型"):
    return f'<h1 id="activity-name">{title}</h1><a id="js_name">{account}</a><em id="publish_time">{published}</em>'


def row(**extra):
    return {**wechat.parse_article(page(), "DeepSeek", URL, NOW), "evidence_url": extra.get("url", URL), **extra}


def searches():
    return [{"account_name": name, "ok": True} for names in wechat.targets().values() for name in names]


def snapshot(rows=None, **extra):
    return {"schema": wechat.SCHEMA, "updated": "2026-10-20", "accounts": {"deepseek": rows or [row()]},
            "last_run": {"at": wechat.iso(NOW), "ok": True}, **extra}


def save(tmp_path, payload):
    path = tmp_path / "wechat-accounts.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_wechat_url_rejects_other_hosts_and_strips_session_parameters():
    assert wechat.canonical_url(URL + "?token=PRIVATE#fragment") == URL
    long = "https://mp.weixin.qq.com/s?__biz=abc&mid=123&idx=1&sn=xyz&token=PRIVATE"
    assert "token" not in wechat.canonical_url(long)
    for url in ["https://mp.weixin.qq.com.attacker/s/id", "https://attacker/s/id", "file:///s/id", "https://mp.weixin.qq.com/home"]:
        with pytest.raises(ValueError):
            wechat.canonical_url(url)


def test_account_match_rejects_media_and_near_names():
    for account in ["APPSO", "晚点LatePost", "字母榜", "DeepSeek研究资讯"]:
        with pytest.raises(ValueError, match="account_mismatch"):
            wechat.parse_article(page(account), "DeepSeek", URL, NOW)
    assert wechat.parse_article(page("MiniMax 稀宇科技"), "MiniMax稀宇科技", URL, NOW)["account_verified"]


def test_uses_shanghai_date_and_never_fills_unknown_date_with_now():
    assert row()["published"] == "2026-10-20T02:00:00Z"
    for value in ["", "昨天", "10月20日", "2026-02-30"]:
        assert wechat.parse_article(page(published=value), "DeepSeek", URL, NOW)["published"] is None
    with pytest.raises(ValueError, match="future_publication"):
        wechat.parse_article(page(published="2026-10-21"), "DeepSeek", URL, NOW)


def test_parses_original_js_metadata_without_using_archive_capture_date():
    html = '<meta property="og:title" content="模型发布"><script>var nick_name = "DeepSeek"; var ct = "1792454400";</script>'
    assert wechat.parse_article(html, "DeepSeek", URL, NOW)["published"] == "2026-10-20T00:00:00Z"
    for source in ["环境异常，请完成验证", "请求过于频繁"]:
        with pytest.raises(ValueError):
            wechat.parse_article(source, "DeepSeek", URL, NOW)


def test_wayback_fallback_and_404_are_honest(monkeypatch):
    calls = []
    def fetch(url):
        calls.append(url)
        return "环境异常" if len(calls) == 1 else page()
    monkeypatch.setattr(wechat, "read_page", fetch)
    candidate = {"company_id": "deepseek", "account_name": "DeepSeek", "url": URL}
    verified = wechat.verify_candidate(candidate, NOW)
    assert verified["evidence_url"] == f"https://web.archive.org/web/2026id_/{URL}"
    monkeypatch.setattr(wechat, "read_page", lambda url: (_ for _ in ()).throw(requests.HTTPError("404")))
    result = wechat.sync({"searches": searches(), "candidates": [candidate]}, snapshot(), NOW)
    assert not result["last_run"]["ok"]
    assert result["last_run"]["errors"][0]["error"] == "HTTPError"
    assert result["accounts"]["deepseek"][0]["url"] == URL


def test_dedupe_cap_per_account_and_preserve_other_accounts():
    candidates = [{"company_id": "deepseek", "account_name": "DeepSeek", "url": URL}] * 2
    candidates += [{"company_id": "deepseek", "account_name": "DeepSeek", "url": f"{URL}-{i}"} for i in range(12)]
    def verify(candidate, now):
        return row(company_id="deepseek", url=candidate["url"])
    previous = [row(url=f"{URL}-old-{i}", published=f"2026-09-{i + 1:02d}T00:00:00Z") for i in range(20)]
    previous += [row(account_name="深度求索", url=URL + "-other")]
    result = wechat.sync({"searches": searches(), "candidates": candidates}, snapshot(previous), NOW, verify)
    assert result["last_run"]["verified"] == 10
    assert len(result["accounts"]["deepseek"]) == 21
    assert len({r["url"] for r in result["accounts"]["deepseek"]}) == 21
    assert any(r["account_name"] == "深度求索" for r in result["accounts"]["deepseek"])


def test_missing_search_does_not_claim_success():
    result = wechat.sync({"searches": [], "candidates": []}, snapshot(), NOW)
    assert not result["last_run"]["ok"]
    assert len(result["last_run"]["errors"]) == 24


def test_qwen_consumer_account_is_separate_from_the_research_lab(monkeypatch):
    assert "千问APP" in wechat.targets()["qwen"]
    assert "通义实验室" in wechat.targets()["qwen"]
    monkeypatch.setattr(wechat, "read_page", lambda url: page(account="千问APP"))
    result = wechat.verify_candidate({"company_id": "qwen", "account_name": "千问APP", "url": URL}, NOW)
    assert result["account_name"] == "千问APP"


def test_radar_ingress_only_admits_verified_recent_rows_and_no_secret_keys(tmp_path):
    recent = row(cookie="SECRET", auth_token="SECRET", storage_state={"cookies": []})
    data = snapshot([recent, row(url=URL + "-null", published=None),
                     row(url=URL + "-old", published="2026-10-01T00:00:00Z"),
                     row(url=URL + "-future", published="2026-10-21T00:00:00Z"),
                     row(url=URL + "-unverified", account_verified=False),
                     row(url=URL + "-media", account_name="APPSO"),
                     row(url=URL + "-wrong-evidence", evidence_url="https://attacker/")])
    data["last_run"]["auth_token"] = "SECRET"
    items, status = load_wechat_bridge_items(save(tmp_path, data), NOW)
    assert len(items) == 1
    assert items[0].source == "公众号：DeepSeek"
    assert items[0].meta["select_tier"] == "T1_5"
    assert status["undated_count"] == 1
    assert "SECRET" not in json.dumps([items[0].meta, status])


def test_no_file_bad_schema_and_stale_snapshot(tmp_path):
    assert wechat.load_radar_rows(tmp_path / "missing", NOW)[1]["skipped"]
    assert not wechat.load_radar_rows(save(tmp_path, {"schema": "wrong"}), NOW)[1]["ok"]
    data = snapshot(last_run={"at": wechat.iso(NOW - timedelta(hours=31)), "ok": True})
    items, status = wechat.load_radar_rows(save(tmp_path, data), NOW)
    assert len(items) == 1  # Still usable public article, with an honest failed health status.
    assert not status["ok"] and status["stale"]
    assert not wechat.load_radar_rows(save(tmp_path, snapshot(last_run=None)), NOW)[1]["ok"]
    malformed = snapshot([row(title=123)])
    assert not wechat.load_radar_rows(save(tmp_path, malformed), NOW)[0]


def test_verification_evidence_survives_normal_archive_projection(tmp_path):
    items, _ = load_wechat_bridge_items(save(tmp_path, snapshot()), NOW)
    raw = items[0]
    record = {"title": raw.title, "url": raw.url, "source": raw.source, "site_id": raw.site_id}
    apply_public_raw_meta(record, raw)
    attach_select_tier(record, site_id=raw.site_id, source=raw.source, meta=raw.meta)
    assert record["account_name"] == "DeepSeek"
    assert record["account_verified"] is True
    assert record["evidence_url"] == URL
    assert record["select_tier"] == "T1_5"
