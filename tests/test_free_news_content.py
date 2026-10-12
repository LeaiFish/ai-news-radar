import json
import socket

from scripts import free_news_content as content
from scripts import update_news


def test_extracts_article_prose_without_navigation_or_script():
    html = '<nav><p>登录订阅访问个人账户，关注我们以获取更多信息和最新资讯。</p></nav><article><p>千问发布新的开放模型，提供公开权重和部署说明，开发者可以在本地运行。</p><script>secret</script></article>'
    summary, origin = content.extract_excerpt(html, "千问发布模型")
    assert "公开权重" in summary
    assert "登录" not in summary and "secret" not in summary
    assert origin == "article_excerpt"


def test_jsonld_and_title_only_pages():
    text = "新模型提供开放权重，包含部署示例和公开评测结果，可供开发者独立验证。"
    html = '<script type="application/ld+json">' + json.dumps({"@type": "NewsArticle", "description": text}) + '</script>'
    assert content.extract_excerpt(html)[0] == text
    assert content.extract_excerpt('<h1>New model released</h1>') == ("", "")
    assert content.excerpt("New model released", "New model released") == ""


def test_public_url_rejects_private_dns_and_unapproved_destinations(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))])
    assert not content.public_url("https://www.aibase.com/news/123")
    assert not content.public_url("https://internal.example/secret")
    assert not content.public_url("file:///etc/passwd")
    assert not content.public_url("https://www.aibase.com:invalid/news/123")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("1.1.1.1", 443))])
    assert content.public_url("https://www.aibase.com/news/123")


def test_redirect_to_private_destination_is_never_requested(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **kw: [(2, 1, 6, "", ("1.1.1.1", 443))])
    class Response:
        status_code = 302
        headers = {"Location": "http://127.0.0.1/private"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    class Session:
        def __init__(self):
            self.calls = []
        def get(self, url, **kwargs):
            self.calls.append(url)
            assert kwargs["allow_redirects"] is False
            return Response()
    session = Session()
    assert content.fetch_excerpt(session, "https://www.aibase.com/news/123", "News") == ("", "")
    assert session.calls == ["https://www.aibase.com/news/123"]


def test_paid_processing_stays_off_even_with_a_key(monkeypatch):
    monkeypatch.setenv("RADAR_FREE_ONLY", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    def forbidden(*args, **kwargs):
        raise AssertionError("Paid processing must not make a request")
    monkeypatch.setattr(update_news.requests, "post", forbidden)
    assert update_news.translate_to_zh_deepseek("Model release") is None
    assert update_news.enhance_title_deepseek("Model release", "Full text") is None
    assert update_news.generate_recommend_reason_deepseek("Model release", "Full text") is None


def test_rss_content_is_preserved_as_source_excerpt():
    text = "The model has public weights, documented deployment steps, and independently reproducible evaluation results."
    entry = {"title": "Model release", "content": [{"value": "<p>" + text + "</p>"}]}
    assert update_news.feed_entry_summary(entry) == text


def test_zero_budget_reuses_source_summary_without_fetching(tmp_path, monkeypatch):
    text = "千问发布新的开放模型，提供公开权重和部署说明，开发者可以在本地运行。"
    (tmp_path / "archive.json").write_text(json.dumps({"generated_at": "2026-10-12T00:00:00Z", "items": [
        {"title": "Qwen release", "url": "https://qwen.ai/blog?id=test", "published_at": "2026-10-12T00:00:00Z", "summary": text}
    ]}))
    monkeypatch.setattr(content, "fetch_excerpt", lambda *a: (_ for _ in ()).throw(AssertionError("No fetching")))
    counts = content.enrich(tmp_path, max_fetch=0, max_translate=0)
    assert counts["fetched"] == 0 and counts["available"] == 1
    cache = json.loads((tmp_path / "news-summary-cache.json").read_text())
    assert cache["https://qwen.ai/blog?id=test"]["summary_zh"] == text
