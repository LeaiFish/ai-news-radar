from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.update_news import (
    X_BRIDGE_SITE_ID,
    X_BRIDGE_SITE_NAME,
    load_x_bridge_items,
    parse_x_bridge_items,
    sanitize_x_bridge_mapping,
    x_bridge_key_is_forbidden,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "x-items.json"
NOW = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)


class XPrivateBridgeTests(unittest.TestCase):
    def test_forbidden_key_names(self):
        self.assertTrue(x_bridge_key_is_forbidden("auth_token"))
        self.assertTrue(x_bridge_key_is_forbidden("ct0"))
        self.assertTrue(x_bridge_key_is_forbidden("cookie"))
        self.assertTrue(x_bridge_key_is_forbidden("storage_state"))
        self.assertTrue(x_bridge_key_is_forbidden("playwright_storage_state"))
        self.assertFalse(x_bridge_key_is_forbidden("username"))
        self.assertFalse(x_bridge_key_is_forbidden("text"))

    def test_sanitize_strips_secret_like_keys(self):
        dirty = {
            "schema": "x_bridge_v1",
            "auth_token": "SHOULD_NOT_LEAK",
            "cookie": "a=b",
            "ct0": "xyz",
            "storage_state": {"cookies": []},
            "items": [
                {
                    "id": "1",
                    "url": "https://x.com/a/status/1",
                    "username": "a",
                    "text": "OpenAI ships an AI agent SDK",
                    "published": "2026-09-22T11:00:00Z",
                    "likes": 1,
                    "retweets": 0,
                    "auth_token": "nope",
                    "cookie_header": "secret",
                }
            ],
        }
        cleaned = sanitize_x_bridge_mapping(dirty)
        self.assertNotIn("auth_token", cleaned)
        self.assertNotIn("cookie", cleaned)
        self.assertNotIn("ct0", cleaned)
        self.assertNotIn("storage_state", cleaned)
        self.assertNotIn("auth_token", cleaned["items"][0])
        self.assertNotIn("cookie_header", cleaned["items"][0])
        self.assertEqual(cleaned["items"][0]["id"], "1")

    def test_valid_fixture_ingest_within_window(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        items = parse_x_bridge_items(payload, now=NOW, window_hours=24)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item.site_id, X_BRIDGE_SITE_ID)
        self.assertEqual(item.site_name, X_BRIDGE_SITE_NAME)
        self.assertEqual(item.source, "@openai")
        self.assertIn("GPT", item.title)
        self.assertEqual(item.url, "https://x.com/openai/status/1234567890")
        self.assertEqual(item.meta["post_id"], "1234567890")
        self.assertEqual(item.meta["bridge"], "private_x_cookie_bridge")
        self.assertNotIn("auth_token", item.meta)
        self.assertNotIn("cookie", item.meta)
        self.assertNotIn("ct0", item.meta)
        self.assertNotIn("storage_state", item.meta)

    def test_window_filtering_drops_old_items(self):
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        items = parse_x_bridge_items(payload, now=NOW, window_hours=24)
        ids = {item.meta["post_id"] for item in items}
        self.assertIn("1234567890", ids)
        self.assertNotIn("9988776655", ids)

    def test_load_missing_file_no_crash(self):
        missing = Path(__file__).resolve().parent / "fixtures" / "does-not-exist-x-items.json"
        self.assertFalse(missing.exists())
        items, status = load_x_bridge_items(missing, now=NOW, window_hours=24)
        self.assertEqual(items, [])
        self.assertTrue(status["ok"])
        self.assertTrue(status["skipped"])
        self.assertEqual(status["skip_reason"], "no_x_bridge_items_file")
        self.assertEqual(status["item_count"], 0)

    def test_load_empty_items_file(self):
        path = Path(__file__).resolve().parent / "fixtures" / "x-items-empty.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "x_bridge_v1",
                    "generated_at": "2026-09-22T12:00:00Z",
                    "source": "private_x_cookie_bridge",
                    "items": [],
                }
            ),
            encoding="utf-8",
        )
        try:
            items, status = load_x_bridge_items(path, now=NOW, window_hours=24)
            self.assertEqual(items, [])
            self.assertTrue(status["ok"])
            self.assertFalse(status["skipped"])
            self.assertEqual(status["item_count"], 0)
            self.assertIsNone(status["error"])
        finally:
            if path.exists():
                path.unlink()

    def test_load_fixture_reports_status(self):
        items, status = load_x_bridge_items(FIXTURE, now=NOW, window_hours=24)
        self.assertEqual(len(items), 1)
        self.assertTrue(status["ok"])
        self.assertFalse(status["skipped"])
        self.assertEqual(status["item_count"], 1)
        self.assertEqual(status["site_id"], X_BRIDGE_SITE_ID)
        self.assertIsNone(status["error"])

    def test_malicious_keys_never_reach_raw_item_meta(self):
        payload = {
            "schema": "x_bridge_v1",
            "cookie": "session=abc",
            "items": [
                {
                    "id": "55",
                    "url": "https://x.com/dev/status/55",
                    "username": "dev",
                    "text": "Anthropic Claude and LLM tooling update",
                    "published": "2026-09-22T11:45:00Z",
                    "likes": 3,
                    "retweets": 1,
                    "auth_token": "leak-token-value",
                    "ct0": "leak-ct0-value",
                    "storage_state": {"cookies": [{"name": "auth_token"}]},
                }
            ],
        }
        items = parse_x_bridge_items(payload, now=NOW, window_hours=24)
        self.assertEqual(len(items), 1)
        meta = items[0].meta
        self.assertNotIn("auth_token", meta)
        self.assertNotIn("ct0", meta)
        self.assertNotIn("storage_state", meta)
        self.assertNotIn("cookie", meta)
        blob = json.dumps(meta)
        self.assertNotIn("leak-token-value", blob)
        self.assertNotIn("leak-ct0-value", blob)


if __name__ == "__main__":
    unittest.main()
