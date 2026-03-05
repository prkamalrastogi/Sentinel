"""Advisory layer translating model outputs + live signals into suggested actions."""

from __future__ import annotations

from typing import Any


def _alert_level(score: float) -> str:
    if score >= 85:
        return "Critical"
    if score >= 60:
        return "Elevated"
    if score >= 35:
        return "Watch"
    return "Routine"


def _category_mentions(signal_summary: dict[str, Any], category: str) -> int:
    return int(signal_summary.get("category_counts", {}).get(category, 0))


def _action_reason(
    action: str,
    *,
    effective_tier: int,
    throughput_mid: float,
    insurance_mid: float,
    lng_delay_mid: float,
    critical_count: int,
    elevated_count: int,
) -> str:
    lower = action.lower()
    if any(token in lower for token in ["shipping", "transit", "cargo", "lng"]):
        return (
            f"Operational continuity is under pressure (throughput {throughput_mid:.1f}%, "
            f"LNG delay {lng_delay_mid:.1f}%). Early routing decisions reduce disruption."
        )
    if any(token in lower for token in ["insurance", "premium", "cover", "underwriter"]):
        return (
            f"Insurance stress is elevated ({insurance_mid:.1f}% midpoint premium increase). "
            "Fallback cover reduces shipment interruption risk."
        )
    if any(token in lower for token in ["liquidity", "cash", "lender", "debt"]):
        return (
            "Revenue variability can tighten liquidity during escalation windows. "
            "Early financing and buffer actions reduce forced decisions."
        )
    if any(token in lower for token in ["briefing", "board", "monitoring", "cell"]):
        return (
            f"Signal intensity ({critical_count} critical, {elevated_count} elevated) "
            "requires faster governance and decision cadence."
        )
    return (
        f"Recommended for Tier {effective_tier} conditions to lower operational and financial downside."
    )


def build_advisory(simulation: dict[str, Any], live_intel: dict[str, Any]) -> dict[str, Any]:
    effective_tier = int(simulation["effective_tier"])
    ops = simulation["operational_disruption"]
    throughput_mid = float(ops["throughput_reduction_pct"]["mid"])
    insurance_mid = float(ops["insurance_premium_increase_pct"]["mid"])
    lng_delay_mid = float(ops["lng_delay_probability_pct"]["mid"])

    signal_summary = live_intel.get("signal_summary", {})
    critical_count = int(signal_summary.get("critical_count", 0))
    elevated_count = int(signal_summary.get("elevated_count", 0))
    watch_count = int(signal_summary.get("watch_count", 0))
    provider_summary = live_intel.get("provider_summary", {})
    total_sources = int(provider_summary.get("total_sources", live_intel.get("sources_checked", 0)))
    healthy_sources = int(provider_summary.get("healthy_sources", live_intel.get("sources_healthy", 0)))
    coverage_ratio = (healthy_sources / total_sources) if total_sources > 0 else 0.0

    advisory_score = (
        effective_tier * 14
        + critical_count * 7
        + elevated_count * 4
        + watch_count * 2
        + (8 if throughput_mid >= 30 else 0)
        + (6 if insurance_mid >= 100 else 0)
        + (5 if lng_delay_mid >= 60 else 0)
        + (3 if critical_count > 0 and coverage_ratio >= 0.6 else 0)
    )

    alert_level = _alert_level(advisory_score)

    top_categories = sorted(
        signal_summary.get("category_counts", {}).items(),
        key=lambda x: x[1],
        reverse=True,
    )[:3]
    category_summary = ", ".join(f"{name}:{count}" for name, count in top_categories) or "none detected"

    insights = [
        (
            f"Live signal mix in lookback window: {critical_count} critical, "
            f"{elevated_count} elevated, {watch_count} watch items."
        ),
        (
            f"Top live thread categories: {category_summary}."
        ),
        (
            f"Source coverage quality: {healthy_sources}/{total_sources} providers healthy."
        ),
        (
            f"Operational midpoint stress profile: throughput {throughput_mid:.1f}%, "
            f"insurance premium {insurance_mid:.1f}%, LNG delay {lng_delay_mid:.1f}%."
        ),
        (
            "Model framing remains scenario-based exposure translation, not conflict prediction."
        ),
    ]

    actions: list[str] = []

    if effective_tier <= 1:
        actions.extend(
            [
                "Maintain daily market-monitoring cadence and refresh trigger thresholds.",
                "Validate insurance counterparties and war-risk premium assumptions weekly.",
            ]
        )
    elif effective_tier == 2:
        actions.extend(
            [
                "Activate cross-functional monitoring cell for daily exposure review.",
                "Pre-book alternate shipping windows and confirm LNG slot flexibility.",
                "Refresh 30/90-day liquidity buffers against the scenario revenue band.",
            ]
        )
    elif effective_tier == 3:
        actions.extend(
            [
                "Shift to twice-daily executive risk briefing with operations and treasury.",
                "Prioritize cargo sequencing across lower-risk routes and protected windows.",
                "Engage lenders and insurers on contingent liquidity and coverage continuity.",
            ]
        )
    else:
        actions.extend(
            [
                "Activate crisis operations protocol with daily board-level situational review.",
                "Execute contingency export allocation and prioritize strategic customer contracts.",
                "Coordinate with regulators and maritime security channels on transit continuity.",
            ]
        )

    if _category_mentions(signal_summary, "blockade_alert") > 0:
        actions.append(
            "Run immediate Strait transit contingency drill, including pipeline/stock draw alternatives."
        )
    if _category_mentions(signal_summary, "terminal_strike") > 0:
        actions.append(
            "Increase terminal hardening posture and validate backup loading/dispatch pathways."
        )
    if _category_mentions(signal_summary, "insurance_withdrawal") > 0:
        actions.append(
            "Secure fallback insurance arrangements and update premium pass-through assumptions."
        )
    if total_sources > 0 and coverage_ratio < 0.5:
        actions.append(
            "Increase source redundancy by adding additional provider APIs and regional media feeds."
        )

    # Keep actions concise and deterministic.
    deduped_actions: list[str] = []
    seen: set[str] = set()
    for action in actions:
        if action in seen:
            continue
        deduped_actions.append(action)
        seen.add(action)

    prioritized = deduped_actions[:8]
    recommended_actions = [
        {
            "priority": idx + 1,
            "step": action,
            "reason": _action_reason(
                action,
                effective_tier=effective_tier,
                throughput_mid=throughput_mid,
                insurance_mid=insurance_mid,
                lng_delay_mid=lng_delay_mid,
                critical_count=critical_count,
                elevated_count=elevated_count,
            ),
        }
        for idx, action in enumerate(prioritized)
    ]

    return {
        "alert_level": alert_level,
        "advisory_score": round(advisory_score, 1),
        "insights": insights,
        "recommended_steps": prioritized,
        "recommended_actions": recommended_actions,
    }
