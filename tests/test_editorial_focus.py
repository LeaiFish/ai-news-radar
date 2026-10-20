from datetime import datetime, timezone

from scripts.editorial_focus import add_editorial_focus, editorial_focus
from scripts.update_news import build_story_record, calculate_item_importance
from scripts.story_select import assign_selection_tiers

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


def test_model_eval_accounts_get_hidden_tag_but_product_function_does_not():
    evaluation = {'title': 'New model reaches #1 on Code Arena', 'url': 'https://x.com/arena/status/1'}
    assert add_editorial_focus(evaluation)['editorial_tags'] == ['model_evaluation']
    assert editorial_focus(evaluation) == 'technical'
    product = {'source': 'LangChain Blog', 'title': 'LangSmith launches a new dashboard for team collaboration'}
    assert editorial_focus(product) == 'product'
    assert editorial_focus({'source': 'LangChain Blog', 'title': 'Context engineering for long-running agents'}) == 'technical'
    assert editorial_focus({'source': 'Meta Engineering Blog', 'title': 'Meta launches a new consumer app'}) == 'product'


def test_model_tech_labels_follow_url_across_direct_and_aggregated_sources():
    for source in ['vLLM Blog', 'vLLM 官方博客（RSS）', 'Some aggregator']:
        row = add_editorial_focus({'source': source, 'url': 'https://vllm.ai/blog/beam', 'title': 'Day 0 support for Beam'})
        assert row['editorial_focus'] == 'technical'
        assert row['editorial_tags'] == ['model_technology']


def test_product_story_outranks_pure_technical_story_without_losing_research():
    def item(url, title):
        return {'id': url, 'site_id': 'official_ai', 'source': 'Official Blog', 'title': title,
                'url': url, 'published_at': NOW.isoformat(), 'ai_score': 0.9, 'ai_is_related': True}
    tech = item('https://vllm.ai/blog/beam', 'Beam inference benchmark')
    product = item('https://example.com/new-app', 'ChatGPT launches a new collaboration app')
    assert calculate_item_importance(tech, NOW, 24)['score'] < calculate_item_importance(product, NOW, 24)['score']
    tech_story = build_story_record('tech', [tech], NOW, 24)
    product_story = build_story_record('product', [product], NOW, 24)
    assign_selection_tiers([tech_story, product_story], limit=1, company_topics=[], lens_topics=[], now=NOW)
    assert product_story['tier'] == 'selected'
    assert tech_story['tier'] == 'all'
    assert tech_story['editorial_focus'] == 'technical'
    mixed = build_story_record('mixed', [tech, product], NOW, 24)
    assert mixed['editorial_focus'] == 'product'


def test_internal_archive_tags_are_derived_not_provider_priority_claims():
    from scripts.update_news import RawItem, apply_public_raw_meta
    record = {'title': 'Model comparison', 'url': 'https://x.com/arena/status/1', 'source': 'Arena'}
    raw = RawItem('aihot', 'AIHOT', 'Arena', record['title'], record['url'], NOW,
                  {'editorial_focus': 'product', 'editorial_tags': ['product_update']})
    apply_public_raw_meta(record, raw)
    assert record['editorial_focus'] == 'technical'
    assert record['editorial_tags'] == ['model_evaluation']
