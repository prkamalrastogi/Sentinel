"""Export disruption model outputs for each tier and duration."""

from typing import Dict

from app.config import BASE_DISRUPTION_RANGES, DISRUPTION_DURATION_MULTIPLIERS


def _scale_metric(range_values: Dict[str, float], multiplier: float, cap: float) -> Dict[str, float]:
    low = round(min(cap, range_values["low"] * multiplier), 2)
    high = round(min(cap, range_values["high"] * multiplier), 2)
    mid = round((low + high) / 2, 2)
    return {"low": low, "high": high, "mid": mid}


def _stress_level(score: float) -> str:
    if score < 30:
        return "Low"
    if score < 55:
        return "Moderate"
    if score < 75:
        return "High"
    return "Severe"


def simulate_disruption(tier: int, duration_days: int) -> Dict[str, object]:
    if tier not in BASE_DISRUPTION_RANGES:
        raise ValueError(f"Unsupported escalation tier: {tier}")
    if duration_days not in DISRUPTION_DURATION_MULTIPLIERS:
        raise ValueError(f"Unsupported duration: {duration_days}")

    base = BASE_DISRUPTION_RANGES[tier]
    multiplier = DISRUPTION_DURATION_MULTIPLIERS[duration_days]

    throughput = _scale_metric(base["throughput_reduction_pct"], multiplier, cap=95.0)
    insurance = _scale_metric(base["insurance_premium_increase_pct"], multiplier, cap=400.0)
    lng_delay = _scale_metric(base["lng_delay_probability_pct"], multiplier, cap=98.0)

    refinery_score = _scale_metric(base["refinery_margin_stress_score"], multiplier, cap=100.0)
    refinery_indicator = _stress_level(refinery_score["mid"])

    return {
        "throughput_reduction_pct": throughput,
        "insurance_premium_increase_pct": insurance,
        "lng_delay_probability_pct": lng_delay,
        "refinery_margin_stress": {
            "score": refinery_score,
            "indicator": refinery_indicator,
        },
    }
