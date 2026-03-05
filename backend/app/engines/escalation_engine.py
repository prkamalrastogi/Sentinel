"""Escalation tier engine and trigger-based auto-upgrade logic."""

from typing import Dict, List, Tuple

from app.config import ESCALATION_TIERS, TRIGGER_RULES


def get_all_tiers() -> List[Dict[str, object]]:
    """Return all tiers sorted by index with attached metadata."""
    tiers: List[Dict[str, object]] = []
    for tier, definition in sorted(ESCALATION_TIERS.items()):
        tiers.append(
            {
                "tier": tier,
                "name": definition["name"],
                "summary": definition["summary"],
                "consequences": definition["consequences"],
            }
        )
    return tiers


def get_tier_definition(tier: int) -> Dict[str, object]:
    if tier not in ESCALATION_TIERS:
        raise ValueError(f"Unsupported escalation tier: {tier}")
    definition = ESCALATION_TIERS[tier]
    return {
        "tier": tier,
        "name": definition["name"],
        "summary": definition["summary"],
        "consequences": definition["consequences"],
    }


def _is_triggered(rule: Dict[str, object], trigger_inputs: Dict[str, float]) -> bool:
    key = str(rule["key"])
    threshold = float(rule["threshold"])
    value = float(trigger_inputs.get(key, 0.0))
    return value >= threshold


def apply_trigger_rules(
    selected_tier: int, trigger_inputs: Dict[str, float] | None
) -> Tuple[int, List[Dict[str, object]]]:
    """
    Evaluate trigger thresholds and return:
    - effective tier after auto-upgrade rules
    - list of triggered rules with context
    """
    if trigger_inputs is None:
        trigger_inputs = {}

    effective_tier = selected_tier
    triggered_rules: List[Dict[str, object]] = []

    for rule in TRIGGER_RULES:
        if not _is_triggered(rule, trigger_inputs):
            continue

        key = str(rule["key"])
        observed_value = float(trigger_inputs.get(key, 0.0))

        if rule["type"] == "delta":
            effective_tier = min(4, effective_tier + int(rule["value"]))
        elif rule["type"] == "set":
            effective_tier = max(effective_tier, int(rule["value"]))
        else:
            raise ValueError(f"Unsupported trigger type: {rule['type']}")

        triggered_rules.append(
            {
                "key": key,
                "label": rule["label"],
                "condition": rule["condition"],
                "action": rule["action"],
                "threshold": rule["threshold"],
                "observed_value": observed_value,
            }
        )

    return effective_tier, triggered_rules


def get_trigger_rules() -> List[Dict[str, object]]:
    return TRIGGER_RULES
