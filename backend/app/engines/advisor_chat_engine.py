"""Deterministic advisor chat layer for plain-language Sentinel guidance."""

from __future__ import annotations

from typing import Any


def _top_evidence(live_intel: dict[str, Any], max_items: int = 3) -> list[dict[str, str]]:
    headlines = list(live_intel.get("headlines", []))
    if not headlines:
        return []

    ranked = sorted(
        headlines,
        key=lambda item: (int(item.get("signal_score", 0)), int(item.get("relevance_score", 0))),
        reverse=True,
    )
    evidence: list[dict[str, str]] = []
    for item in ranked[:max_items]:
        evidence.append(
            {
                "title": str(item.get("title", "Untitled")),
                "source": str(item.get("source", "")),
                "signal_level": str(item.get("signal_level", "none")),
                "link": str(item.get("link", "")),
            }
        )
    return evidence


TOPIC_KEYWORDS: dict[str, list[str]] = {
    "liquidity": ["liquidity", "cash", "debt", "treasury", "financing", "covenant", "credit"],
    "shipping": ["shipping", "hormuz", "route", "logistics", "tanker", "lng", "cargo", "transit"],
    "insurance": ["insurance", "premium", "underwriter", "cover", "war-risk"],
    "trigger": ["trigger", "upgrade", "tier", "escalat", "threshold", "auto"],
    "oil": ["price", "oil", "brent", "market", "regime", "band", "hedge"],
    "immediate": ["now", "immediate", "today", "next step", "first", "urgent"],
}


def _topic(question: str) -> str:
    q = question.lower()
    scores: dict[str, int] = {topic: 0 for topic in TOPIC_KEYWORDS}
    for topic, keywords in TOPIC_KEYWORDS.items():
        for token in keywords:
            if token in q:
                scores[topic] += 1
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if ranked and ranked[0][1] > 0:
        return ranked[0][0]
    return "general"


def _question_intent(question: str) -> str:
    q = question.lower()
    if any(token in q for token in ["first", "priority", "top", "urgent", "now", "immediate"]):
        return "priority"
    if any(token in q for token in ["why", "reason", "because"]):
        return "rationale"
    if any(token in q for token in ["risk", "worst", "danger", "threat"]):
        return "risk"
    if any(token in q for token in ["24", "48", "7 day", "30 day", "90 day", "timeline", "when"]):
        return "timeline"
    return "general"


def _topic_actions(
    topic: str,
    advisory_steps: list[str],
    simulation: dict[str, Any],
    live_intel: dict[str, Any],
) -> list[str]:
    ops = simulation.get("operational_disruption", {})
    company = simulation.get("company_exposure", {})
    throughput_mid = float((ops.get("throughput_reduction_pct") or {}).get("mid", 0))
    insurance_mid = float((ops.get("insurance_premium_increase_pct") or {}).get("mid", 0))
    lng_mid = float((ops.get("lng_delay_probability_pct") or {}).get("mid", 0))
    liquidity = str(company.get("liquidity_stress_indicator", "Unknown"))
    signal_summary = live_intel.get("signal_summary", {})
    categories = signal_summary.get("category_counts", {})

    if topic == "liquidity":
        return [
            "Freeze non-essential capex for the current window and preserve cash buffers.",
            "Run 30/90-day cashflow stress checks against the scenario revenue band.",
            "Pre-negotiate contingency lines with lenders before tier escalation.",
        ]
    if topic == "shipping":
        actions = [
            "Pre-book alternate load windows and prioritize lower-risk transit slots.",
            "Sequence cargoes to protect contractual deliveries first.",
            "Run daily Strait transit fallback drill with operations and trading.",
        ]
        if throughput_mid >= 20 or lng_mid >= 30:
            actions.append(
                "Shift vessel nomination cut-offs earlier to absorb schedule disruption."
            )
        return actions[:3]
    if topic == "insurance":
        actions = [
            "Secure fallback insurers and brokers immediately for war-risk continuity.",
            "Update freight pass-through and premium assumptions in daily PnL.",
            "Define trigger points for shipment deferral if cover is suspended.",
        ]
        if insurance_mid >= 60:
            actions.append("Escalate daily premium monitoring with treasury and trading.")
        return actions[:3]
    if topic == "trigger":
        return [
            "Track terminal strikes, blockade alerts, and insurer withdrawal every hour.",
            "Auto-upgrade one tier when strike or insurer-withdrawal thresholds are crossed.",
            "Escalate directly to Tier 4 for active blockade alert conditions.",
        ]
    if topic == "oil":
        return [
            "Hedge short-term downside while preserving upside from higher realized prices.",
            "Reprice refinery and trading books daily against updated oil bands.",
            "Align sales nominations with expected throughput constraints.",
        ]
    if topic == "immediate":
        return advisory_steps[:3] if advisory_steps else []

    actions: list[str] = []
    if int(categories.get("blockade_alert", 0)) > 0:
        actions.append("Run immediate Strait transit contingency drill and route fallback test.")
    if int(categories.get("insurance_withdrawal", 0)) > 0:
        actions.append("Secure backup war-risk cover and approve premium pass-through rules.")
    if int(categories.get("terminal_strike", 0)) > 0:
        actions.append("Activate terminal protection and backup loading sequence immediately.")
    if liquidity.lower() in {"moderate", "high"}:
        actions.append("Move to daily liquidity war-room review with treasury.")

    actions.extend(advisory_steps)

    deduped: list[str] = []
    seen: set[str] = set()
    for action in actions:
        if action in seen:
            continue
        seen.add(action)
        deduped.append(action)
        if len(deduped) == 3:
            break
    return deduped


def build_chat_advice(
    *,
    question: str,
    simulation: dict[str, Any],
    advisory: dict[str, Any],
    live_intel: dict[str, Any],
    learning_lessons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return simple-language, auditable advisory output for chat UX."""
    question_clean = " ".join(question.split())
    topic = _topic(question)
    intent = _question_intent(question)
    ops = simulation["operational_disruption"]
    company = simulation["company_exposure"]
    advisory_steps = list(advisory.get("recommended_steps", []))
    next_actions = _topic_actions(topic, advisory_steps, simulation, live_intel)[:3]

    tier = int(simulation["effective_tier"])
    duration = int(simulation["duration_days"])
    throughput_mid = float(ops["throughput_reduction_pct"]["mid"])
    insurance_mid = float(ops["insurance_premium_increase_pct"]["mid"])
    lng_mid = float(ops["lng_delay_probability_pct"]["mid"])
    liquidity = str(company.get("liquidity_stress_indicator", "Unknown"))
    alert_level = str(advisory.get("alert_level", "Routine"))
    signal_summary = live_intel.get("signal_summary", {})
    critical = int(signal_summary.get("critical_count", 0))
    elevated = int(signal_summary.get("elevated_count", 0))
    category_counts = signal_summary.get("category_counts", {})
    top_category = "none"
    if category_counts:
        top_category = sorted(category_counts.items(), key=lambda item: item[1], reverse=True)[0][0]

    lessons_note = ""
    if learning_lessons:
        top_titles = [str(item.get("title", "")).strip() for item in learning_lessons if item.get("title")]
        if top_titles:
            lessons_note = f" Prior lessons used: {', '.join(top_titles[:2])}."

    focus_line = {
        "liquidity": "Primary focus: protect cash and debt headroom before stress compounds.",
        "shipping": "Primary focus: preserve export continuity and cargo sequencing.",
        "insurance": "Primary focus: keep insurance coverage continuous despite repricing.",
        "trigger": "Primary focus: tighten thresholds and escalation governance.",
        "oil": "Primary focus: align hedging and nominations with price-band volatility.",
        "immediate": "Primary focus: execute the next 24-hour action sequence cleanly.",
        "general": "Primary focus: sequence operations, insurance, and liquidity actions in parallel.",
    }[topic]

    intent_line = {
        "priority": "Priority order is based on highest immediate downside to exports and cash.",
        "rationale": "These actions are selected because they reduce downside first, then protect optionality.",
        "risk": "Biggest current risk is disruption compounding across shipping, insurance, and liquidity.",
        "timeline": "Use a 24-hour, 7-day, and 30-day cadence for action checkpoints.",
        "general": "This recommendation is tied to the current simulated exposure profile.",
    }[intent]

    answer = (
        f'You asked: "{question_clean}". '
        f"Current Sentinel view: Tier {tier} over {duration} days with {alert_level} alert. "
        f"Midpoint stress is throughput {throughput_mid:.1f}%, insurance {insurance_mid:.1f}%, "
        f"LNG delay {lng_mid:.1f}%, and liquidity risk is {liquidity}. "
        f"Live signals: {critical} critical and {elevated} elevated, top category is {top_category}. "
        f"{focus_line} {intent_line} "
        f"{lessons_note}"
        "This is scenario translation, not war prediction."
    )

    evidence = _top_evidence(live_intel)
    return {
        "answer": answer,
        "next_actions": next_actions,
        "evidence": evidence,
        "disclaimer": (
            "Sentinel converts escalation signals into exposure guidance. "
            "It does not forecast conflict outcomes."
        ),
    }
