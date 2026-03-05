"""World Monitor style connector layer for normalized event intelligence."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


REGION_KEYWORDS = {
    "Strait of Hormuz": ["hormuz", "strait"],
    "GCC": ["gcc", "saudi", "uae", "qatar", "kuwait", "oman", "bahrain"],
    "Levant": ["israel", "lebanon", "syria", "gaza"],
    "Iraq": ["iraq", "basra", "baghdad"],
    "Iran": ["iran", "tehran"],
    "Global": [],
}

ASSET_KEYWORDS = {
    "Export terminal": ["terminal", "port", "loading"],
    "Shipping lane": ["shipping", "lane", "transit", "strait", "tanker"],
    "LNG logistics": ["lng", "cargo"],
    "Refining": ["refinery", "margin", "crack spread"],
    "Insurance market": ["insurance", "underwriter", "premium", "war-risk"],
}

SIGNAL_TO_EVENT_TYPE = {
    "terminal_strike": "Infrastructure Attack",
    "blockade_alert": "Maritime Disruption",
    "insurance_withdrawal": "Insurance Stress",
    "shipping_disruption": "Logistics Disruption",
    "energy_market_stress": "Market Stress",
}

SIGNAL_TO_TAGS = {
    "terminal_strike": "critical_infrastructure",
    "blockade_alert": "maritime_access",
    "insurance_withdrawal": "insurance_liquidity",
    "shipping_disruption": "shipping_continuity",
    "energy_market_stress": "price_volatility",
}

MAX_EVENT_SUMMARY_LENGTH = 420


def _severity(level: str) -> str:
    mapping = {
        "critical": "Critical",
        "elevated": "Elevated",
        "watch": "Watch",
    }
    return mapping.get(level, "Info")


def _infer_region(text: str) -> str:
    text_lower = text.lower()
    for region, keywords in REGION_KEYWORDS.items():
        if not keywords:
            continue
        if any(keyword in text_lower for keyword in keywords):
            return region
    return "Global"


def _infer_assets(text: str) -> list[str]:
    text_lower = text.lower()
    assets: list[str] = []
    for asset, keywords in ASSET_KEYWORDS.items():
        if any(keyword in text_lower for keyword in keywords):
            assets.append(asset)
    return assets


def _infer_event_type(signal_categories: list[str]) -> str:
    for category in signal_categories:
        event_type = SIGNAL_TO_EVENT_TYPE.get(category)
        if event_type:
            return event_type
    return "General Geopolitical Update"


def _event_tags(signal_categories: list[str], assets: list[str], region: str) -> list[str]:
    tags: set[str] = set()
    for category in signal_categories:
        tag = SIGNAL_TO_TAGS.get(category)
        if tag:
            tags.add(tag)
    for asset in assets:
        tags.add(asset.lower().replace(" ", "_"))
    tags.add(region.lower().replace(" ", "_"))
    return sorted(tags)


def _confidence_score(item: dict[str, Any], provider_summary: dict[str, Any]) -> float:
    relevance = float(item.get("relevance_score", 0))
    signal_level = str(item.get("signal_level", "none"))
    coverage_ratio = 0.0

    total = float(provider_summary.get("total_sources", 0) or 0)
    healthy = float(provider_summary.get("healthy_sources", 0) or 0)
    if total > 0:
        coverage_ratio = healthy / total

    score = 0.35 + min(0.35, relevance * 0.03) + (coverage_ratio * 0.2)
    if signal_level == "critical":
        score += 0.15
    elif signal_level == "elevated":
        score += 0.08
    elif signal_level == "watch":
        score += 0.03

    return round(min(0.98, score), 2)


def _event_id(title: str, published_utc: str | None) -> str:
    raw = f"{title}|{published_utc or ''}".encode("utf-8", "ignore")
    return "wm-" + hashlib.sha1(raw).hexdigest()[:12]


def _compact_summary(summary: str) -> str:
    normalized = " ".join(summary.split()).strip()
    if len(normalized) <= MAX_EVENT_SUMMARY_LENGTH:
        return normalized
    return normalized[: MAX_EVENT_SUMMARY_LENGTH - 3].rstrip() + "..."


def _aggregate_counts(events: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for event in events:
        value = str(event.get(key, "Unknown"))
        counts[value] = counts.get(value, 0) + 1
    return [
        {key: name, "count": count}
        for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)
    ]


def build_world_monitor_layer(live_intel: dict[str, Any], max_events: int = 25) -> dict[str, Any]:
    """
    Normalize live feed headlines into a world-monitor style event layer.
    This forms a connector between broad signal observation and Sentinel modeling.
    """
    headlines = live_intel.get("headlines", [])[:max_events]
    provider_summary = live_intel.get("provider_summary", {})
    events: list[dict[str, Any]] = []

    for item in headlines:
        title = str(item.get("title", "")).strip()
        summary = str(item.get("summary", "")).strip()
        if not title:
            continue

        signal_categories = item.get("signal_categories", [])
        combined_text = f"{title} {summary}".strip()
        region = _infer_region(combined_text)
        assets = _infer_assets(combined_text)
        event_type = _infer_event_type(signal_categories)
        severity = _severity(str(item.get("signal_level", "none")))
        published_utc = item.get("published_utc")

        events.append(
            {
                "event_id": _event_id(title, published_utc),
                "event_type": event_type,
                "severity": severity,
                "title": title,
                "summary": _compact_summary(summary),
                "region": region,
                "assets_exposed": assets,
                "source": item.get("source", ""),
                "provider_id": item.get("provider_id", ""),
                "provider_type": item.get("provider_type", ""),
                "published_utc": published_utc,
                "confidence": _confidence_score(item, provider_summary),
                "tags": _event_tags(signal_categories, assets, region),
                "link": item.get("link", ""),
            }
        )

    region_heatmap = _aggregate_counts(events, "region")
    type_heatmap = _aggregate_counts(events, "event_type")
    severity_heatmap = _aggregate_counts(events, "severity")

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "connector": "world_monitor_adapter_v1",
        "events_count": len(events),
        "events": events,
        "heatmaps": {
            "region": region_heatmap,
            "event_type": type_heatmap,
            "severity": severity_heatmap,
        },
        "thread_summary": live_intel.get("thread_summary", []),
        "provider_summary": provider_summary,
    }
