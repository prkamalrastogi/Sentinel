"""Generate a deterministic scenario matrix output for handoff/reporting."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from app.config import DURATION_OPTIONS_DAYS, ESCALATION_TIERS
from app.service import run_simulation

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
OUTPUT_JSON = OUTPUT_DIR / "scenario_matrix.json"
OUTPUT_CSV = OUTPUT_DIR / "scenario_matrix.csv"


def build_matrix() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for tier in sorted(ESCALATION_TIERS.keys()):
        for duration_days in DURATION_OPTIONS_DAYS:
            result = run_simulation(
                selected_tier=tier,
                duration_days=duration_days,
                trigger_inputs={
                    "terminal_strikes": 0,
                    "blockade_alert_level": 0,
                    "insurance_withdrawal_pct": 0,
                },
            )
            rows.append(
                {
                    "tier": result["effective_tier"],
                    "tier_name": result["tier_definition"]["name"],
                    "duration_days": duration_days,
                    "oil_band_usd_per_bbl": result["oil_regime"]["band_label"],
                    "throughput_reduction_mid_pct": result["operational_disruption"][
                        "throughput_reduction_pct"
                    ]["mid"],
                    "insurance_premium_mid_pct": result["operational_disruption"][
                        "insurance_premium_increase_pct"
                    ]["mid"],
                    "lng_delay_mid_pct": result["operational_disruption"]["lng_delay_probability_pct"][
                        "mid"
                    ],
                    "refinery_stress_mid": result["operational_disruption"]["refinery_margin_stress"][
                        "score"
                    ]["mid"],
                    "revenue_impact_band_usd_bn": result["company_exposure"]["revenue_impact_band_usd_bn"][
                        "label"
                    ],
                    "liquidity_stress": result["company_exposure"]["liquidity_stress_indicator"],
                    "export_disruption_severity": result["company_exposure"][
                        "export_disruption_severity"
                    ],
                }
            )
    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "principle": (
            "This simulator does not predict conflict outcomes; "
            "it translates escalation conditions into structured exposure bands."
        ),
    }
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    fieldnames = list(rows[0].keys()) if rows else []
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_matrix()
    write_outputs(rows)
    print(f"Wrote {len(rows)} scenarios to {OUTPUT_JSON}")
    print(f"Wrote CSV summary to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
