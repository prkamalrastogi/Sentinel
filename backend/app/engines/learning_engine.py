"""Simple persistent learning log for post-incident feedback and lessons."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Any


_LOCK = threading.Lock()
_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "learning_log.jsonl"


def _ensure_store() -> None:
    _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _DATA_PATH.exists():
        _DATA_PATH.touch()


def list_learning_entries(limit: int = 100) -> list[dict[str, Any]]:
    _ensure_store()
    with _LOCK:
        rows: list[dict[str, Any]] = []
        with _DATA_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        rows.append(obj)
                except Exception:
                    continue
    rows.sort(key=lambda item: str(item.get("created_utc", "")), reverse=True)
    return rows[: max(1, min(limit, 500))]


def add_learning_entry(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure_store()
    entry = {
        "id": f"learn-{uuid4().hex[:12]}",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "title": str(payload.get("title", "")).strip(),
        "observation": str(payload.get("observation", "")).strip(),
        "action_taken": str(payload.get("action_taken", "")).strip(),
        "outcome": str(payload.get("outcome", "")).strip(),
        "lesson": str(payload.get("lesson", "")).strip(),
        "tags": [str(tag).strip().lower() for tag in payload.get("tags", []) if str(tag).strip()],
    }
    with _LOCK:
        with _DATA_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=True) + "\n")
    return entry


def relevant_lessons(
    *,
    question: str,
    simulation: dict[str, Any],
    max_items: int = 3,
) -> list[dict[str, Any]]:
    entries = list_learning_entries(limit=120)
    if not entries:
        return []

    question_tokens = set(question.lower().split())
    tier = int(simulation.get("effective_tier", 0))
    throughput_mid = float(
        ((simulation.get("operational_disruption") or {}).get("throughput_reduction_pct") or {}).get("mid", 0)
    )
    insurance_mid = float(
        ((simulation.get("operational_disruption") or {}).get("insurance_premium_increase_pct") or {}).get(
            "mid", 0
        )
    )
    lng_mid = float(
        ((simulation.get("operational_disruption") or {}).get("lng_delay_probability_pct") or {}).get("mid", 0)
    )

    scored: list[tuple[float, dict[str, Any]]] = []
    for entry in entries:
        text = " ".join(
            [
                str(entry.get("title", "")),
                str(entry.get("observation", "")),
                str(entry.get("action_taken", "")),
                str(entry.get("lesson", "")),
                " ".join(entry.get("tags", [])),
            ]
        ).lower()
        score = 0.0
        score += sum(1 for token in question_tokens if token and token in text) * 1.0
        if tier >= 3 and any(tok in text for tok in ["crisis", "board", "contingency"]):
            score += 1.5
        if throughput_mid >= 20 and any(tok in text for tok in ["shipping", "throughput", "terminal"]):
            score += 1.5
        if insurance_mid >= 50 and any(tok in text for tok in ["insurance", "premium", "underwriter"]):
            score += 1.5
        if lng_mid >= 30 and any(tok in text for tok in ["lng", "cargo", "delay"]):
            score += 1.0
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in scored[: max(1, min(max_items, 8))]]
