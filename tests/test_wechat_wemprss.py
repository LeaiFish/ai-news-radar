from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from scripts.wechat_wemprss import collect, merge_result
from scripts.wechat_sources import canonical_evidence_url, eligible_rows, load_radar_rows
from scripts.publish_wechat_snapshot import public_snapshot, merged_snapshot

@pytest.fixture(autouse=True)
def no_public_network(monkeypatch):
    monkeypatch.setattr('scripts.wechat_wemprss.discover_public',
        lambda *args, **kwargs: {'ok': True, 'truncated': False, 'candidates': []})


NOW = datetime(2026, 10, 20, 10, tzinfo=timezone.utc)
JOB = {"company_id": "deepseek", "account_name": "DeepSeek", "book_id": "MP_WXS_123"}
URL = "https://mp.weixin.qq.com/s/test__article"
EVIDENCE = "https://weread.qq.com/web/mp/content?reviewId=MP_WXS_123_test~~article"


class Reader:
    def __init__(self, name="DeepSeek", body=None, error=None):
        self.name, self.body, self.error, self.calls = name, body, error, 0

    def _get_mp_cover(self, book):
        self.calls += 1
        if self.error:
            raise self.error
        return {"name": self.name, "reviewId": book + "_test~~article", "create_time": int(NOW.timestamp())}

    def _weread_http_get(self, *args, **kwargs):
        body = self.body if self.body is not None else '<h1 id="activity-name">发布更新</h1><a id="js_name">DeepSeek</a><em id="publish_time">2026-10-15 17:54</em>'
        def not_json():
            raise ValueError()
        return SimpleNamespace(text=body, raise_for_status=lambda: None, json=not_json)


def test_verified_reader_metadata_is_publishable_and_uses_original_date(tmp_path):
    result = collect(Reader(), [JOB], NOW, delay=lambda _: None)
    snapshot = merge_result(result, None, [JOB], NOW)
    clean = public_snapshot(snapshot, NOW)
    row = clean["accounts"]["deepseek"][0]
    assert row["published"] == "2026-10-15T09:54:00Z"
    assert row["url"] == URL
    assert row["evidence_url"] == EVIDENCE
    assert not clean["last_run"]["ok"]  # A readable cover does not prove complete list coverage.
    assert clean["last_run"]["coverage_complete"] is False
    assert clean["last_run"]["searched_accounts"] == 1
    assert clean["last_run"]["collector"] == "wemprss"
    path = tmp_path / "snapshot.json"
    import json
    path.write_text(json.dumps(clean))
    rows, status = load_radar_rows(path, NOW)
    assert len(rows) == 1  # Historical originals are archived, without becoming today's news.
    assert rows[0]["published"] == "2026-10-15T09:54:00Z"
    assert status["recent_window_item_count"] == 0
    assert status["historical_item_count"] == 1


@pytest.mark.parametrize("value", [
    EVIDENCE + "&token=PRIVATE", EVIDENCE + "&reviewId=another",
    EVIDENCE + "#PRIVATE", EVIDENCE.replace("https:", "http:"),
    EVIDENCE.replace("weread.qq.com", "weread.qq.com.attacker"),
    EVIDENCE.replace("test~~article", "wrong"),
])
def test_evidence_rejects_credentials_and_mismatched_article(value):
    with pytest.raises(ValueError):
        canonical_evidence_url(value, URL)


def test_wrong_publisher_rejected_and_no_date_never_becomes_now():
    assert collect(Reader(name="其他账号"), [JOB], NOW)["rows"] == []
    body = '<h1 id="activity-name">发布更新</h1><a id="js_name">DeepSeek</a>'
    result = collect(Reader(body=body), [JOB], NOW)
    assert result["rows"][0]["published"] is None


def test_auth_failure_stops_requests_and_keeps_verified_history():
    good = merge_result(collect(Reader(), [JOB], NOW), None, [JOB], NOW)
    error = RuntimeError("PRIVATE credentials must never escape")
    error.code = -2012
    reader = Reader(error=error)
    second = {"company_id": "qwen", "account_name": "千问APP", "book_id": "MP_WXS_456"}
    failed = collect(reader, [JOB, second], NOW, delay=lambda _: None)
    assert reader.calls == 1
    assert "PRIVATE" not in str(failed)
    snapshot = merge_result(failed, good, [JOB, second], NOW)
    assert not snapshot["last_run"]["ok"]
    assert len(list(eligible_rows(snapshot, NOW))) == 1
    assert snapshot["last_run"]["collection_state"] == "failed"
    assert public_snapshot(snapshot, NOW)["last_run"]["errors"][0]["error"] in {
        "wemprss_api_-2012", "wemprss_stopped_after_auth_or_quota_error"}


def test_publish_counts_include_remote_history_without_counting_it_as_added():
    incoming = merge_result(collect(Reader(), [JOB], NOW), None, [JOB], NOW)
    remote = public_snapshot(incoming, NOW)
    row = dict(remote["accounts"]["deepseek"][0], account_name="千问APP",
               url="https://mp.weixin.qq.com/s/old", evidence_url="https://mp.weixin.qq.com/s/old")
    remote["accounts"] = {"qwen": [row]}
    merged = merged_snapshot(incoming, remote, NOW)
    assert merged["last_run"]["covered_companies"] == 2
    assert merged["last_run"]["covered_accounts"] == 2
    assert merged["last_run"]["added"] == 1
    assert merged["last_run"]["recent_24h"] == 0
