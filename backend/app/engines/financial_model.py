"""Company-level operational and financial exposure translation logic."""

from copy import deepcopy
from typing import Any, Dict, List

from app.config import DEFAULT_COMPANY_PROFILE


def get_default_company_profile() -> Dict[str, Any]:
    return deepcopy(DEFAULT_COMPANY_PROFILE)


def get_mock_company_profile() -> Dict[str, Any]:
    # Backward-compatible helper used in metadata and tests.
    return get_default_company_profile()


def normalize_company_profile(overrides: Dict[str, object] | None = None) -> Dict[str, Any]:
    profile = get_default_company_profile()
    if overrides:
        profile.update(overrides)

    fallback_name = str(DEFAULT_COMPANY_PROFILE.get("name", "Company")).strip() or "Company"
    normalized_name = str(profile.get("name", fallback_name)).strip()
    profile["name"] = normalized_name or fallback_name

    numeric_fields = (
        "daily_export_volume_bpd",
        "fiscal_break_even_price_usd_per_bbl",
        "debt_obligations_usd_bn",
        "insurance_dependency_ratio",
    )

    for key in numeric_fields:
        fallback = float(DEFAULT_COMPANY_PROFILE[key])
        try:
            value = float(profile.get(key, fallback))
        except (TypeError, ValueError):
            value = fallback
        value = max(0.0, value)
        if key == "insurance_dependency_ratio":
            value = min(1.0, value)
        profile[key] = value

    return profile


def _band_to_string(low: float, high: float, prefix: str = "") -> str:
    return f"{prefix}{low:,.2f} to {prefix}{high:,.2f}"


def _usd_bn(value: float) -> float:
    return round(value / 1_000_000_000, 3)


def _liquidity_indicator(
    break_even: float,
    oil_low: float,
    throughput_mid_pct: float,
    insurance_mid_pct: float,
    duration_days: int,
    debt_obligations_bn: float,
    insurance_dependency_ratio: float,
) -> str:
    score = 0

    if oil_low < break_even:
        score += 2
    elif oil_low < (break_even + 8):
        score += 1

    if throughput_mid_pct >= 30:
        score += 2
    elif throughput_mid_pct >= 15:
        score += 1

    if insurance_mid_pct >= 90 and insurance_dependency_ratio >= 0.6:
        score += 1

    if debt_obligations_bn >= 4.0:
        score += 1

    if duration_days == 90:
        score += 1

    if score <= 2:
        return "Low"
    if score <= 4:
        return "Moderate"
    return "High"


def _export_severity(throughput_mid_pct: float, lng_delay_mid_pct: float) -> str:
    composite = (throughput_mid_pct * 0.7) + (lng_delay_mid_pct * 0.3)
    if composite < 12:
        return "Low"
    if composite < 25:
        return "Moderate"
    if composite < 40:
        return "High"
    return "Severe"


def _risk_label(score: float) -> str:
    if score < 30:
        return "Low"
    if score < 55:
        return "Moderate"
    if score < 75:
        return "High"
    return "Severe"


def build_risk_heat_map(
    tier: int,
    duration_days: int,
    throughput_mid: float,
    insurance_mid: float,
    lng_delay_mid: float,
    liquidity_indicator: str,
    debt_obligations_bn: float,
    insurance_dependency_ratio: float,
) -> List[Dict[str, object]]:
    liquidity_score = {"Low": 30, "Moderate": 55, "High": 78}[liquidity_indicator]

    market_score = min(100.0, tier * 18.0 + (duration_days / 90.0) * 10.0 + 22.0)
    operations_score = min(100.0, throughput_mid * 1.4 + lng_delay_mid * 0.45)
    insurance_score = min(100.0, insurance_mid * 0.4 + insurance_dependency_ratio * 35.0)
    finance_score = min(100.0, liquidity_score + debt_obligations_bn * 4.0)

    risk_rows = [
        {"risk_area": "Market Price", "score": round(market_score, 1), "level": _risk_label(market_score)},
        {
            "risk_area": "Operational Continuity",
            "score": round(operations_score, 1),
            "level": _risk_label(operations_score),
        },
        {
            "risk_area": "Insurance & Maritime",
            "score": round(insurance_score, 1),
            "level": _risk_label(insurance_score),
        },
        {"risk_area": "Liquidity & Debt", "score": round(finance_score, 1), "level": _risk_label(finance_score)},
    ]

    return risk_rows


def compute_company_exposure(
    tier: int,
    duration_days: int,
    oil_band: Dict[str, object],
    disruption: Dict[str, object],
    company_profile: Dict[str, Any],
) -> Dict[str, object]:
    volume_bpd = float(company_profile["daily_export_volume_bpd"])
    break_even = float(company_profile["fiscal_break_even_price_usd_per_bbl"])
    debt_obligations_bn = float(company_profile["debt_obligations_usd_bn"])
    insurance_dependency_ratio = float(company_profile["insurance_dependency_ratio"])

    throughput_mid = float(disruption["throughput_reduction_pct"]["mid"])
    insurance_mid = float(disruption["insurance_premium_increase_pct"]["mid"])
    lng_delay_mid = float(disruption["lng_delay_probability_pct"]["mid"])

    export_factor = max(0.0, 1.0 - throughput_mid / 100.0)

    scenario_revenue_low = volume_bpd * export_factor * float(oil_band["low"]) * duration_days
    scenario_revenue_high = volume_bpd * export_factor * float(oil_band["high"]) * duration_days

    baseline_revenue = volume_bpd * break_even * duration_days
    delta_low = scenario_revenue_low - baseline_revenue
    delta_high = scenario_revenue_high - baseline_revenue

    liquidity = _liquidity_indicator(
        break_even=break_even,
        oil_low=float(oil_band["low"]),
        throughput_mid_pct=throughput_mid,
        insurance_mid_pct=insurance_mid,
        duration_days=duration_days,
        debt_obligations_bn=debt_obligations_bn,
        insurance_dependency_ratio=insurance_dependency_ratio,
    )
    export_severity = _export_severity(throughput_mid_pct=throughput_mid, lng_delay_mid_pct=lng_delay_mid)

    risk_heat_map = build_risk_heat_map(
        tier=tier,
        duration_days=duration_days,
        throughput_mid=throughput_mid,
        insurance_mid=insurance_mid,
        lng_delay_mid=lng_delay_mid,
        liquidity_indicator=liquidity,
        debt_obligations_bn=debt_obligations_bn,
        insurance_dependency_ratio=insurance_dependency_ratio,
    )

    return {
        "company_profile": company_profile,
        "revenue_impact_band_usd_bn": {
            "low": round(_usd_bn(delta_low), 3),
            "high": round(_usd_bn(delta_high), 3),
            "label": _band_to_string(_usd_bn(delta_low), _usd_bn(delta_high), prefix="$"),
        },
        "scenario_revenue_band_usd_bn": {
            "low": round(_usd_bn(scenario_revenue_low), 3),
            "high": round(_usd_bn(scenario_revenue_high), 3),
            "label": _band_to_string(_usd_bn(scenario_revenue_low), _usd_bn(scenario_revenue_high), prefix="$"),
        },
        "liquidity_stress_indicator": liquidity,
        "export_disruption_severity": export_severity,
        "risk_heat_map": risk_heat_map,
    }
