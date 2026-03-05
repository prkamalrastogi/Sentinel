import importlib

from fastapi.testclient import TestClient


def build_client(monkeypatch, api_keys: str, rate_limit_per_minute: int = 120) -> TestClient:
    monkeypatch.setenv("SENTINEL_API_KEYS", api_keys)
    monkeypatch.setenv("SENTINEL_RATE_LIMIT_PER_MINUTE", str(rate_limit_per_minute))
    monkeypatch.setenv("SENTINEL_EXPOSE_DOCS", "false")

    from app.settings import get_settings

    get_settings.cache_clear()
    import app.main as main_module

    importlib.reload(main_module)
    return TestClient(main_module.app)


def test_health_open_without_auth(monkeypatch):
    client = build_client(monkeypatch, api_keys="secure-demo-key")

    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_meta_requires_api_key_when_configured(monkeypatch):
    client = build_client(monkeypatch, api_keys="secure-demo-key")

    unauthorized = client.get("/meta/tiers")
    assert unauthorized.status_code == 401

    authorized = client.get("/meta/tiers", headers={"X-API-Key": "secure-demo-key"})
    assert authorized.status_code == 200
    assert "tiers" in authorized.json()


def test_simulate_payload_validation(monkeypatch):
    client = build_client(monkeypatch, api_keys="")

    response = client.post(
        "/simulate",
        json={
            "tier": 1,
            "duration_days": 15,
            "trigger_inputs": {
                "terminal_strikes": 0,
                "blockade_alert_level": 0,
                "insurance_withdrawal_pct": 0,
            },
        },
    )

    assert response.status_code == 422


def test_simulate_accepts_company_profile_override(monkeypatch):
    client = build_client(monkeypatch, api_keys="")

    response = client.post(
        "/simulate",
        json={
            "tier": 1,
            "duration_days": 7,
            "trigger_inputs": {
                "terminal_strikes": 0,
                "blockade_alert_level": 0,
                "insurance_withdrawal_pct": 0,
            },
            "company_profile": {
                "name": "ENOC Test Override",
                "daily_export_volume_bpd": 600000,
                "fiscal_break_even_price_usd_per_bbl": 50,
                "debt_obligations_usd_bn": 1.7,
                "insurance_dependency_ratio": 0.8,
            },
        },
    )

    assert response.status_code == 200
    company_profile = response.json()["company_exposure"]["company_profile"]
    assert company_profile["name"] == "ENOC Test Override"
    assert company_profile["daily_export_volume_bpd"] == 600000


def test_rate_limit_enforced(monkeypatch):
    client = build_client(monkeypatch, api_keys="", rate_limit_per_minute=10)

    payload = {
        "tier": 0,
        "duration_days": 7,
        "trigger_inputs": {
            "terminal_strikes": 0,
            "blockade_alert_level": 0,
            "insurance_withdrawal_pct": 0,
        },
    }

    responses = [client.post("/simulate", json=payload) for _ in range(11)]
    assert all(resp.status_code == 200 for resp in responses[:10])
    assert responses[10].status_code == 429


def test_simulate_live_returns_advisory(monkeypatch):
    client = build_client(monkeypatch, api_keys="")

    def fake_live_intel(*args, **kwargs):
        return {
            "generated_at_utc": "2026-03-01T00:00:00Z",
            "lookback_hours": 48,
            "sources_checked": 2,
            "sources_healthy": 2,
            "source_status": [],
            "fetch_warnings": [],
            "signal_summary": {
                "critical_count": 1,
                "elevated_count": 2,
                "watch_count": 0,
                "neutral_count": 0,
                "category_counts": {"blockade_alert": 1, "shipping_disruption": 2},
            },
            "thread_summary": [],
            "headlines": [
                {
                    "title": "Naval blockade alert in key transit corridor",
                    "summary": "",
                    "link": "https://example.com/news",
                    "source": "Example",
                    "published_utc": "2026-03-01T00:00:00Z",
                    "domain": "example.com",
                    "signal_level": "critical",
                    "signal_categories": ["blockade_alert"],
                    "signal_score": 6,
                    "relevance_score": 11,
                }
            ],
        }

    monkeypatch.setattr("app.service.fetch_live_intelligence", fake_live_intel)

    payload = {
        "tier": 2,
        "duration_days": 30,
        "trigger_inputs": {
            "terminal_strikes": 0,
            "blockade_alert_level": 0,
            "insurance_withdrawal_pct": 0,
        },
        "live_intel": {"lookback_hours": 48, "max_items": 20},
    }

    response = client.post("/simulate/live", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "simulation" in body
    assert "live_intelligence" in body
    assert "world_monitor_layer" in body
    assert "advisory" in body
    assert body["advisory"]["alert_level"] in {"Routine", "Watch", "Elevated", "Critical"}


def test_advisor_chat_returns_guidance(monkeypatch):
    client = build_client(monkeypatch, api_keys="")

    payload = {
        "tier": 2,
        "duration_days": 30,
        "trigger_inputs": {
            "terminal_strikes": 0,
            "blockade_alert_level": 0,
            "insurance_withdrawal_pct": 0,
        },
        "question": "What should we do now to protect cash and exports?",
        "enable_live_intel": False,
        "live_intel": {"lookback_hours": 24, "max_items": 20, "include_api_sources": False},
        "chat_history": [],
    }

    response = client.post("/advisor/chat", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["answer"]
    assert len(body["next_actions"]) >= 1
    assert "next_action_reasons" in body
    assert body["advisor_mode"] in {"rules", "ai"}
    assert "context_snapshot" in body
    assert body["context_snapshot"]["effective_tier"] >= 0


def test_advisor_chat_varies_by_question_topic(monkeypatch):
    client = build_client(monkeypatch, api_keys="")

    base_payload = {
        "tier": 2,
        "duration_days": 30,
        "trigger_inputs": {
            "terminal_strikes": 0,
            "blockade_alert_level": 0,
            "insurance_withdrawal_pct": 0,
        },
        "enable_live_intel": False,
        "live_intel": {"lookback_hours": 24, "max_items": 20, "include_api_sources": False},
        "chat_history": [],
    }

    p1 = {**base_payload, "question": "How do we protect liquidity in this scenario?"}
    p2 = {**base_payload, "question": "How do we keep shipping routes running?"}

    r1 = client.post("/advisor/chat", json=p1)
    r2 = client.post("/advisor/chat", json=p2)
    assert r1.status_code == 200
    assert r2.status_code == 200

    b1 = r1.json()
    b2 = r2.json()
    assert b1["answer"] != b2["answer"]
    assert b1["next_actions"] != b2["next_actions"]


def test_learning_entry_roundtrip(monkeypatch):
    client = build_client(monkeypatch, api_keys="")

    payload = {
        "title": "Unit test entry",
        "observation": "Shipping insurance tightened quickly.",
        "action_taken": "Activated fallback broker channel.",
        "outcome": "Coverage remained available with higher premium.",
        "lesson": "Pre-negotiate fallback insurers before escalation.",
        "tags": ["insurance", "shipping"],
    }

    created = client.post("/learning/entries", json=payload)
    assert created.status_code == 200
    body = created.json()
    assert body["id"].startswith("learn-")
    assert body["title"] == payload["title"]

    fetched = client.get("/learning/entries", params={"limit": 20})
    assert fetched.status_code == 200
    entries = fetched.json()
    assert isinstance(entries, list)
    assert any(item.get("id") == body["id"] for item in entries)
