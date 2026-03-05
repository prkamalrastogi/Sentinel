import json
import os
import tomllib
from html import escape
from datetime import datetime, timezone
from typing import Any, Dict

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

try:
    import pydeck as pdk
except Exception:  # pragma: no cover - optional visual dependency in some environments
    pdk = None

st.set_page_config(page_title="Sentinel - GCC Energy Escalation Simulator", layout="wide")


def _load_local_secrets() -> dict[str, Any]:
    frontend_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(frontend_dir)
    candidates = [
        os.path.join(project_dir, ".streamlit", "secrets.toml"),
        os.path.join(frontend_dir, ".streamlit", "secrets.toml"),
    ]

    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as f:
                raw = tomllib.load(f)
            if isinstance(raw, dict):
                return raw
        except Exception:
            continue
    return {}


LOCAL_SECRETS = _load_local_secrets()


def get_runtime_setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value

    secret_value = LOCAL_SECRETS.get(name)
    if isinstance(secret_value, str):
        secret_value = secret_value.strip()
        if secret_value:
            return secret_value

    return default


BACKEND_URL = get_runtime_setting("SENTINEL_BACKEND_URL", "http://localhost:8000").rstrip("/")
DEFAULT_API_KEY = get_runtime_setting("SENTINEL_API_KEY", "")

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

    :root {
        --bg-top: #edf4ff;
        --bg-bottom: #dfeaf9;
        --aurora-a: rgba(28, 146, 173, 0.22);
        --aurora-b: rgba(17, 84, 138, 0.14);
        --ink-900: #0b2339;
        --ink-700: #214158;
        --muted-500: #4f6b80;
        --card-bg: rgba(255, 255, 255, 0.76);
        --card-brd: rgba(29, 74, 108, 0.18);
        --accent: #1d8bb0;
        --accent-2: #267d69;
        --warn: #b55d14;
        --danger: #b83a30;
        --mono: "IBM Plex Mono", "SFMono-Regular", Menlo, Consolas, monospace;
        --sans: "Space Grotesk", "Avenir Next", "Segoe UI", sans-serif;
    }
    html, body {
        background: var(--bg-top) !important;
        color: var(--ink-900) !important;
        font-family: var(--sans);
    }
    .stApp {
        position: relative;
        min-height: 100vh;
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        pointer-events: none;
        background:
            radial-gradient(1200px 400px at 8% -10%, var(--aurora-a), transparent 68%),
            radial-gradient(1000px 600px at 95% -15%, var(--aurora-b), transparent 64%),
            linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 100%);
    }
    .stApp::after {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        pointer-events: none;
        background: repeating-linear-gradient(
            180deg,
            rgba(18, 53, 84, 0.015),
            rgba(18, 53, 84, 0.015) 1px,
            transparent 1px,
            transparent 6px
        );
        animation: scan-drift 18s linear infinite;
    }
    @keyframes scan-drift {
        0% { transform: translateY(0); }
        100% { transform: translateY(12px); }
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMainBlockContainer"],
    [data-testid="stVerticalBlock"],
    .block-container {
        background: transparent !important;
    }
    .block-container {
        max-width: 1380px;
        padding-top: 1.2rem;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(235, 242, 252, 0.94) 0%, rgba(228, 237, 248, 0.92) 100%);
        border-right: 1px solid var(--card-brd);
        backdrop-filter: blur(8px);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span {
        color: var(--ink-900) !important;
        font-family: var(--sans) !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] input {
        border-radius: 10px !important;
        border-color: rgba(21, 64, 99, 0.28) !important;
        background: rgba(255, 255, 255, 0.85) !important;
    }
    h1, h2, h3, h4 {
        color: var(--ink-900) !important;
        font-family: var(--sans) !important;
        letter-spacing: 0.01em;
    }
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] li {
        color: var(--ink-700) !important;
        font-family: var(--sans) !important;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(var(--card-bg), var(--card-bg)) padding-box,
            linear-gradient(135deg, rgba(29, 139, 176, 0.4), rgba(40, 104, 145, 0.14)) border-box;
        border: 1px solid transparent;
        border-radius: 12px;
        padding: 8px 12px;
        box-shadow: 0 10px 24px rgba(8, 39, 66, 0.08);
        backdrop-filter: blur(5px);
    }
    [data-testid="stMetricLabel"] > div {
        font-family: var(--mono) !important;
        color: var(--muted-500) !important;
        font-size: 0.8rem !important;
        letter-spacing: 0.03em;
        text-transform: uppercase;
    }
    [data-testid="stMetricValue"] {
        color: var(--ink-900) !important;
    }
    .sentinel-note {
        border: 1px solid var(--card-brd);
        border-left: 4px solid var(--accent);
        background: var(--card-bg);
        padding: 12px 14px;
        margin-bottom: 12px;
        color: var(--ink-900);
        border-radius: 10px;
        box-shadow: 0 8px 18px rgba(17, 57, 87, 0.08);
    }
    .sentinel-panel {
        border: 1px solid var(--card-brd);
        background: var(--card-bg);
        border-radius: 10px;
        padding: 8px 10px;
        margin-bottom: 10px;
        box-shadow: 0 6px 16px rgba(11, 44, 72, 0.06);
    }
    .sentinel-hero {
        margin: 0 0 0.9rem 0;
        border: 1px solid var(--card-brd);
        border-radius: 14px;
        overflow: hidden;
        background:
            linear-gradient(90deg, rgba(32, 84, 126, 0.18) 0%, rgba(29, 139, 176, 0.1) 40%, rgba(39, 125, 105, 0.08) 100%),
            var(--card-bg);
        box-shadow: 0 14px 28px rgba(9, 41, 68, 0.1);
    }
    .sentinel-hero-grid {
        display: grid;
        grid-template-columns: 1.8fr 1fr;
        gap: 0.75rem;
        padding: 1rem 1.1rem;
    }
    .hero-kicker {
        font-family: var(--mono);
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        color: var(--muted-500);
        text-transform: uppercase;
    }
    .hero-title {
        font-size: 1.85rem;
        line-height: 1.06;
        color: var(--ink-900);
        font-weight: 650;
        margin-top: 0.2rem;
    }
    .hero-sub {
        color: var(--ink-700);
        margin-top: 0.5rem;
        max-width: 70ch;
        font-size: 0.96rem;
    }
    .hero-rail {
        border-left: 1px solid rgba(26, 86, 128, 0.24);
        padding-left: 0.75rem;
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
        justify-content: center;
    }
    .rail-item {
        font-family: var(--mono);
        font-size: 0.78rem;
        color: #1f415b;
        letter-spacing: 0.03em;
    }
    .sentinel-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.55rem;
        margin: 0.25rem 0 0.85rem;
    }
    .status-chip {
        border: 1px solid var(--card-brd);
        background: rgba(255, 255, 255, 0.72);
        border-radius: 999px;
        padding: 0.45rem 0.72rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        min-height: 2.1rem;
        box-shadow: 0 6px 14px rgba(9, 44, 72, 0.08);
    }
    .status-label {
        font-family: var(--mono);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--muted-500);
        font-size: 0.68rem;
    }
    .status-value {
        color: var(--ink-900);
        font-weight: 640;
        font-size: 0.86rem;
        text-align: right;
        line-height: 1.15;
    }
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        margin-right: 0.45rem;
        display: inline-block;
        animation: pulse-chip 2.6s ease-in-out infinite;
    }
    .pulse-routine { background: var(--accent-2); }
    .pulse-watch { background: #5f7f2e; }
    .pulse-elevated { background: var(--warn); }
    .pulse-critical { background: var(--danger); }
    @keyframes pulse-chip {
        0%, 100% { transform: scale(0.9); opacity: 0.7; }
        50% { transform: scale(1.25); opacity: 1; }
    }
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid var(--card-brd);
        box-shadow: 0 8px 16px rgba(7, 35, 60, 0.06);
    }
    [data-testid="stDataFrame"] thead tr th {
        background: rgba(221, 233, 246, 0.95) !important;
        color: var(--ink-900) !important;
        font-family: var(--mono) !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }
    [data-testid="stRadio"] label {
        font-family: var(--mono) !important;
        color: var(--muted-500) !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    [role="radiogroup"] {
        gap: 0.4rem !important;
        flex-wrap: wrap;
    }
    [role="radiogroup"] > label {
        border: 1px solid rgba(24, 77, 114, 0.24);
        border-radius: 999px;
        padding: 0.16rem 0.75rem !important;
        background: rgba(255, 255, 255, 0.68);
        min-height: 2rem;
    }
    [role="radiogroup"] > label:has(input:checked) {
        background: rgba(30, 137, 169, 0.16);
        border-color: rgba(28, 112, 145, 0.5);
        box-shadow: 0 0 0 2px rgba(20, 108, 147, 0.08) inset;
    }
    [data-testid="stExpander"] {
        border: 1px solid var(--card-brd);
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.7);
    }
    .ticker-shell {
        border: 1px solid rgba(27, 88, 128, 0.28);
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.72);
        box-shadow: 0 8px 18px rgba(10, 43, 72, 0.08);
        display: grid;
        grid-template-columns: auto 1fr;
        align-items: center;
        overflow: hidden;
        margin: 0.2rem 0 0.9rem;
    }
    .ticker-label {
        font-family: var(--mono);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--ink-900);
        padding: 0.45rem 0.7rem;
        border-right: 1px solid rgba(27, 88, 128, 0.22);
        background: rgba(29, 139, 176, 0.16);
    }
    .ticker-wrap {
        width: 100%;
        overflow: hidden;
    }
    .ticker-track {
        white-space: nowrap;
        display: inline-block;
        padding-left: 100%;
        animation: ticker-scroll 78s linear infinite;
        animation-timing-function: linear;
        transform: translate3d(0, 0, 0);
        will-change: transform;
        color: var(--ink-700);
        font-family: var(--mono);
        font-size: 0.78rem;
        letter-spacing: 0.02em;
        line-height: 1.6;
    }
    .ticker-item {
        margin-right: 2.3rem;
    }
    @keyframes ticker-scroll {
        0% { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }
    .mode-panel {
        border: 1px solid var(--card-brd);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.74);
        box-shadow: 0 9px 20px rgba(7, 39, 66, 0.08);
        padding: 0.7rem 0.85rem;
        margin: 0 0 0.75rem;
    }
    .mode-title {
        font-family: var(--mono);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        font-size: 0.71rem;
        color: var(--muted-500);
    }
    .mode-body {
        color: var(--ink-900);
        font-weight: 560;
        margin-top: 0.25rem;
        font-size: 0.9rem;
    }
    .mode-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.45rem;
        margin-top: 0.55rem;
    }
    .mode-pill {
        border-radius: 999px;
        border: 1px solid rgba(32, 95, 132, 0.22);
        padding: 0.35rem 0.55rem;
        font-family: var(--mono);
        font-size: 0.7rem;
        color: #264a63;
        background: rgba(255, 255, 255, 0.68);
    }
    @media (max-width: 1100px) {
        .sentinel-hero-grid {
            grid-template-columns: 1fr;
        }
        .hero-rail {
            border-left: none;
            border-top: 1px solid rgba(26, 86, 128, 0.24);
            padding-left: 0;
            padding-top: 0.6rem;
        }
        .sentinel-strip {
            grid-template-columns: 1fr 1fr;
        }
        .mode-grid {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def build_headers(api_key: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if api_key.strip():
        headers["X-API-Key"] = api_key.strip()
    return headers


@st.cache_data(ttl=60)
def load_meta(api_key: str) -> Dict[str, Any]:
    response = requests.get(
        f"{BACKEND_URL}/meta/tiers",
        headers=build_headers(api_key),
        timeout=6,
    )
    response.raise_for_status()
    return response.json()


def run_scenario(
    payload: Dict[str, Any],
    api_key: str,
    enable_live_intel: bool,
    lookback_hours: int,
    max_items: int,
    include_api_sources: bool,
    providers: list[str],
) -> Dict[str, Any]:
    headers = build_headers(api_key)

    if not enable_live_intel:
        response = requests.post(
            f"{BACKEND_URL}/simulate",
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        simulation = response.json()
        return {
            "simulation": simulation,
            "live_intelligence": None,
            "advisory": None,
        }

    live_payload = {
        **payload,
        "live_intel": {
            "lookback_hours": lookback_hours,
            "max_items": max_items,
            "include_api_sources": include_api_sources,
            "providers": providers,
        },
    }
    response = requests.post(
        f"{BACKEND_URL}/simulate/live",
        json=live_payload,
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def run_advisor_chat(
    *,
    payload: Dict[str, Any],
    question: str,
    chat_history: list[dict[str, str]],
    api_key: str,
    enable_live_intel: bool,
    lookback_hours: int,
    max_items: int,
    include_api_sources: bool,
    providers: list[str],
    use_ai_advisor: bool,
) -> Dict[str, Any]:
    headers = build_headers(api_key)
    chat_payload = {
        **payload,
        "question": question,
        "enable_live_intel": enable_live_intel,
        "use_ai_advisor": use_ai_advisor,
        "live_intel": {
            "lookback_hours": lookback_hours,
            "max_items": max_items,
            "include_api_sources": include_api_sources,
            "providers": providers,
        },
        "chat_history": chat_history[-10:],
    }
    response = requests.post(
        f"{BACKEND_URL}/advisor/chat",
        json=chat_payload,
        headers=headers,
        timeout=25,
    )
    response.raise_for_status()
    return response.json()


def add_learning_entry(entry: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    response = requests.post(
        f"{BACKEND_URL}/learning/entries",
        json=entry,
        headers=build_headers(api_key),
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=45)
def load_learning_entries(api_key: str, limit: int = 120) -> list[Dict[str, Any]]:
    response = requests.get(
        f"{BACKEND_URL}/learning/entries",
        params={"limit": limit},
        headers=build_headers(api_key),
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


def parse_url_list(raw: str) -> list[str]:
    urls: list[str] = []
    for line in raw.splitlines():
        normalized = line.strip()
        if not normalized:
            continue
        if normalized.startswith(("http://", "https://")):
            urls.append(normalized)
    return urls


WORLDMONITOR_PARITY_WIDGETS = [
    {
        "title": "World Monitor Main",
        "category": "Global Dashboard",
        "url": "https://worldmonitor.app",
    },
    {
        "title": "MarineTraffic Gulf View",
        "category": "Maritime Tracking",
        "url": "https://www.marinetraffic.com/en/ais/home/centerx:56.2/centery:25.4/zoom:6",
    },
    {
        "title": "Flightradar24 Middle East",
        "category": "Aviation Tracking",
        "url": "https://www.flightradar24.com/28.40,51.20/5",
    },
    {
        "title": "Google News Hormuz",
        "category": "News Feed",
        "url": "https://news.google.com/search?q=Strait%20of%20Hormuz",
    },
]


def _source_channel(provider_id: str, source_name: str) -> str:
    key = f"{provider_id} {source_name}".lower()
    if any(token in key for token in ["hormuz", "shipping", "tanker", "lng"]):
        return "Maritime + Energy"
    if any(token in key for token in ["reuters", "ap", "bbc", "cnn", "guardian", "nyt", "al jazeera"]):
        return "Global News"
    if any(token in key for token in ["reddit"]):
        return "OSINT Threads"
    if any(token in key for token in ["google"]):
        return "Aggregated News Search"
    return "General Intelligence"


def build_worldmonitor_parity_table(live_intel: Dict[str, Any] | None) -> pd.DataFrame:
    if not live_intel:
        return pd.DataFrame(columns=["Channel", "Source", "Type", "Status", "Items"])

    rows: list[dict[str, Any]] = []
    for item in live_intel.get("source_status", []):
        provider_id = str(item.get("provider_id", ""))
        source_name = str(item.get("source", provider_id))
        rows.append(
            {
                "Channel": _source_channel(provider_id, source_name),
                "Source": source_name,
                "Type": str(item.get("provider_type", "unknown")).upper(),
                "Status": str(item.get("status", "unknown")).upper(),
                "Items": int(item.get("items_collected", 0)),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Channel", "Status", "Items"], ascending=[True, True, False], ignore_index=True)
    return df


def render_external_embed(title: str, url: str, *, height: int = 320, key_suffix: str = "") -> None:
    st.markdown(f"**{title}**")
    st.caption(f"Source: {url}")
    try:
        components.iframe(url, height=height, scrolling=True)
    except Exception:
        st.info("Embed unavailable in this environment.")
    button_key = f"open_src_{abs(hash((title, url, key_suffix)))}"
    st.link_button(f"Open {title}", url, use_container_width=True, key=button_key)


def pct_band(value: Dict[str, float]) -> str:
    return f"{value['low']:.1f}% - {value['high']:.1f}%"


def score_band(value: Dict[str, float]) -> str:
    return f"{value['low']:.1f} - {value['high']:.1f}"


def fmt_bn(label_value: str) -> str:
    return f"{label_value} bn"


def build_operational_table(ops: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Metric": "Export throughput reduction",
                "Range": pct_band(ops["throughput_reduction_pct"]),
                "Midpoint": f"{ops['throughput_reduction_pct']['mid']:.1f}%",
            },
            {
                "Metric": "Shipping insurance premium increase",
                "Range": pct_band(ops["insurance_premium_increase_pct"]),
                "Midpoint": f"{ops['insurance_premium_increase_pct']['mid']:.1f}%",
            },
            {
                "Metric": "LNG delay probability",
                "Range": pct_band(ops["lng_delay_probability_pct"]),
                "Midpoint": f"{ops['lng_delay_probability_pct']['mid']:.1f}%",
            },
            {
                "Metric": "Refinery margin stress indicator",
                "Range": score_band(ops["refinery_margin_stress"]["score"]),
                "Midpoint": f"{ops['refinery_margin_stress']['score']['mid']:.1f}",
            },
        ]
    )


def build_exposure_table(company: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Output": "Revenue impact band (vs break-even baseline)",
                "Value": fmt_bn(company["revenue_impact_band_usd_bn"]["label"]),
            },
            {
                "Output": "Scenario revenue band",
                "Value": fmt_bn(company["scenario_revenue_band_usd_bn"]["label"]),
            },
            {"Output": "Liquidity stress indicator", "Value": company["liquidity_stress_indicator"]},
            {"Output": "Export disruption severity", "Value": company["export_disruption_severity"]},
        ]
    )


def build_headline_table(live_intel: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in live_intel.get("headlines", []):
        rows.append(
            {
                "Published (UTC)": item.get("published_utc") or "n/a",
                "Source": item.get("source", ""),
                "Provider": item.get("provider_id", ""),
                "Type": item.get("provider_type", ""),
                "Signal Level": item.get("signal_level", "none"),
                "Categories": ", ".join(item.get("signal_categories", [])),
                "Headline": item.get("title", ""),
                "Link": item.get("link", ""),
            }
        )
    return pd.DataFrame(rows)


def build_world_event_table(world_monitor_layer: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for event in world_monitor_layer.get("events", []):
        rows.append(
            {
                "Published (UTC)": event.get("published_utc") or "n/a",
                "Severity": event.get("severity", ""),
                "Type": event.get("event_type", ""),
                "Region": event.get("region", ""),
                "Source": event.get("source", ""),
                "Confidence": event.get("confidence", ""),
                "Title": event.get("title", ""),
                "Link": event.get("link", ""),
            }
        )
    return pd.DataFrame(rows)


def build_signal_counts(signal_summary: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Signal": "Critical", "Count": signal_summary.get("critical_count", 0)},
            {"Signal": "Elevated", "Count": signal_summary.get("elevated_count", 0)},
            {"Signal": "Watch", "Count": signal_summary.get("watch_count", 0)},
            {"Signal": "Neutral", "Count": signal_summary.get("neutral_count", 0)},
        ]
    )


def build_provider_health(provider_summary: Dict[str, Any]) -> pd.DataFrame:
    api = provider_summary.get("api_sources", {})
    rss = provider_summary.get("rss_sources", {})
    return pd.DataFrame(
        [
            {
                "Provider Type": "RSS",
                "Healthy": rss.get("healthy", 0),
                "Total": rss.get("total", 0),
            },
            {
                "Provider Type": "API",
                "Healthy": api.get("healthy", 0),
                "Total": api.get("total", 0),
            },
        ]
    )


def build_headline_timeline(live_intel: Dict[str, Any]) -> pd.DataFrame:
    timestamps: list[datetime] = []
    for item in live_intel.get("headlines", []):
        raw = item.get("published_utc")
        if not raw:
            continue
        parsed = pd.to_datetime(raw, utc=True, errors="coerce")
        if pd.isna(parsed):
            continue
        timestamps.append(parsed.to_pydatetime())

    if not timestamps:
        return pd.DataFrame(columns=["Hour (UTC)", "Headlines"])

    hourly = pd.Series(timestamps, dtype="datetime64[ns, UTC]").dt.floor("h")
    grouped = (
        hourly.to_frame(name="Hour (UTC)")
        .groupby("Hour (UTC)")
        .size()
        .reset_index(name="Headlines")
    )
    return grouped


def build_threat_ticker_items(
    live_intel: Dict[str, Any] | None,
    advisory: Dict[str, Any] | None,
    world_monitor_layer: Dict[str, Any] | None,
) -> list[str]:
    items: list[str] = []
    if advisory:
        items.append(
            f"ALERT {advisory.get('alert_level', 'Routine')} | SCORE {advisory.get('advisory_score', 0)}"
        )

    if live_intel:
        signal = live_intel.get("signal_summary", {})
        items.append(
            f"SIGNALS C:{signal.get('critical_count', 0)} E:{signal.get('elevated_count', 0)} W:{signal.get('watch_count', 0)}"
        )
        for thread in live_intel.get("thread_summary", [])[:3]:
            items.append(f"THREAD {thread.get('category', 'n/a')}: {thread.get('count', 0)}")
        for headline in live_intel.get("headlines", [])[:4]:
            title = str(headline.get("title", "Untitled")).strip()
            source = str(headline.get("source", "source")).strip()
            if title:
                items.append(f"{source}: {title[:90]}")

    if world_monitor_layer:
        for sev in world_monitor_layer.get("heatmaps", {}).get("severity", [])[:2]:
            items.append(f"EVENT SEVERITY {sev.get('severity', 'Info')}: {sev.get('count', 0)}")

    # Keep ticker compact but meaningful.
    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= 12:
            break
    return deduped


def render_threat_ticker(items: list[str]) -> None:
    if not items:
        return

    chunks = "".join(f'<span class="ticker-item">{escape(item)}</span>' for item in items)
    # duplicate chunks once for smoother loop continuity
    track = chunks + chunks
    total_chars = sum(len(item) for item in items)
    duration_seconds = max(62, min(128, int(total_chars / 4)))
    st.markdown(
        f"""
        <div class="ticker-shell">
          <div class="ticker-label">Live Threat Ticker</div>
          <div class="ticker-wrap">
            <div class="ticker-track" style="animation-duration:{duration_seconds}s;">{track}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


REGION_COORDS = {
    "Strait of Hormuz": {"lat": 26.566, "lon": 56.25},
    "GCC": {"lat": 24.0, "lon": 47.0},
    "Iran": {"lat": 32.4, "lon": 53.7},
    "Iraq": {"lat": 33.2, "lon": 43.7},
    "Levant": {"lat": 33.2, "lon": 36.3},
    "Global": {"lat": 22.0, "lon": 25.0},
}


def build_region_density_map_df(world_monitor_layer: Dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in world_monitor_layer.get("heatmaps", {}).get("region", []):
        region = str(item.get("region", "Global"))
        coord = REGION_COORDS.get(region)
        if not coord:
            continue
        count = int(item.get("count", 0))
        rows.append(
            {
                "region": region,
                "lat": coord["lat"],
                "lon": coord["lon"],
                "count": count,
                "weight": max(1, count) * 18000,
            }
        )
    return pd.DataFrame(rows)


def render_region_density_map(world_monitor_layer: Dict[str, Any]) -> None:
    map_df = build_region_density_map_df(world_monitor_layer)
    if map_df.empty:
        st.info("No mappable region density available for this scenario.")
        return

    if pdk is None:
        st.warning("Map rendering unavailable in this environment. Showing density table instead.")
        st.dataframe(map_df[["region", "count", "lat", "lon"]], hide_index=True, use_container_width=True)
        return

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=map_df,
        get_position="[lon, lat]",
        get_radius="weight",
        radius_min_pixels=8,
        radius_max_pixels=48,
        get_fill_color="[29 + count*10, 139, 176, 130]",
        stroked=True,
        get_line_color=[25, 74, 111, 180],
        line_width_min_pixels=1,
        pickable=True,
    )
    view_state = pdk.ViewState(latitude=25, longitude=49, zoom=2.9, pitch=28, bearing=12)
    deck = pdk.Deck(
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        initial_view_state=view_state,
        layers=[layer],
        tooltip={"html": "<b>{region}</b><br/>Events: {count}", "style": {"color": "white"}},
    )
    st.pydeck_chart(deck, use_container_width=True)


def render_mode_brief(
    mission_mode: str,
    simulation: Dict[str, Any],
    advisory: Dict[str, Any] | None,
    live_intel: Dict[str, Any] | None,
) -> None:
    ops = simulation["operational_disruption"]
    throughput_mid = float(ops["throughput_reduction_pct"]["mid"])
    insurance_mid = float(ops["insurance_premium_increase_pct"]["mid"])
    lng_mid = float(ops["lng_delay_probability_pct"]["mid"])
    liquidity = simulation["company_exposure"]["liquidity_stress_indicator"]
    alert_level = advisory.get("alert_level", "Routine") if advisory else "Routine"

    if mission_mode == "Operator":
        body = (
            f"Operator mode prioritizes operational continuity. "
            f"Current stress: throughput {throughput_mid:.1f}%, LNG delay {lng_mid:.1f}%."
        )
        pills = ["Transit continuity", "Terminal readiness", "LNG slot protection"]
    elif mission_mode == "Board":
        body = (
            f"Board mode compresses decision risk. Alert {alert_level}, liquidity {liquidity}, "
            f"insurance stress {insurance_mid:.1f}%."
        )
        pills = ["Capital protection", "Governance cadence", "Stakeholder briefings"]
    else:
        body = (
            f"Trader mode focuses on market positioning. Oil regime {simulation['oil_regime']['band_label']} "
            f"with insurance stress {insurance_mid:.1f}%."
        )
        pills = ["Hedging posture", "Nomination timing", "Basis risk watch"]

    pills_html = "".join(f'<div class="mode-pill">{escape(item)}</div>' for item in pills)
    st.markdown(
        f"""
        <div class="mode-panel">
          <div class="mode-title">{escape(mission_mode)} Command Layout</div>
          <div class="mode-body">{escape(body)}</div>
          <div class="mode-grid">{pills_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_download_bundle(result: Dict[str, Any]) -> Dict[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    simulation = result["simulation"]
    ops_table = build_operational_table(simulation["operational_disruption"])
    exposure_table = build_exposure_table(simulation["company_exposure"])
    risk_table = pd.DataFrame(simulation["company_exposure"]["risk_heat_map"])

    csv_sections = [
        "Operational Disruption\n" + ops_table.to_csv(index=False),
        "Company Exposure\n" + exposure_table.to_csv(index=False),
        "Risk Heat Map\n" + risk_table.to_csv(index=False),
    ]

    if result.get("live_intelligence"):
        headline_table = build_headline_table(result["live_intelligence"])
        csv_sections.append("Live News Threads\n" + headline_table.to_csv(index=False))
    if result.get("world_monitor_layer"):
        world_table = build_world_event_table(result["world_monitor_layer"])
        csv_sections.append("World Monitor Connector Events\n" + world_table.to_csv(index=False))

    advisory = result.get("advisory") or {}
    simulation = result["simulation"]
    company = simulation["company_exposure"]

    brief_lines = [
        "Sentinel Executive Brief",
        f"Generated at (UTC): {timestamp}",
        "",
        f"Selected Tier: {simulation['selected_tier']}",
        f"Effective Tier: {simulation['effective_tier']}",
        f"Duration: {simulation['duration_days']} days",
        f"Oil Band: {simulation['oil_regime']['band_label']} {simulation['oil_regime']['currency']}",
        f"Liquidity Stress: {company['liquidity_stress_indicator']}",
        f"Export Disruption Severity: {company['export_disruption_severity']}",
        "",
    ]
    if advisory:
        brief_lines.append(
            f"Alert Level: {advisory.get('alert_level', 'Routine')} (Score {advisory.get('advisory_score', 0)})"
        )
        brief_lines.append("")
        brief_lines.append("Top Recommended Steps:")
        for step in advisory.get("recommended_steps", [])[:6]:
            brief_lines.append(f"- {step}")

    json_bundle = {
        "generated_at_utc": timestamp,
        "result": result,
        "note": (
            "Sentinel is a structured exposure simulator. It does not predict conflict outcomes."
        ),
    }

    return {
        "json": json.dumps(json_bundle, indent=2),
        "csv": "\n".join(csv_sections),
        "brief": "\n".join(brief_lines),
    }


st.markdown(
    """
    <section class="sentinel-hero">
      <div class="sentinel-hero-grid">
        <div>
          <div class="hero-kicker">Sentinel Control Mesh</div>
          <div class="hero-title">GCC Energy Escalation Simulator</div>
          <div class="hero-sub">
            Strategic decision console translating live geopolitical escalation into operational and financial exposure.
          </div>
        </div>
        <div class="hero-rail">
          <div class="rail-item">Signal Layer -> Event Layer -> Exposure Layer</div>
          <div class="rail-item">Geography: GCC States + Strait of Hormuz</div>
          <div class="rail-item">Decision Mode: Scenario Translation</div>
        </div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Backend Access")
    api_key = st.text_input("Backend API key (optional)", value=DEFAULT_API_KEY, type="password")
    st.caption("Leave this blank unless backend authentication is enabled.")

try:
    meta = load_meta(api_key)
except Exception as exc:
    st.error(
        "Backend is unavailable or unauthorized. Ensure FastAPI is running and set API key if required."
    )
    st.caption(str(exc))
    st.stop()

st.markdown(
    f"""
    <div class="sentinel-note">
        <strong>Core principle:</strong> {meta['principle']}
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption("Geographic scope: " + ", ".join(meta["scope"]))

tier_options = {f"Tier {t['tier']} - {t['name']}": t["tier"] for t in meta["tiers"]}
duration_options = meta["durations_days"]
provider_meta = meta.get("live_intelligence_providers", {})
api_provider_ids = [item.get("id") for item in provider_meta.get("api", []) if item.get("id")]
rss_provider_ids = [item.get("id") for item in provider_meta.get("rss", []) if item.get("id")]
default_company_profile = meta.get("default_company_profile") or meta.get("mock_company_profile") or {}

company_defaults = {
    "company_profile_name": str(default_company_profile.get("name", "Emirates National Oil Company (ENOC)")),
    "company_daily_export_volume_bpd": float(default_company_profile.get("daily_export_volume_bpd", 569_863)),
    "company_break_even_usd_per_bbl": float(
        default_company_profile.get("fiscal_break_even_price_usd_per_bbl", 45.0)
    ),
    "company_debt_obligations_usd_bn": float(default_company_profile.get("debt_obligations_usd_bn", 1.19)),
    "company_insurance_dependency_ratio": float(default_company_profile.get("insurance_dependency_ratio", 0.78)),
}
for key, val in company_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

with st.sidebar:
    st.header("Scenario Controls")
    mission_mode = st.selectbox("Dashboard Mode", ["Operator", "Board", "Trader"], index=0)
    tier_label = st.selectbox("Escalation Tier", list(tier_options.keys()), index=0)
    selected_tier = tier_options[tier_label]
    duration_days = st.selectbox("Duration (days)", duration_options, index=0)

    st.subheader("Company Profile")
    st.text_input("Company name", key="company_profile_name")
    st.number_input(
        "Daily export volume (bpd)",
        min_value=0.0,
        step=10_000.0,
        key="company_daily_export_volume_bpd",
    )
    st.number_input(
        "Fiscal break-even price (USD/bbl)",
        min_value=0.0,
        step=1.0,
        key="company_break_even_usd_per_bbl",
    )
    st.number_input(
        "Debt obligations (USD bn)",
        min_value=0.0,
        step=0.1,
        key="company_debt_obligations_usd_bn",
    )
    st.slider(
        "Insurance dependency ratio",
        min_value=0.0,
        max_value=1.0,
        step=0.01,
        key="company_insurance_dependency_ratio",
    )
    with st.expander("ENOC data provenance (proxy)"):
        st.caption(
            "Public data is incomplete for several metrics. Defaults are editable and marked by confidence level."
        )
        confidence = default_company_profile.get("data_confidence", {})
        if isinstance(confidence, dict) and confidence:
            st.dataframe(
                pd.DataFrame(
                    [{"Metric": k, "Confidence": v} for k, v in confidence.items()]
                ),
                hide_index=True,
                use_container_width=True,
            )
        notes = default_company_profile.get("data_notes", [])
        if isinstance(notes, list):
            for note in notes:
                st.write(f"- {note}")
        sources = default_company_profile.get("sources", [])
        if isinstance(sources, list) and sources:
            source_rows = []
            for item in sources:
                if not isinstance(item, dict):
                    continue
                source_rows.append(
                    {
                        "Metric": item.get("metric", ""),
                        "Source": item.get("source", ""),
                        "URL": item.get("url", ""),
                    }
                )
            if source_rows:
                st.dataframe(pd.DataFrame(source_rows), hide_index=True, use_container_width=True)

    st.subheader("Trigger Inputs")
    terminal_strikes = st.number_input(
        "Missile strikes on export terminals", min_value=0, max_value=10, value=0
    )
    blockade_alert_level = st.select_slider("Naval blockade alert level", options=[0, 1, 2], value=0)
    insurance_withdrawal_pct = st.slider(
        "Insurance market withdrawal (%)", min_value=0, max_value=100, value=0
    )

    st.subheader("Live Intelligence")
    enable_live_intel = st.checkbox("Enable internet live feeds", value=True)
    include_api_sources = st.checkbox("Include API providers", value=True)
    use_ai_advisor = st.checkbox("Use AI advisor (if configured)", value=True)
    lookback_hours = st.selectbox("News lookback window", options=[24, 48, 72, 120], index=2)
    max_items = st.slider("Max headlines", min_value=20, max_value=100, value=40, step=10)
    provider_options = ["all"] + api_provider_ids + rss_provider_ids
    selected_providers = st.multiselect(
        "Provider selection",
        options=provider_options,
        default=["all"],
        help="Use all for full-source aggregation, or select specific providers.",
    )
    with st.expander("External Plugins"):
        use_worldmonitor_parity = st.checkbox(
            "Load World Monitor parity widget set",
            value=True,
            help="Shows category-equivalent intelligence widgets and source links when direct embedding is restricted.",
        )
        try_worldmonitor_embed = st.checkbox(
            "Try direct worldmonitor.app embed (experimental)",
            value=False,
            help="Some providers block iframe embedding. Keep off for stable layout.",
        )
        world_monitor_url = st.text_input(
            "World Monitor URL",
            value="https://worldmonitor.app",
            help="Embedded in External Intel Grid if framing is allowed by provider.",
        )
        youtube_urls_raw = st.text_area(
            "YouTube Live URLs",
            value=(
                "https://www.youtube.com/watch?v=jfKfPfyJRdk\n"
                "https://www.youtube.com/watch?v=21X5lGlDOfg"
            ),
            height=80,
        )
        live_cam_urls_raw = st.text_area(
            "Live Cam URLs",
            value="https://www.earthcam.com/",
            height=80,
        )
    configured_api_keys = provider_meta.get("api_provider_keys_present", [])
    st.caption(
        "Detected configured API keys: "
        + (", ".join(configured_api_keys) if configured_api_keys else "none")
    )
    auto_refresh_scenario = st.checkbox(
        "Auto refresh on control changes",
        value=False,
        help="Disable for smoother interactions; use Refresh Scenario button instead.",
    )
    refresh_scenario = st.button("Refresh Scenario", type="primary", use_container_width=True)

youtube_urls = parse_url_list(youtube_urls_raw)
live_cam_urls = parse_url_list(live_cam_urls_raw)

payload = {
    "tier": int(selected_tier),
    "duration_days": int(duration_days),
    "trigger_inputs": {
        "terminal_strikes": float(terminal_strikes),
        "blockade_alert_level": float(blockade_alert_level),
        "insurance_withdrawal_pct": float(insurance_withdrawal_pct),
    },
    "company_profile": {
        "name": str(st.session_state["company_profile_name"]).strip()
        or str(default_company_profile.get("name", "Company")),
        "daily_export_volume_bpd": float(st.session_state["company_daily_export_volume_bpd"]),
        "fiscal_break_even_price_usd_per_bbl": float(st.session_state["company_break_even_usd_per_bbl"]),
        "debt_obligations_usd_bn": float(st.session_state["company_debt_obligations_usd_bn"]),
        "insurance_dependency_ratio": float(st.session_state["company_insurance_dependency_ratio"]),
    },
}

scenario_signature = json.dumps(
    {
        "mission_mode": mission_mode,
        "tier": payload["tier"],
        "duration_days": payload["duration_days"],
        "trigger_inputs": payload["trigger_inputs"],
        "company_profile": payload["company_profile"],
        "enable_live_intel": enable_live_intel,
        "use_ai_advisor": use_ai_advisor,
        "auto_refresh_scenario": auto_refresh_scenario,
        "lookback_hours": int(lookback_hours),
        "max_items": int(max_items),
        "include_api_sources": include_api_sources,
        "providers": selected_providers or ["all"],
        "use_worldmonitor_parity": use_worldmonitor_parity,
        "try_worldmonitor_embed": try_worldmonitor_embed,
        "world_monitor_url": world_monitor_url,
        "youtube_urls": youtube_urls,
        "live_cam_urls": live_cam_urls,
    },
    sort_keys=True,
)
if "scenario_result" not in st.session_state:
    st.session_state["scenario_result"] = None

signature_changed = st.session_state.get("scenario_signature_last") != scenario_signature
needs_refresh = (
    st.session_state["scenario_result"] is None
    or refresh_scenario
    or (auto_refresh_scenario and signature_changed)
)

if needs_refresh:
    try:
        result = run_scenario(
            payload=payload,
            api_key=api_key,
            enable_live_intel=enable_live_intel,
            lookback_hours=int(lookback_hours),
            max_items=int(max_items),
            include_api_sources=include_api_sources,
            providers=selected_providers or ["all"],
        )
        st.session_state["scenario_result"] = result
        st.session_state["scenario_signature_last"] = scenario_signature
    except Exception as exc:
        if st.session_state["scenario_result"] is None:
            st.error("Scenario request failed.")
            st.caption(str(exc))
            st.stop()
        st.warning("Latest refresh failed; displaying last successful scenario.")
        st.caption(str(exc))

result = st.session_state["scenario_result"]
if result is None:
    st.error("Scenario result unavailable. Please click Refresh Scenario.")
    st.stop()
if signature_changed and not auto_refresh_scenario and not refresh_scenario:
    st.info("Controls changed. Click `Refresh Scenario` to apply updates.")

applied_signature = st.session_state.get("scenario_signature_last", scenario_signature)
if st.session_state.get("advisor_chat_signature") != applied_signature:
    st.session_state["advisor_chat_signature"] = applied_signature
    st.session_state["advisor_chat_history"] = []

simulation = result["simulation"]
live_intel = result.get("live_intelligence")
world_monitor_layer = result.get("world_monitor_layer")
advisory = result.get("advisory")

tier_def = simulation["tier_definition"]
oil_regime = simulation["oil_regime"]
ops = simulation["operational_disruption"]
company = simulation["company_exposure"]

alert_level = advisory.get("alert_level", "Routine") if advisory else "Routine"
pulse_class = {
    "Routine": "pulse-routine",
    "Watch": "pulse-watch",
    "Elevated": "pulse-elevated",
    "Critical": "pulse-critical",
}.get(alert_level, "pulse-watch")
sources_health = (
    f"{live_intel.get('sources_healthy', 0)}/{live_intel.get('sources_checked', 0)}"
    if live_intel
    else "n/a"
)
advisor_state = "AI-Enabled" if use_ai_advisor else "Rules-Only"
snapshot_utc = live_intel.get("generated_at_utc", "n/a") if live_intel else "n/a"

st.markdown(
    f"""
    <div class="sentinel-strip">
      <div class="status-chip">
        <div class="status-label">Alert</div>
        <div class="status-value"><span class="pulse-dot {pulse_class}"></span>{alert_level}</div>
      </div>
      <div class="status-chip">
        <div class="status-label">Effective Tier</div>
        <div class="status-value">Tier {simulation['effective_tier']}</div>
      </div>
      <div class="status-chip">
        <div class="status-label">Source Health</div>
        <div class="status-value">{sources_health}</div>
      </div>
      <div class="status-chip">
        <div class="status-label">Advisor</div>
        <div class="status-value">{advisor_state}<br/><span style="font-size:0.66rem;color:#4f6b80;">{snapshot_utc}</span></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ticker_items = build_threat_ticker_items(live_intel=live_intel, advisory=advisory, world_monitor_layer=world_monitor_layer)
render_threat_ticker(ticker_items)

render_mode_brief(
    mission_mode=mission_mode,
    simulation=simulation,
    advisory=advisory,
    live_intel=live_intel,
)

if live_intel and live_intel.get("sources_checked", 0) > 0:
    coverage_ratio = int(
        round(100 * live_intel.get("sources_healthy", 0) / live_intel.get("sources_checked", 1))
    )
    st.caption(f"Live intelligence coverage pulse: {coverage_ratio}% healthy sources")
    st.progress(coverage_ratio)

col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Effective Tier", f"Tier {simulation['effective_tier']}", tier_def["name"])
col_b.metric("Oil Price Band", oil_regime["band_label"], oil_regime["currency"])
col_c.metric("Liquidity Stress", company["liquidity_stress_indicator"])
col_d.metric("Export Disruption", company["export_disruption_severity"])

if simulation["tier_upgraded"]:
    st.warning(
        f"Auto-upgrade applied: selected Tier {simulation['selected_tier']} "
        f"-> effective Tier {simulation['effective_tier']} based on trigger thresholds."
    )

mode_view_options = {
    "Operator": [
        "Scenario Overview",
        "Operations Dashboard",
        "Live Intelligence",
        "World Event Layer",
        "External Intel Grid",
        "Action Advisory",
        "Sentinel Advisor Chat",
        "Learning Lab",
    ],
    "Board": [
        "Scenario Overview",
        "Action Advisory",
        "External Intel Grid",
        "World Event Layer",
        "Sentinel Advisor Chat",
        "Learning Lab",
    ],
    "Trader": [
        "Operations Dashboard",
        "Live Intelligence",
        "World Event Layer",
        "External Intel Grid",
        "Action Advisory",
        "Sentinel Advisor Chat",
        "Learning Lab",
    ],
}
view_options = mode_view_options.get(mission_mode, mode_view_options["Operator"])
mode_default_view = view_options[0]

if "active_view" not in st.session_state:
    st.session_state["active_view"] = mode_default_view
if st.session_state.get("last_mission_mode") != mission_mode:
    st.session_state["last_mission_mode"] = mission_mode
    st.session_state["active_view"] = mode_default_view
if st.session_state.get("force_active_view"):
    forced_view = st.session_state.pop("force_active_view")
    if forced_view in view_options:
        st.session_state["active_view"] = forced_view
if st.session_state["active_view"] not in view_options:
    st.session_state["active_view"] = mode_default_view

active_view = st.radio(
    "Console View",
    options=view_options,
    horizontal=True,
    key="active_view",
)

if active_view == "Scenario Overview":
    st.subheader("Escalation Consequences")
    st.write(tier_def["summary"])
    for consequence in tier_def["consequences"]:
        st.write(f"- {consequence}")

    profile = company["company_profile"]
    company_name = profile.get("name", "Company")
    st.subheader(f"Company Exposure Dashboard ({company_name})")
    pro1, pro2, pro3, pro4 = st.columns(4)
    pro1.metric("Daily Export Volume", f"{profile['daily_export_volume_bpd']:,.0f} bpd")
    pro2.metric("Fiscal Break-even", f"${profile['fiscal_break_even_price_usd_per_bbl']:.1f}/bbl")
    pro3.metric("Debt Obligations", f"${profile['debt_obligations_usd_bn']:.1f} bn")
    pro4.metric("Insurance Dependency", f"{profile['insurance_dependency_ratio'] * 100:.0f}%")
    profile_mode = str(profile.get("profile_mode", "")).strip()
    if profile_mode:
        st.caption("Profile mode: " + profile_mode.replace("_", " "))

    confidence = profile.get("data_confidence", {})
    if isinstance(confidence, dict) and confidence:
        st.caption("Input confidence")
        st.dataframe(
            pd.DataFrame([{"Metric": k, "Confidence": v} for k, v in confidence.items()]),
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("Profile assumptions and sources"):
        notes = profile.get("data_notes", [])
        if isinstance(notes, list) and notes:
            for note in notes:
                st.write(f"- {note}")
        sources = profile.get("sources", [])
        if isinstance(sources, list) and sources:
            source_rows = []
            for item in sources:
                if not isinstance(item, dict):
                    continue
                source_rows.append(
                    {
                        "Metric": item.get("metric", ""),
                        "Source": item.get("source", ""),
                        "URL": item.get("url", ""),
                    }
                )
            if source_rows:
                st.dataframe(pd.DataFrame(source_rows), hide_index=True, use_container_width=True)

    exp_table = build_exposure_table(company)
    st.dataframe(exp_table, hide_index=True, use_container_width=True)

    st.subheader("Risk Heat Map")
    risk_df = pd.DataFrame(company["risk_heat_map"])
    st.dataframe(risk_df, hide_index=True, use_container_width=True)

    st.subheader("Trigger-Based Alert Logic")
    trigger_rules_df = pd.DataFrame(meta["trigger_rules"])[["label", "condition", "action"]]
    st.dataframe(trigger_rules_df, hide_index=True, use_container_width=True)

    if simulation["triggered_rules"]:
        st.write("Triggered rules in this run:")
        for rule in simulation["triggered_rules"]:
            st.write(
                f"- {rule['label']}: observed {rule['observed_value']} (threshold {rule['threshold']})"
            )
    else:
        st.write("No trigger threshold crossed in this run.")

if active_view == "Operations Dashboard":
    st.subheader("Operational Disruption Model")
    ops_table = build_operational_table(ops)
    st.dataframe(ops_table, hide_index=True, use_container_width=True)

    chart_df = pd.DataFrame(
        {
            "Metric": [
                "Throughput Reduction %",
                "Insurance Premium Increase %",
                "LNG Delay Probability %",
                "Refinery Stress Score",
            ],
            "Midpoint": [
                ops["throughput_reduction_pct"]["mid"],
                ops["insurance_premium_increase_pct"]["mid"],
                ops["lng_delay_probability_pct"]["mid"],
                ops["refinery_margin_stress"]["score"]["mid"],
            ],
        }
    ).set_index("Metric")
    st.dataframe(
        chart_df.reset_index().rename(columns={"Midpoint": "Midpoint Value"}),
        hide_index=True,
        use_container_width=True,
    )

    st.write("Stress gauges")
    g1, g2 = st.columns(2)
    g3, g4 = st.columns(2)
    g1.metric("Throughput Stress", f"{ops['throughput_reduction_pct']['mid']:.1f}%")
    g1.progress(min(100, int(round(ops["throughput_reduction_pct"]["mid"]))))
    g2.metric("Insurance Stress", f"{ops['insurance_premium_increase_pct']['mid']:.1f}%")
    g2.progress(min(100, int(round(ops["insurance_premium_increase_pct"]["mid"]))))
    g3.metric("LNG Delay Stress", f"{ops['lng_delay_probability_pct']['mid']:.1f}%")
    g3.progress(min(100, int(round(ops["lng_delay_probability_pct"]["mid"]))))
    g4.metric("Refinery Stress", f"{ops['refinery_margin_stress']['score']['mid']:.1f}")
    g4.progress(min(100, int(round(ops["refinery_margin_stress"]["score"]["mid"]))))

    duration = int(simulation["duration_days"])
    oil_band_df = pd.DataFrame(
        {
            "Day": list(range(1, duration + 1)),
            "Low Price": [oil_regime["low"]] * duration,
            "High Price": [oil_regime["high"]] * duration,
        }
    )
    st.caption("Oil regime band projection over selected duration")
    st.dataframe(oil_band_df, hide_index=True, use_container_width=True)

if active_view == "Live Intelligence":
    if not live_intel:
        st.info("Live intelligence is disabled for this run.")
    else:
        st.subheader("Live Signal Dashboard")
        signal_summary = live_intel.get("signal_summary", {})
        provider_summary = live_intel.get("provider_summary", {})

        live_col1, live_col2, live_col3, live_col4 = st.columns(4)
        live_col1.metric("Critical Signals", signal_summary.get("critical_count", 0))
        live_col2.metric("Elevated Signals", signal_summary.get("elevated_count", 0))
        live_col3.metric(
            "Sources Healthy",
            f"{live_intel.get('sources_healthy', 0)}/{live_intel.get('sources_checked', 0)}",
        )
        live_col4.metric(
            "API Healthy",
            f"{provider_summary.get('api_sources', {}).get('healthy', 0)}/{provider_summary.get('api_sources', {}).get('total', 0)}",
        )

        st.caption(
            f"Snapshot: {live_intel.get('generated_at_utc', 'n/a')} | "
            f"Lookback: {live_intel.get('lookback_hours', 0)}h | "
            f"Focus filter: {'on' if live_intel.get('focus_filter_applied') else 'off'}"
        )

        signal_counts_df = build_signal_counts(signal_summary).set_index("Signal")
        provider_health_df = build_provider_health(provider_summary).set_index("Provider Type")
        c1, c2 = st.columns(2)
        c1.caption("Signal levels")
        c1.dataframe(signal_counts_df.reset_index(), hide_index=True, use_container_width=True)
        c2.caption("Provider health")
        c2.dataframe(provider_health_df.reset_index(), hide_index=True, use_container_width=True)

        timeline_df = build_headline_timeline(live_intel)
        if not timeline_df.empty:
            st.caption("Headline cadence (UTC)")
            st.dataframe(timeline_df, hide_index=True, use_container_width=True)

        if live_intel.get("fetch_warnings"):
            st.info(
                "Some live sources were temporarily unavailable: "
                + "; ".join(live_intel["fetch_warnings"][:5])
            )

        st.caption(
            "Configured API keys detected: "
            + (
                ", ".join(provider_summary.get("api_provider_keys_present", []))
                if provider_summary.get("api_provider_keys_present")
                else "none"
            )
        )

        source_status_df = pd.DataFrame(live_intel.get("source_status", []))
        if not source_status_df.empty:
            st.write("Source status")
            st.dataframe(source_status_df, hide_index=True, use_container_width=True)

        headlines_df = build_headline_table(live_intel)
        st.write("Top headlines")
        st.dataframe(headlines_df, hide_index=True, use_container_width=True)

if active_view == "World Event Layer":
    if not world_monitor_layer:
        st.info("World event connector data is unavailable.")
    else:
        st.subheader("World Monitor Connector Layer")
        st.caption(
            f"Connector: {world_monitor_layer.get('connector', 'world_monitor_adapter_v1')} | "
            f"Events normalized: {world_monitor_layer.get('events_count', 0)}"
        )

        st.caption("Animated geo density map")
        render_region_density_map(world_monitor_layer)

        heatmaps = world_monitor_layer.get("heatmaps", {})
        region_df = pd.DataFrame(heatmaps.get("region", []))
        type_df = pd.DataFrame(heatmaps.get("event_type", []))
        severity_df = pd.DataFrame(heatmaps.get("severity", []))

        hm1, hm2, hm3 = st.columns(3)
        if not region_df.empty:
            hm1.caption("Region density")
            hm1.dataframe(region_df, hide_index=True, use_container_width=True)
        if not type_df.empty:
            hm2.caption("Event type density")
            hm2.dataframe(type_df, hide_index=True, use_container_width=True)
        if not severity_df.empty:
            hm3.caption("Severity density")
            hm3.dataframe(severity_df, hide_index=True, use_container_width=True)

        wm_table = build_world_event_table(world_monitor_layer)
        st.write("Normalized event stream")
        st.dataframe(wm_table, hide_index=True, use_container_width=True)

if active_view == "External Intel Grid":
    st.subheader("External Intel Grid")
    st.caption(
        "World Monitor parity layer: Sentinel mirrors comparable signal categories "
        "and overlays them with company-impact translation."
    )
    parity_df = build_worldmonitor_parity_table(live_intel)
    if not parity_df.empty:
        p1, p2, p3 = st.columns(3)
        p1.metric("Channels Mirrored", int(parity_df["Channel"].nunique()))
        p2.metric("Sources Active", int((parity_df["Status"] == "OK").sum()))
        p3.metric("Feeds Listed", len(parity_df))
        st.write("Parity ingestion matrix")
        st.dataframe(parity_df, hide_index=True, use_container_width=True)

    parity_widgets = list(WORLDMONITOR_PARITY_WIDGETS)
    if world_monitor_url:
        parity_widgets[0] = {
            "title": "World Monitor Main",
            "category": "Global Dashboard",
            "url": world_monitor_url,
        }

    if use_worldmonitor_parity:
        st.write("World Monitor category-equivalent widgets")
        st.caption(
            "If a provider blocks iframe embedding, use the Open Source button for direct access."
        )
        w_cols = st.columns(2)
        for idx, widget in enumerate(parity_widgets):
            with w_cols[idx % 2]:
                st.caption(widget["category"])
                if widget["title"] == "World Monitor Main" and not try_worldmonitor_embed:
                    st.markdown(f"**{widget['title']}**")
                    st.info("Direct site embed disabled for stability. Open in new tab.")
                    st.link_button("Open World Monitor", widget["url"], use_container_width=True)
                else:
                    render_external_embed(widget["title"], widget["url"], height=340)
    elif world_monitor_url:
        st.markdown(f"World Monitor source: [{world_monitor_url}]({world_monitor_url})")
        if try_worldmonitor_embed:
            render_external_embed("World Monitor Main", world_monitor_url, height=520)
        else:
            st.link_button("Open World Monitor", world_monitor_url, use_container_width=True)

    media_tabs = st.tabs(["YouTube Live", "Live Cams"])
    with media_tabs[0]:
        if youtube_urls:
            y_cols = st.columns(2)
            for idx, url in enumerate(youtube_urls[:4]):
                with y_cols[idx % 2]:
                    st.video(url)
                    st.caption(url)
        else:
            st.info("No YouTube URLs configured.")

    with media_tabs[1]:
        if live_cam_urls:
            c_cols = st.columns(2)
            for idx, url in enumerate(live_cam_urls[:4]):
                with c_cols[idx % 2]:
                    render_external_embed(f"Live Cam {idx + 1}", url, height=300)
        else:
            st.info("No live cam URLs configured.")

if active_view == "Action Advisory":
    if not advisory:
        st.info("Advisory output unavailable because live intelligence is disabled.")
    else:
        st.subheader("Alert and Recommended Steps")
        adv_col1, adv_col2 = st.columns(2)
        adv_col1.metric("Alert Level", advisory.get("alert_level", "Routine"))
        adv_col2.metric("Advisory Score", advisory.get("advisory_score", 0))

        st.write("Insights")
        for insight in advisory.get("insights", []):
            st.write(f"- {insight}")

        st.write("Suggested next steps")
        for step in advisory.get("recommended_steps", []):
            st.write(f"- {step}")

        recommended_actions_df = pd.DataFrame(advisory.get("recommended_actions", []))
        if not recommended_actions_df.empty:
            st.write("Action rationale matrix")
            st.dataframe(recommended_actions_df, hide_index=True, use_container_width=True)

if active_view == "Sentinel Advisor Chat":
    st.subheader("Sentinel Security Advisor Chat")
    st.caption(
        "Ask simple questions about what to do next. Sentinel answers using the active scenario and live feeds."
    )

    if "advisor_chat_history" not in st.session_state:
        st.session_state.advisor_chat_history = []

    reset_col, suggest_col = st.columns([1, 3])
    if reset_col.button("Reset Chat", use_container_width=True):
        st.session_state.advisor_chat_history = []
        st.rerun()
    suggest_col.caption(
        "Try: `What should we do in the next 24 hours?`, "
        "`How do we reduce liquidity stress?`, "
        "`What if shipping insurance worsens?`"
    )

    if not st.session_state.advisor_chat_history:
        default_answer = (
            "I can translate this scenario into immediate actions. "
            "Ask me what to do next for shipping, liquidity, insurance, or escalation triggers."
        )
        st.session_state.advisor_chat_history.append({"role": "assistant", "content": default_answer})

    for msg in st.session_state.advisor_chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_prompt = st.chat_input("Ask Sentinel what to do next", key="advisor_chat_input")
    if user_prompt:
        st.session_state.advisor_chat_history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.write(user_prompt)

        chat_history_payload = [
            {"role": m["role"], "content": m["content"]} for m in st.session_state.advisor_chat_history[-10:]
        ]
        try:
            chat_result = run_advisor_chat(
                payload=payload,
                question=user_prompt,
                chat_history=chat_history_payload,
                api_key=api_key,
                enable_live_intel=enable_live_intel,
                lookback_hours=int(lookback_hours),
                max_items=int(max_items),
                include_api_sources=include_api_sources,
                providers=selected_providers or ["all"],
                use_ai_advisor=use_ai_advisor,
            )

            response_lines = [chat_result.get("answer", "No answer returned.")]
            mode = chat_result.get("advisor_mode", "rules")
            response_lines.append("")
            response_lines.append(f"Advisor mode: {mode}")
            actions = chat_result.get("next_actions", [])
            action_reasons = chat_result.get("next_action_reasons", [])
            reason_lookup = {
                item.get("step", ""): item.get("reason", "")
                for item in action_reasons
                if isinstance(item, dict)
            }
            if actions:
                response_lines.append("")
                response_lines.append("Recommended next steps:")
                for action in actions:
                    response_lines.append(f"- {action}")
                    if reason_lookup.get(action):
                        response_lines.append(f"  reason: {reason_lookup[action]}")

            evidence = chat_result.get("evidence", [])
            if evidence:
                response_lines.append("")
                response_lines.append("Supporting signals:")
                for item in evidence[:3]:
                    title = item.get("title", "Untitled")
                    source = item.get("source", "")
                    level = item.get("signal_level", "none")
                    link = item.get("link", "")
                    if link:
                        response_lines.append(f"- [{title}]({link}) ({source}, {level})")
                    else:
                        response_lines.append(f"- {title} ({source}, {level})")

            disclaimer = chat_result.get("disclaimer")
            if disclaimer:
                response_lines.append("")
                response_lines.append(disclaimer)

            assistant_text = "\n".join(response_lines)
        except Exception as exc:
            assistant_text = f"Advisor chat request failed: {exc}"

        st.session_state.advisor_chat_history.append({"role": "assistant", "content": assistant_text})
        st.session_state["force_active_view"] = "Sentinel Advisor Chat"
        with st.chat_message("assistant"):
            st.write(assistant_text)

if active_view == "Learning Lab":
    st.subheader("Learning Lab")
    st.caption(
        "Capture outcomes and lessons so Sentinel can reuse institutional memory in future recommendations."
    )

    with st.form("learning_form", clear_on_submit=True):
        learn_title = st.text_input("Case title", placeholder="Hormuz insurance squeeze - March review")
        learn_obs = st.text_area("Observation", height=90)
        learn_action = st.text_area("Action taken", height=90)
        learn_outcome = st.text_area("Outcome", height=90)
        learn_lesson = st.text_area("Lesson learned", height=90)
        learn_tags = st.text_input("Tags (comma separated)", placeholder="insurance, shipping, liquidity")
        submit_learning = st.form_submit_button("Save Learning Entry", use_container_width=True)

    if submit_learning:
        try:
            payload_learning = {
                "title": learn_title,
                "observation": learn_obs,
                "action_taken": learn_action,
                "outcome": learn_outcome,
                "lesson": learn_lesson,
                "tags": [tag.strip().lower() for tag in learn_tags.split(",") if tag.strip()],
            }
            add_learning_entry(payload_learning, api_key=api_key)
            load_learning_entries.clear()
            st.success("Learning entry saved.")
        except Exception as exc:
            st.error(f"Unable to save learning entry: {exc}")

    try:
        entries = load_learning_entries(api_key=api_key, limit=150)
    except Exception as exc:
        entries = []
        st.error(f"Unable to load learning log: {exc}")

    if entries:
        entries_df = pd.DataFrame(entries)
        st.write("Recent learning entries")
        st.dataframe(entries_df, hide_index=True, use_container_width=True)
    else:
        st.info("No learning entries yet. Add one above to initialize the training ground.")

bundle = build_download_bundle(result)

st.subheader("Final Output")
d0, d1, d2 = st.columns(3)
d0.download_button(
    label="Download Executive Brief",
    data=bundle["brief"],
    file_name="sentinel_executive_brief.txt",
    mime="text/plain",
)
d1.download_button(
    label="Download Scenario JSON",
    data=bundle["json"],
    file_name="sentinel_scenario_output.json",
    mime="application/json",
)
d2.download_button(
    label="Download Scenario CSV",
    data=bundle["csv"],
    file_name="sentinel_scenario_output.csv",
    mime="text/csv",
)

if advisory:
    st.caption(
        f"Decision snapshot: Alert {advisory.get('alert_level', 'Routine')} | "
        f"Score {advisory.get('advisory_score', 0)} | "
        f"Liquidity {company.get('liquidity_stress_indicator', 'n/a')}."
    )

with st.expander("Model Transparency (Editable Inputs and Outputs)"):
    transparency_payload = {
        "simulation": {
            "selected_tier": simulation["selected_tier"],
            "effective_tier": simulation["effective_tier"],
            "duration_days": simulation["duration_days"],
            "oil_band": oil_regime,
            "operational_disruption_midpoints": {
                "throughput_reduction_pct": ops["throughput_reduction_pct"]["mid"],
                "insurance_premium_increase_pct": ops["insurance_premium_increase_pct"]["mid"],
                "lng_delay_probability_pct": ops["lng_delay_probability_pct"]["mid"],
                "refinery_margin_stress_score": ops["refinery_margin_stress"]["score"]["mid"],
            },
            "company_outputs": {
                "revenue_impact_band_usd_bn": company["revenue_impact_band_usd_bn"],
                "liquidity_stress_indicator": company["liquidity_stress_indicator"],
                "export_disruption_severity": company["export_disruption_severity"],
            },
        },
        "live_intelligence": live_intel,
        "world_monitor_layer": world_monitor_layer,
        "advisory": advisory,
    }
    st.json(transparency_payload)
