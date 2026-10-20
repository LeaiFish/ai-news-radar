from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import pytest

from scripts import publish_wechat_snapshot as publisher

NOW = datetime(2026, 10, 20, 4, tzinfo=timezone.utc)


def snapshot(url="https://mp.weixin.qq.com/s/verified", at="2026-10-20T01:00:00Z"):
    return {"schema": "wechat_accounts_v1", "updated": "2026-10-20", "accounts": {"deepseek": [{
        "url": url, "title": "DeepSeek 发布模型", "account_name": "DeepSeek", "published": None,
        "verified_at": "2026-10-20T00:00:00Z", "account_verified": True, "evidence_url": url,
        "cookie": "PRIVATE"}]}, "last_run": {"at": at, "ok": True, "searched_accounts": 24,
        "candidates": 1, "verified": 1, "added": 1, "covered_companies": 1, "covered_accounts": 1,
        "errors": [], "token": "PRIVATE"}, "cookie": "PRIVATE"}


def git(*args, cwd=None):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()


def test_publication_strips_arbitrary_fields_and_url_session_parameters():
    data = snapshot("https://mp.weixin.qq.com/s/verified?token=PRIVATE")
    clean = publisher.public_snapshot(data, NOW)
    assert "PRIVATE" not in json.dumps(clean)
    assert clean["accounts"]["deepseek"][0]["published"] is None
    assert clean["accounts"]["deepseek"][0]["url"] == "https://mp.weixin.qq.com/s/verified"


def test_invalid_snapshot_fails_before_any_git_or_network(monkeypatch):
    data = snapshot()
    data["accounts"]["deepseek"][0]["account_verified"] = False
    monkeypatch.setattr(publisher, "git", lambda *a, **kw: pytest.fail("unexpected git operation"))
    with pytest.raises(ValueError, match="unverified"):
        publisher.publish(data)


def test_merge_preserves_remote_articles_and_rejects_older_discovery():
    remote = snapshot("https://mp.weixin.qq.com/s/remote")
    incoming = snapshot(at="2026-10-20T02:00:00Z")
    merged = publisher.merged_snapshot(incoming, remote, NOW)
    assert len(merged["accounts"]["deepseek"]) == 2
    with pytest.raises(ValueError, match="remote_snapshot_is_newer"):
        publisher.merged_snapshot(remote, incoming, NOW)


def test_push_is_isolated_idempotent_and_retries_concurrent_remote_change(tmp_path, monkeypatch):
    remote, seed = tmp_path / "remote.git", tmp_path / "seed"
    git("init", "--bare", "--initial-branch=master", str(remote))
    git("clone", str(remote), str(seed))
    git("config", "user.name", "Test", cwd=seed)
    git("config", "user.email", "test@example.invalid", cwd=seed)
    (seed / "README.md").write_text("original\n")
    git("add", "README.md", cwd=seed)
    git("commit", "-m", "initial", cwd=seed)
    git("push", "origin", "master", cwd=seed)
    original_git = publisher.git
    pushed = []
    def concurrent_git(*args, **kwargs):
        if args[0] == "push" and not pushed:
            (seed / "README.md").write_text("concurrent public change\n")
            git("add", "README.md", cwd=seed)
            git("commit", "-m", "concurrent change", cwd=seed)
            git("push", "origin", "master", cwd=seed)
            pushed.append(True)
        return original_git(*args, **kwargs)
    monkeypatch.setattr(publisher, "git", concurrent_git)
    monkeypatch.chdir(seed)
    (seed / "private-uncommitted.txt").write_text("PRIVATE")
    result = publisher.publish(snapshot(), repository=str(remote))
    assert result["status"] == "pushed"
    assert git("--git-dir", str(remote), "show", "master:README.md") == "concurrent public change"
    assert git("--git-dir", str(remote), "diff-tree", "--no-commit-id", "--name-only", "-r", "master") == str(publisher.SNAPSHOT)
    public = git("--git-dir", str(remote), "show", "master:" + str(publisher.SNAPSHOT))
    assert "PRIVATE" not in public
    assert (seed / "private-uncommitted.txt").read_text() == "PRIVATE"
    assert publisher.publish(snapshot(), repository=str(remote))["status"] == "unchanged"
