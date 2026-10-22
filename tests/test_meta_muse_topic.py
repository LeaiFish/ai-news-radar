import json
from pathlib import Path
import pytest
from scripts.build_topics import record_matches_topic

TOPIC = next(t for t in json.loads(Path('config/topics.json').read_text())['topics'] if t['id'] == 'meta-llama')

@pytest.mark.parametrize('title,url,expected', [
    ('Muse for Small Business adds store tools', 'https://about.fb.com/news/example', True),
    ('Meta Muse adds app connections', 'https://about.fb.com/news/example', True),
    ('Muse.ai adds a business tool', 'https://muse.ai/new', True),
    ('A museum guide builds an AI demo', 'https://example.com/museum', False),
    ('Muse concert tickets are on sale', 'https://example.com/music', False),
])
def test_muse_identity_is_scoped(title, url, expected):
    assert record_matches_topic({'title': title, 'url': url}, TOPIC) is expected
