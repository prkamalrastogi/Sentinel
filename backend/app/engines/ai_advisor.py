"""Optional LLM-backed advisor layer with deterministic fallback."""

from __future__ import annotations

import json
import re
from typing import Any

import requests

from app.settings import get_settings


def _extract_content(payload: dict[str, Any]) -> str:
    # Chat Completions format
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        content = message.get("content")
        if isinstance(content, str):
            return content

    # Responses-style convenience field
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    # Responses-style structured output
    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            for content_item in item.get("content", []):
                text = content_item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)
    return ""


def _parse_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _context_for_model(
    question: str,
    simulation: dict[str, Any],
    advisory: dict[str, Any],
    live_intel: dict[str, Any],
    learning_lessons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ops = simulation.get("operational_disruption", {})
    company = simulation.get("company_exposure", {})
    signal = live_intel.get("signal_summary", {})
    headlines = []
    for item in list(live_intel.get("headlines", []))[:5]:
        headlines.append(
            {
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "signal_level": item.get("signal_level", "none"),
            }
        )

    return {
        "question": question,
        "tier": simulation.get("effective_tier"),
        "duration_days": simulation.get("duration_days"),
        "alert_level": advisory.get("alert_level"),
        "advisory_score": advisory.get("advisory_score"),
        "oil_band": simulation.get("oil_regime", {}).get("band_label"),
        "ops_midpoints": {
            "throughput_reduction_pct": (ops.get("throughput_reduction_pct") or {}).get("mid"),
            "insurance_premium_increase_pct": (ops.get("insurance_premium_increase_pct") or {}).get("mid"),
            "lng_delay_probability_pct": (ops.get("lng_delay_probability_pct") or {}).get("mid"),
        },
        "company": {
            "liquidity_stress_indicator": company.get("liquidity_stress_indicator"),
            "export_disruption_severity": company.get("export_disruption_severity"),
        },
        "live_signals": {
            "critical_count": signal.get("critical_count", 0),
            "elevated_count": signal.get("elevated_count", 0),
            "watch_count": signal.get("watch_count", 0),
            "category_counts": signal.get("category_counts", {}),
        },
        "headlines": headlines,
        "baseline_steps": advisory.get("recommended_steps", [])[:6],
        "learning_lessons": (learning_lessons or [])[:3],
    }


def maybe_apply_ai_advisor(
    *,
    question: str,
    simulation: dict[str, Any],
    advisory: dict[str, Any],
    live_intel: dict[str, Any],
    fallback: dict[str, Any],
    use_ai_advisor: bool,
    learning_lessons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not use_ai_advisor or not settings.enable_ai_advisor:
        return {**fallback, "advisor_mode": "rules"}
    if not settings.openai_api_key.strip():
        return {**fallback, "advisor_mode": "rules"}

    system_prompt = (
        "You are Sentinel Advisor for GCC energy operators. "
        "Use plain, direct language for executives. "
        "Do not predict war outcomes. "
        "Return JSON only with keys: answer (string), next_actions (array of 3 short strings)."
    )

    context = _context_for_model(
        question,
        simulation,
        advisory,
        live_intel,
        learning_lessons=learning_lessons,
    )
    user_prompt = (
        "Generate concise guidance for this scenario context.\n"
        "Keep answer under 130 words.\n"
        "Focus on immediate operational and financial actions.\n"
        f"Context JSON:\n{json.dumps(context, ensure_ascii=True)}"
    )

    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.openai_model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key.strip()}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=settings.openai_timeout_seconds,
        )
        response.raise_for_status()
        content = _extract_content(response.json())
        parsed = _parse_json(content)
        if not parsed:
            return {**fallback, "advisor_mode": "rules"}

        answer = parsed.get("answer")
        next_actions = parsed.get("next_actions")
        if not isinstance(answer, str) or not answer.strip():
            return {**fallback, "advisor_mode": "rules"}
        if not isinstance(next_actions, list):
            return {**fallback, "advisor_mode": "rules"}

        clean_actions = [
            str(item).strip()
            for item in next_actions
            if isinstance(item, str) and str(item).strip()
        ][:3]
        if not clean_actions:
            clean_actions = list(fallback.get("next_actions", []))[:3]

        return {
            **fallback,
            "answer": answer.strip(),
            "next_actions": clean_actions,
            "advisor_mode": "ai",
        }
    except Exception:
        return {**fallback, "advisor_mode": "rules"}
