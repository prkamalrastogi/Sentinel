from app.service import run_simulation
from app.service import get_live_intelligence


def test_run_simulation_baseline_scenario():
    result = run_simulation(selected_tier=1, duration_days=7, trigger_inputs={})

    assert result["selected_tier"] == 1
    assert result["effective_tier"] == 1
    assert result["tier_upgraded"] is False
    assert result["oil_regime"]["low"] == 80.0
    assert result["oil_regime"]["high"] == 95.0
    assert "revenue_impact_band_usd_bn" in result["company_exposure"]


def test_run_simulation_trigger_upgrade_to_tier_4():
    result = run_simulation(
        selected_tier=2,
        duration_days=30,
        trigger_inputs={
            "terminal_strikes": 0,
            "blockade_alert_level": 1,
            "insurance_withdrawal_pct": 0,
        },
    )

    assert result["effective_tier"] == 4
    assert result["tier_upgraded"] is True
    assert len(result["triggered_rules"]) >= 1


def test_get_live_intelligence_forwards_provider_options(monkeypatch):
    captured: dict[str, object] = {}

    def fake_fetch_live_intelligence(*, lookback_hours, max_items, selected_providers, include_api_sources):
        captured["lookback_hours"] = lookback_hours
        captured["max_items"] = max_items
        captured["selected_providers"] = selected_providers
        captured["include_api_sources"] = include_api_sources
        return {"headlines": []}

    monkeypatch.setattr("app.service.fetch_live_intelligence", fake_fetch_live_intelligence)

    result = get_live_intelligence(
        lookback_hours=48,
        max_items=25,
        providers=["all"],
        include_api_sources=False,
    )
    assert result == {"headlines": []}
    assert captured["lookback_hours"] == 48
    assert captured["max_items"] == 25
    assert captured["selected_providers"] == ["all"]
    assert captured["include_api_sources"] is False
