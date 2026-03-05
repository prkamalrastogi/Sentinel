"""Oil regime simulation based on escalation tier and scenario duration."""

from typing import Dict

from app.config import BASE_OIL_PRICE_BANDS, OIL_DURATION_MULTIPLIERS


def simulate_oil_price_band(tier: int, duration_days: int) -> Dict[str, object]:
    if tier not in BASE_OIL_PRICE_BANDS:
        raise ValueError(f"Unsupported escalation tier: {tier}")
    if duration_days not in OIL_DURATION_MULTIPLIERS:
        raise ValueError(f"Unsupported duration: {duration_days}")

    base_band = BASE_OIL_PRICE_BANDS[tier]
    duration_factor = OIL_DURATION_MULTIPLIERS[duration_days]

    low = round(base_band["low"] * duration_factor["low"], 2)
    high = round(base_band["high"] * duration_factor["high"], 2)

    regime = "Extreme volatility band" if tier == 4 else "Escalation-linked price band"

    return {
        "regime": regime,
        "currency": "USD/bbl",
        "low": low,
        "high": high,
        "band_label": f"${low:.2f} - ${high:.2f}",
    }
