from app.connectors.world_monitor_connector import build_world_monitor_layer


def test_world_monitor_connector_normalizes_events():
    live_intel = {
        "provider_summary": {
            "total_sources": 10,
            "healthy_sources": 8,
        },
        "headlines": [
            {
                "title": "Missile strike reported near export terminal in Gulf",
                "summary": "Shipping lane stress rises after incident.",
                "link": "https://example.com/a",
                "source": "Example Source",
                "provider_id": "rss_google_hormuz",
                "provider_type": "rss",
                "published_utc": "2026-03-05T09:00:00+00:00",
                "signal_level": "critical",
                "signal_categories": ["terminal_strike", "shipping_disruption"],
                "relevance_score": 12,
            },
            {
                "title": "Insurance market withdrawal concerns in GCC tanker routes",
                "summary": "War-risk cover repricing continues.",
                "link": "https://example.com/b",
                "source": "Example Source",
                "provider_id": "newsapi",
                "provider_type": "api",
                "published_utc": "2026-03-05T08:00:00+00:00",
                "signal_level": "critical",
                "signal_categories": ["insurance_withdrawal"],
                "relevance_score": 10,
            },
        ],
        "thread_summary": [],
    }

    layer = build_world_monitor_layer(live_intel, max_events=10)
    assert layer["events_count"] == 2
    assert layer["connector"] == "world_monitor_adapter_v1"
    assert len(layer["events"]) == 2
    assert len(layer["heatmaps"]["region"]) >= 1
    assert len(layer["heatmaps"]["event_type"]) >= 1
