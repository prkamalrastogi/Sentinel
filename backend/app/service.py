"""Scenario service that composes escalation, disruption, and financial engines."""

from typing import Dict

from app.config import DURATION_OPTIONS_DAYS, GEOGRAPHIC_SCOPE
from app.connectors.world_monitor_connector import build_world_monitor_layer
from app.engines.advisory_engine import build_advisory
from app.engines.advisor_chat_engine import build_chat_advice
from app.engines.ai_advisor import maybe_apply_ai_advisor
from app.engines.disruption_model import simulate_disruption
from app.engines.learning_engine import (
    add_learning_entry,
    list_learning_entries,
    relevant_lessons,
)
from app.engines.escalation_engine import (
    apply_trigger_rules,
    get_all_tiers,
    get_tier_definition,
    get_trigger_rules,
)
from app.engines.financial_model import (
    compute_company_exposure,
    get_default_company_profile,
    get_mock_company_profile,
    normalize_company_profile,
)
from app.engines.news_intelligence import fetch_live_intelligence, get_supported_live_providers
from app.engines.oil_simulator import simulate_oil_price_band


def build_metadata() -> Dict[str, object]:
    return {
        "project": "Sentinel - GCC Energy Escalation Simulator",
        "scope": GEOGRAPHIC_SCOPE,
        "principle": (
            "This simulator does not predict conflict outcomes. "
            "It translates escalation conditions into structured exposure bands."
        ),
        "tiers": get_all_tiers(),
        "durations_days": DURATION_OPTIONS_DAYS,
        "trigger_rules": get_trigger_rules(),
        "default_company_profile": get_default_company_profile(),
        "mock_company_profile": get_mock_company_profile(),
        "live_intelligence_providers": get_supported_live_providers(),
        "connectors": [
            {
                "id": "world_monitor_adapter_v1",
                "description": (
                    "Normalizes multi-source live signals into structured world events "
                    "before Sentinel consequence modeling."
                ),
            }
        ],
        "learning": {
            "enabled": True,
            "description": "Operator feedback loop for post-incident lessons and model refinement.",
        },
    }


def run_simulation(
    selected_tier: int,
    duration_days: int,
    trigger_inputs: Dict[str, float] | None = None,
    company_profile_override: Dict[str, object] | None = None,
) -> Dict[str, object]:
    effective_tier, triggered_rules = apply_trigger_rules(selected_tier, trigger_inputs)
    tier_definition = get_tier_definition(effective_tier)

    oil_band = simulate_oil_price_band(effective_tier, duration_days)
    disruption = simulate_disruption(effective_tier, duration_days)
    company_profile = normalize_company_profile(company_profile_override)
    company_exposure = compute_company_exposure(
        tier=effective_tier,
        duration_days=duration_days,
        oil_band=oil_band,
        disruption=disruption,
        company_profile=company_profile,
    )

    return {
        "selected_tier": selected_tier,
        "effective_tier": effective_tier,
        "tier_upgraded": effective_tier != selected_tier,
        "triggered_rules": triggered_rules,
        "duration_days": duration_days,
        "tier_definition": tier_definition,
        "oil_regime": oil_band,
        "operational_disruption": disruption,
        "company_exposure": company_exposure,
    }


def get_live_intelligence(
    lookback_hours: int = 72,
    max_items: int = 40,
    providers: list[str] | None = None,
    include_api_sources: bool = True,
) -> Dict[str, object]:
    return fetch_live_intelligence(
        lookback_hours=lookback_hours,
        max_items=max_items,
        selected_providers=providers,
        include_api_sources=include_api_sources,
    )


def run_live_simulation(
    selected_tier: int,
    duration_days: int,
    trigger_inputs: Dict[str, float] | None = None,
    company_profile_override: Dict[str, object] | None = None,
    lookback_hours: int = 72,
    max_items: int = 40,
    providers: list[str] | None = None,
    include_api_sources: bool = True,
) -> Dict[str, object]:
    simulation = run_simulation(
        selected_tier=selected_tier,
        duration_days=duration_days,
        trigger_inputs=trigger_inputs,
        company_profile_override=company_profile_override,
    )
    live_intel = fetch_live_intelligence(
        lookback_hours=lookback_hours,
        max_items=max_items,
        selected_providers=providers,
        include_api_sources=include_api_sources,
    )
    world_monitor_layer = build_world_monitor_layer(live_intel=live_intel, max_events=max_items)
    advisory = build_advisory(simulation=simulation, live_intel=live_intel)
    return {
        "simulation": simulation,
        "live_intelligence": live_intel,
        "world_monitor_layer": world_monitor_layer,
        "advisory": advisory,
    }


def run_advisor_chat(
    *,
    selected_tier: int,
    duration_days: int,
    question: str,
    trigger_inputs: Dict[str, float] | None = None,
    company_profile_override: Dict[str, object] | None = None,
    enable_live_intel: bool = True,
    lookback_hours: int = 72,
    max_items: int = 40,
    providers: list[str] | None = None,
    include_api_sources: bool = True,
    use_ai_advisor: bool = True,
) -> Dict[str, object]:
    simulation = run_simulation(
        selected_tier=selected_tier,
        duration_days=duration_days,
        trigger_inputs=trigger_inputs,
        company_profile_override=company_profile_override,
    )

    if enable_live_intel:
        live_intel = fetch_live_intelligence(
            lookback_hours=lookback_hours,
            max_items=max_items,
            selected_providers=providers,
            include_api_sources=include_api_sources,
        )
    else:
        live_intel = {
            "signal_summary": {
                "critical_count": 0,
                "elevated_count": 0,
                "watch_count": 0,
                "neutral_count": 0,
                "category_counts": {},
            },
            "provider_summary": {
                "total_sources": 0,
                "healthy_sources": 0,
                "api_sources": {"total": 0, "healthy": 0},
                "rss_sources": {"total": 0, "healthy": 0},
                "api_provider_keys_present": [],
                "api_source_ingestion_enabled": False,
            },
            "headlines": [],
            "thread_summary": [],
        }

    advisory = build_advisory(simulation=simulation, live_intel=live_intel)
    lessons = relevant_lessons(question=question, simulation=simulation, max_items=3)
    rules_chat = build_chat_advice(
        question=question,
        simulation=simulation,
        advisory=advisory,
        live_intel=live_intel,
        learning_lessons=lessons,
    )
    chat = maybe_apply_ai_advisor(
        question=question,
        simulation=simulation,
        advisory=advisory,
        live_intel=live_intel,
        fallback=rules_chat,
        use_ai_advisor=use_ai_advisor,
        learning_lessons=lessons,
    )
    action_reason_lookup = {
        item.get("step", ""): item.get("reason", "")
        for item in advisory.get("recommended_actions", [])
        if isinstance(item, dict)
    }
    next_action_reasons = [
        {"step": action, "reason": action_reason_lookup.get(action, "Selected to reduce immediate downside.")}
        for action in chat.get("next_actions", [])[:3]
    ]

    return {
        **chat,
        "next_action_reasons": next_action_reasons,
        "context_snapshot": {
            "selected_tier": simulation["selected_tier"],
            "effective_tier": simulation["effective_tier"],
            "duration_days": simulation["duration_days"],
            "alert_level": advisory["alert_level"],
            "advisory_score": advisory["advisory_score"],
            "liquidity_stress_indicator": simulation["company_exposure"]["liquidity_stress_indicator"],
            "export_disruption_severity": simulation["company_exposure"]["export_disruption_severity"],
            "lessons_considered": len(lessons),
        },
    }


def create_learning_entry(payload: Dict[str, object]) -> Dict[str, object]:
    return add_learning_entry(payload)


def get_learning_entries(limit: int = 100) -> list[Dict[str, object]]:
    return list_learning_entries(limit=limit)
