"""Editable model assumptions for the Sentinel GCC simulator."""

from typing import Any, Dict, List

# Geographic scope stays explicit in API metadata and UI.
GEOGRAPHIC_SCOPE: List[str] = ["GCC states", "Strait of Hormuz"]

# Only 7/30/90 day scenarios are enabled for the MVP.
DURATION_OPTIONS_DAYS: List[int] = [7, 30, 90]

# Tier definitions and structured consequence notes.
ESCALATION_TIERS: Dict[int, Dict[str, object]] = {
    0: {
        "name": "Normal stability",
        "summary": "Routine regional risk environment with stable maritime operations.",
        "consequences": [
            "Baseline export continuity",
            "Standard insurance terms",
            "Low probability of LNG logistics delay",
        ],
    },
    1: {
        "name": "Limited strike exchange",
        "summary": "Localized exchange of strikes with limited spillover.",
        "consequences": [
            "Moderate export scheduling friction",
            "Selective increase in voyage insurance premia",
            "Early refinery margin pressure",
        ],
    },
    2: {
        "name": "Sustained cross-border attacks",
        "summary": "Repeated cross-border action affecting key transport confidence.",
        "consequences": [
            "Meaningful throughput and loading reductions",
            "Higher rerouting and convoy requirements",
            "Growing LNG delay probability",
        ],
    },
    3: {
        "name": "Regional proxy spillover",
        "summary": "Multi-theater pressure with broader operational uncertainty.",
        "consequences": [
            "Material export interruption risk across multiple corridors",
            "Strong insurance repricing and selective capacity withdrawal",
            "High refinery margin stress and working-capital volatility",
        ],
    },
    4: {
        "name": "Hormuz disruption",
        "summary": "Direct stress on Strait of Hormuz transit continuity.",
        "consequences": [
            "Severe throughput dislocation",
            "Extreme shipping insurance volatility",
            "Elevated LNG delay and inventory management risk",
        ],
    },
}

# Base oil bands (USD/bbl) before duration-based widening.
BASE_OIL_PRICE_BANDS: Dict[int, Dict[str, float]] = {
    0: {"low": 68.0, "high": 82.0},
    1: {"low": 80.0, "high": 95.0},
    2: {"low": 95.0, "high": 115.0},
    3: {"low": 110.0, "high": 140.0},
    4: {"low": 130.0, "high": 190.0},  # extreme volatility regime
}

# Duration multiplies lower/upper oil bounds.
OIL_DURATION_MULTIPLIERS: Dict[int, Dict[str, float]] = {
    7: {"low": 1.00, "high": 1.00},
    30: {"low": 1.02, "high": 1.05},
    90: {"low": 1.05, "high": 1.12},
}

# Base operational disruption assumptions by tier.
BASE_DISRUPTION_RANGES: Dict[int, Dict[str, Dict[str, float]]] = {
    0: {
        "throughput_reduction_pct": {"low": 0.0, "high": 3.0},
        "insurance_premium_increase_pct": {"low": 0.0, "high": 6.0},
        "lng_delay_probability_pct": {"low": 2.0, "high": 8.0},
        "refinery_margin_stress_score": {"low": 12.0, "high": 24.0},
    },
    1: {
        "throughput_reduction_pct": {"low": 5.0, "high": 12.0},
        "insurance_premium_increase_pct": {"low": 15.0, "high": 35.0},
        "lng_delay_probability_pct": {"low": 10.0, "high": 25.0},
        "refinery_margin_stress_score": {"low": 28.0, "high": 45.0},
    },
    2: {
        "throughput_reduction_pct": {"low": 12.0, "high": 25.0},
        "insurance_premium_increase_pct": {"low": 35.0, "high": 70.0},
        "lng_delay_probability_pct": {"low": 25.0, "high": 45.0},
        "refinery_margin_stress_score": {"low": 45.0, "high": 62.0},
    },
    3: {
        "throughput_reduction_pct": {"low": 25.0, "high": 40.0},
        "insurance_premium_increase_pct": {"low": 70.0, "high": 120.0},
        "lng_delay_probability_pct": {"low": 45.0, "high": 68.0},
        "refinery_margin_stress_score": {"low": 62.0, "high": 80.0},
    },
    4: {
        "throughput_reduction_pct": {"low": 40.0, "high": 70.0},
        "insurance_premium_increase_pct": {"low": 120.0, "high": 250.0},
        "lng_delay_probability_pct": {"low": 65.0, "high": 90.0},
        "refinery_margin_stress_score": {"low": 78.0, "high": 95.0},
    },
}

# Duration severity multipliers for disruption variables.
DISRUPTION_DURATION_MULTIPLIERS: Dict[int, float] = {
    7: 1.00,
    30: 1.15,
    90: 1.35,
}

# Trigger-based auto-upgrade logic used in escalation engine.
TRIGGER_RULES: List[Dict[str, object]] = [
    {
        "key": "terminal_strikes",
        "label": "Missile strike on export terminal",
        "condition": "terminal_strikes >= 1",
        "action": "Upgrade by +1 tier (cap Tier 4)",
        "threshold": 1,
        "type": "delta",
        "value": 1,
    },
    {
        "key": "blockade_alert_level",
        "label": "Naval blockade alert",
        "condition": "blockade_alert_level >= 1",
        "action": "Immediate upgrade to Tier 4",
        "threshold": 1,
        "type": "set",
        "value": 4,
    },
    {
        "key": "insurance_withdrawal_pct",
        "label": "Insurance market withdrawal",
        "condition": "insurance_withdrawal_pct >= 35",
        "action": "Upgrade by +1 tier (cap Tier 4)",
        "threshold": 35,
        "type": "delta",
        "value": 1,
    },
]

DEFAULT_COMPANY_PROFILE: Dict[str, Any] = {
    "name": "Emirates National Oil Company (ENOC)",
    "profile_mode": "proxy_public_sources",
    "daily_export_volume_bpd": 569_863,
    "fiscal_break_even_price_usd_per_bbl": 45.0,
    "debt_obligations_usd_bn": 1.19,
    "insurance_dependency_ratio": 0.78,
    "data_confidence": {
        "daily_export_volume_bpd": "medium",
        "fiscal_break_even_price_usd_per_bbl": "low",
        "debt_obligations_usd_bn": "low",
        "insurance_dependency_ratio": "low",
    },
    "data_notes": [
        "Export volume uses a public proxy from ENOC annual sales volume.",
        "Break-even price is an older public reference and should be replaced with current internal value.",
        "Debt obligations use publicly disclosed historical facilities, not current outstanding debt.",
        "Insurance dependency ratio is a modeling assumption for demo use.",
    ],
    "sources": [
        {
            "metric": "daily_export_volume_bpd",
            "source": "ENOC Annual Review 2024",
            "url": "https://www.enoc.com/portals/0/ModuleContent/HomePageCEOWidget/Pdf/V18_ENOC_Annual_Review%202024.pdf",
            "note": "208 million barrels annual sales volume (~569,863 bpd proxy).",
        },
        {
            "metric": "fiscal_break_even_price_usd_per_bbl",
            "source": "The National (2012 ENOC interview reference)",
            "url": "https://www.thenationalnews.com/business/enoc-to-build-saudi-petrol-stations-1.387246",
            "note": "Older public reference around $45/bbl.",
        },
        {
            "metric": "debt_obligations_usd_bn",
            "source": "ENOC press releases",
            "url": "https://www.enoc.com/en/media-centre/news-releases/press-release-detail/id/64/enoc-secures-us-500-million-credit-facility-from-international-and-regional-banks",
            "note": "2017 disclosed $500m facility (historical disclosure).",
        },
        {
            "metric": "debt_obligations_usd_bn",
            "source": "ENOC press releases",
            "url": "https://www.enoc.com/en/media-centre/news-releases/press-release-detail/id/156/enoc-group-secures-us-690-million-term-loan-from-a-consortium-of-chinese-banks",
            "note": "2019 disclosed $690m term loan (historical disclosure).",
        },
    ],
}

# Backward-compatible alias used by older modules/tests.
MOCK_COMPANY_PROFILE = DEFAULT_COMPANY_PROFILE
