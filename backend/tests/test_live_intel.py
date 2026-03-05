from app.engines.advisory_engine import build_advisory
from app.engines.news_intelligence import extract_signal_profile
from app.service import run_simulation


def test_extract_signal_profile_detects_critical_categories():
    text = (
        "Naval blockade alert reported after missile strike on export terminal. "
        "Insurers suspend war-risk cover for tankers."
    )
    profile = extract_signal_profile(text)

    assert profile["level"] == "critical"
    assert "blockade_alert" in profile["categories"]
    assert "terminal_strike" in profile["categories"]
    assert "insurance_withdrawal" in profile["categories"]
    assert profile["score"] >= 10


def test_build_advisory_outputs_recommended_steps():
    simulation = run_simulation(selected_tier=3, duration_days=30, trigger_inputs={})
    live_intel = {
        "signal_summary": {
            "critical_count": 2,
            "elevated_count": 3,
            "watch_count": 1,
            "neutral_count": 0,
            "category_counts": {
                "blockade_alert": 1,
                "terminal_strike": 1,
                "insurance_withdrawal": 1,
            },
        }
    }

    advisory = build_advisory(simulation=simulation, live_intel=live_intel)
    assert advisory["alert_level"] in {"Elevated", "Critical"}
    assert advisory["advisory_score"] > 0
    assert len(advisory["insights"]) >= 3
    assert len(advisory["recommended_steps"]) >= 3
