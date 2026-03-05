"""Live internet news ingestion and signal extraction for Sentinel."""

from __future__ import annotations

import html
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

from app.settings import get_settings

USER_AGENT = "Sentinel-Live-Intel/0.2"
REQUEST_TIMEOUT_SECONDS = 10
CACHE_TTL_SECONDS = 300
MAX_WORKERS = 12
MAX_TITLE_LENGTH = 220
MAX_SUMMARY_LENGTH = 420

FOCUS_KEYWORDS = [
    "hormuz",
    "strait",
    "gcc",
    "gulf",
    "saudi",
    "uae",
    "qatar",
    "kuwait",
    "oman",
    "bahrain",
    "iran",
    "iraq",
    "oil",
    "lng",
    "tanker",
    "shipping",
    "refinery",
    "export terminal",
    "pipeline",
    "energy",
]

# RSS feed coverage for major global outlets + domain-specific aggregations.
RSS_SOURCES = [
    {
        "id": "rss_google_hormuz",
        "name": "Google News - Strait of Hormuz",
        "url": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
        "query": "Strait of Hormuz shipping disruption",
        "priority": 2,
    },
    {
        "id": "rss_google_gcc_exports",
        "name": "Google News - GCC energy exports",
        "url": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
        "query": "GCC oil export terminal attack",
        "priority": 2,
    },
    {
        "id": "rss_google_lng",
        "name": "Google News - LNG delays",
        "url": "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en",
        "query": "Middle East LNG shipping delay insurance premium",
        "priority": 1,
    },
    {
        "id": "rss_reuters_world",
        "name": "Reuters World",
        "url": "https://feeds.reuters.com/reuters/worldNews",
        "query": "",
        "priority": 2,
    },
    {
        "id": "rss_ap_topnews",
        "name": "AP Top News",
        "url": "https://feeds.apnews.com/apnews/topnews",
        "query": "",
        "priority": 2,
    },
    {
        "id": "rss_bbc_world",
        "name": "BBC World",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "query": "",
        "priority": 2,
    },
    {
        "id": "rss_cnn_world",
        "name": "CNN World",
        "url": "http://rss.cnn.com/rss/edition_world.rss",
        "query": "",
        "priority": 1,
    },
    {
        "id": "rss_aljazeera",
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "query": "",
        "priority": 1,
    },
    {
        "id": "rss_reddit_hormuz",
        "name": "Reddit Search - Hormuz",
        "url": "https://www.reddit.com/search.rss?q={query}&sort=new",
        "query": "Strait of Hormuz tanker",
        "priority": 0,
    },
]

API_PROVIDER_IDS = ["newsapi", "gnews", "guardian", "nyt", "mediastack"]

SIGNAL_RULES = [
    {
        "category": "blockade_alert",
        "level": "critical",
        "score": 6,
        "patterns": [
            r"\bnaval blockade\b",
            r"\bblockade alert\b",
            r"\bstrait (?:closure|closed)\b",
            r"\bshipping lane closed\b",
        ],
    },
    {
        "category": "terminal_strike",
        "level": "critical",
        "score": 5,
        "patterns": [
            r"\bmissile strike\b",
            r"\bdrone strike\b",
            r"\bexport terminal (?:hit|attack|strike)\b",
            r"\bport facility (?:hit|attack|damaged)\b",
        ],
    },
    {
        "category": "insurance_withdrawal",
        "level": "critical",
        "score": 5,
        "patterns": [
            r"\binsurance (?:withdrawal|withdrawn)\b",
            r"\bwar-risk cover (?:suspend(?:ed)?|withdrawn)\b",
            r"\bunders?writer(?:s)? (?:withdraw(?:n)?|suspend(?:ed)?)\b",
            r"\binsurers? (?:withdraw(?:n)?|suspend(?:ed)?)\b",
        ],
    },
    {
        "category": "shipping_disruption",
        "level": "elevated",
        "score": 3,
        "patterns": [
            r"\btanker (?:seized|detained|rerouted)\b",
            r"\bshipping disruption\b",
            r"\bmaritime security incident\b",
            r"\bport delays?\b",
        ],
    },
    {
        "category": "energy_market_stress",
        "level": "watch",
        "score": 2,
        "patterns": [
            r"\boil price spike\b",
            r"\benergy market volatility\b",
            r"\brefinery margin pressure\b",
            r"\blng (?:delay|cargo delay)\b",
        ],
    },
]

LEVEL_ORDER = {"none": 0, "watch": 1, "elevated": 2, "critical": 3}

_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"key": None, "at": 0.0, "value": None}


def get_supported_live_providers() -> dict[str, Any]:
    settings = get_settings()
    return {
        "rss": [
            {
                "id": source["id"],
                "name": source["name"],
            }
            for source in RSS_SOURCES
        ],
        "api": [
            {"id": provider_id}
            for provider_id in API_PROVIDER_IDS
        ],
        "api_provider_keys_present": settings.api_news_keys_present,
        "api_source_ingestion_enabled": settings.enable_api_news_sources,
    }


def _http_get(url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
    return requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def _build_feed_url(template: str, query: str) -> str:
    if "{query}" not in template:
        return template
    return template.format(query=quote_plus(query))


def _clean_text(text: str, max_chars: int | None = None) -> str:
    no_html = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", html.unescape(no_html)).strip()
    if max_chars and len(cleaned) > max_chars:
        return cleaned[: max_chars - 3].rstrip() + "..."
    return cleaned


def _parse_rfc_published(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_iso_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def extract_signal_profile(text: str) -> dict[str, Any]:
    """Keyword-based signal extraction. Transparent and editable through SIGNAL_RULES."""
    text_lower = text.lower()
    total_score = 0
    matched_categories: set[str] = set()
    matched_terms: list[str] = []
    level = "none"

    for rule in SIGNAL_RULES:
        for pattern in rule["patterns"]:
            if re.search(pattern, text_lower):
                matched_categories.add(str(rule["category"]))
                matched_terms.append(pattern)
                total_score += int(rule["score"])
                if LEVEL_ORDER[str(rule["level"])] > LEVEL_ORDER[level]:
                    level = str(rule["level"])
                break

    return {
        "level": level,
        "score": total_score,
        "categories": sorted(matched_categories),
        "matched_terms": matched_terms,
    }


def _source_weight(source_name: str, source_priority: int) -> int:
    source_name = source_name.lower()
    trusted = [
        "reuters",
        "associated press",
        "ap",
        "financial times",
        "bloomberg",
        "al jazeera",
        "bbc",
        "cnn",
        "new york times",
        "guardian",
    ]
    if any(token in source_name for token in trusted):
        return source_priority + 2
    return source_priority + 1


def _recency_weight(published_at: datetime | None, now: datetime) -> int:
    if published_at is None:
        return 0
    age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    if age_hours <= 6:
        return 3
    if age_hours <= 24:
        return 2
    if age_hours <= 72:
        return 1
    return 0


def _headline_record(
    *,
    title: str,
    summary: str,
    link: str,
    source_name: str,
    provider_id: str,
    provider_name: str,
    provider_type: str,
    source_priority: int,
    published_at: datetime | None,
    now: datetime,
) -> dict[str, Any]:
    title = _clean_text(title, max_chars=MAX_TITLE_LENGTH)
    summary = _clean_text(summary, max_chars=MAX_SUMMARY_LENGTH)
    combined = f"{title} {summary}".strip()
    signal = extract_signal_profile(combined)
    relevance = signal["score"] + _source_weight(source_name or provider_name, source_priority) + _recency_weight(
        published_at, now
    )

    return {
        "title": title,
        "summary": summary,
        "link": link,
        "source": source_name or provider_name,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "provider_type": provider_type,
        "published_utc": published_at.isoformat() if published_at else None,
        "domain": urlparse(link).netloc or source_name or provider_name,
        "signal_level": signal["level"],
        "signal_categories": signal["categories"],
        "signal_score": signal["score"],
        "relevance_score": relevance,
    }


def _is_focus_relevant(item: dict[str, Any]) -> bool:
    if int(item.get("signal_score", 0)) > 0:
        return True

    provider_id = str(item.get("provider_id", ""))
    if provider_id.startswith("rss_google_"):
        return True

    text = " ".join(
        [
            str(item.get("title", "")),
            str(item.get("summary", "")),
            str(item.get("source", "")),
            str(item.get("domain", "")),
        ]
    ).lower()
    return any(keyword in text for keyword in FOCUS_KEYWORDS)


def _thread_summary(headlines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in headlines:
        categories = item.get("signal_categories") or ["market_watch"]
        for category in categories:
            bucket = buckets.setdefault(category, {"category": category, "count": 0, "top_headlines": []})
            bucket["count"] += 1
            if len(bucket["top_headlines"]) < 3:
                bucket["top_headlines"].append(item["title"])

    return sorted(buckets.values(), key=lambda x: x["count"], reverse=True)


def _signal_summary(headlines: list[dict[str, Any]]) -> dict[str, Any]:
    critical = sum(1 for item in headlines if item["signal_level"] == "critical")
    elevated = sum(1 for item in headlines if item["signal_level"] == "elevated")
    watch = sum(1 for item in headlines if item["signal_level"] == "watch")
    neutral = sum(1 for item in headlines if item["signal_level"] == "none")

    categories: dict[str, int] = {}
    for item in headlines:
        for category in item["signal_categories"]:
            categories[category] = categories.get(category, 0) + 1

    return {
        "critical_count": critical,
        "elevated_count": elevated,
        "watch_count": watch,
        "neutral_count": neutral,
        "category_counts": categories,
    }


def _provider_summary(source_status: list[dict[str, Any]], settings) -> dict[str, Any]:
    total = len(source_status)
    healthy = sum(1 for item in source_status if item.get("status") == "ok")
    api_total = sum(1 for item in source_status if item.get("provider_type") == "api")
    api_healthy = sum(
        1 for item in source_status if item.get("provider_type") == "api" and item.get("status") == "ok"
    )
    rss_total = sum(1 for item in source_status if item.get("provider_type") == "rss")
    rss_healthy = sum(
        1 for item in source_status if item.get("provider_type") == "rss" and item.get("status") == "ok"
    )

    return {
        "total_sources": total,
        "healthy_sources": healthy,
        "api_sources": {"total": api_total, "healthy": api_healthy},
        "rss_sources": {"total": rss_total, "healthy": rss_healthy},
        "api_provider_keys_present": settings.api_news_keys_present,
        "api_source_ingestion_enabled": settings.enable_api_news_sources,
    }


def _normalize_provider_selection(selected_providers: list[str] | None) -> set[str]:
    if not selected_providers:
        return {source["id"] for source in RSS_SOURCES} | set(API_PROVIDER_IDS)
    normalized = {item.strip().lower() for item in selected_providers if item.strip()}
    if "all" in normalized:
        return {source["id"] for source in RSS_SOURCES} | set(API_PROVIDER_IDS)
    return normalized


def _fetch_rss_source(
    source: dict[str, Any],
    *,
    lookback_cutoff: datetime,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source_url = _build_feed_url(str(source["url"]), str(source["query"]))
    source_id = str(source["id"])
    source_name = str(source["name"])
    source_priority = int(source["priority"])

    records: list[dict[str, Any]] = []
    try:
        response = _http_get(source_url)
        response.raise_for_status()
        parsed = feedparser.parse(response.text)

        for entry in parsed.entries:
            title = _clean_text(str(entry.get("title", "")))
            if not title:
                continue

            summary = _clean_text(str(entry.get("summary", "")))
            link = str(entry.get("link", "")).strip()
            published_at = _parse_rfc_published(entry.get("published") or entry.get("updated"))
            if published_at and published_at < lookback_cutoff:
                continue

            entry_source = ""
            source_obj = entry.get("source")
            if isinstance(source_obj, dict):
                entry_source = str(source_obj.get("title", ""))

            records.append(
                _headline_record(
                    title=title,
                    summary=summary,
                    link=link,
                    source_name=entry_source,
                    provider_id=source_id,
                    provider_name=source_name,
                    provider_type="rss",
                    source_priority=source_priority,
                    published_at=published_at,
                    now=now,
                )
            )

        status = {
            "source": source_name,
            "provider_id": source_id,
            "provider_type": "rss",
            "status": "ok",
            "items_collected": len(records),
        }
        return status, records
    except Exception as exc:
        status = {
            "source": source_name,
            "provider_id": source_id,
            "provider_type": "rss",
            "status": "error",
            "items_collected": 0,
            "detail": exc.__class__.__name__,
        }
        return status, []


def _fetch_newsapi(
    *,
    api_key: str,
    query: str,
    lookback_cutoff: datetime,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provider_id = "newsapi"
    provider_name = "NewsAPI"
    try:
        response = _http_get(
            "https://newsapi.org/v2/everything",
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 100,
                "from": lookback_cutoff.date().isoformat(),
                "apiKey": api_key,
            },
        )
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", []) if isinstance(data, dict) else []

        records: list[dict[str, Any]] = []
        for article in articles:
            title = _clean_text(str(article.get("title", "")))
            if not title:
                continue
            published_at = _parse_iso_datetime(article.get("publishedAt"))
            if published_at and published_at < lookback_cutoff:
                continue
            source = article.get("source") or {}
            source_name = str(source.get("name", ""))
            records.append(
                _headline_record(
                    title=title,
                    summary=_clean_text(str(article.get("description", ""))),
                    link=str(article.get("url", "")).strip(),
                    source_name=source_name,
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_type="api",
                    source_priority=3,
                    published_at=published_at,
                    now=now,
                )
            )

        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "ok",
            "items_collected": len(records),
        }
        return status, records
    except Exception as exc:
        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "error",
            "items_collected": 0,
            "detail": exc.__class__.__name__,
        }
        return status, []


def _fetch_gnews(
    *,
    api_key: str,
    query: str,
    lookback_cutoff: datetime,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provider_id = "gnews"
    provider_name = "GNews"
    try:
        response = _http_get(
            "https://gnews.io/api/v4/search",
            params={
                "q": query,
                "lang": "en",
                "sortby": "publishedAt",
                "max": 100,
                "apikey": api_key,
            },
        )
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", []) if isinstance(data, dict) else []

        records: list[dict[str, Any]] = []
        for article in articles:
            title = _clean_text(str(article.get("title", "")))
            if not title:
                continue
            published_at = _parse_iso_datetime(article.get("publishedAt"))
            if published_at and published_at < lookback_cutoff:
                continue
            source = article.get("source") or {}
            records.append(
                _headline_record(
                    title=title,
                    summary=_clean_text(str(article.get("description", ""))),
                    link=str(article.get("url", "")).strip(),
                    source_name=str(source.get("name", "")),
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_type="api",
                    source_priority=3,
                    published_at=published_at,
                    now=now,
                )
            )

        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "ok",
            "items_collected": len(records),
        }
        return status, records
    except Exception as exc:
        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "error",
            "items_collected": 0,
            "detail": exc.__class__.__name__,
        }
        return status, []


def _fetch_guardian(
    *,
    api_key: str,
    query: str,
    lookback_cutoff: datetime,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provider_id = "guardian"
    provider_name = "Guardian Open Platform"
    try:
        response = _http_get(
            "https://content.guardianapis.com/search",
            params={
                "api-key": api_key,
                "q": query,
                "order-by": "newest",
                "from-date": lookback_cutoff.date().isoformat(),
                "show-fields": "trailText",
                "page-size": 100,
            },
        )
        response.raise_for_status()
        data = response.json()
        items = ((data.get("response") or {}).get("results") or []) if isinstance(data, dict) else []

        records: list[dict[str, Any]] = []
        for item in items:
            title = _clean_text(str(item.get("webTitle", "")))
            if not title:
                continue
            published_at = _parse_iso_datetime(item.get("webPublicationDate"))
            if published_at and published_at < lookback_cutoff:
                continue
            fields = item.get("fields") or {}
            records.append(
                _headline_record(
                    title=title,
                    summary=_clean_text(str(fields.get("trailText", ""))),
                    link=str(item.get("webUrl", "")).strip(),
                    source_name="The Guardian",
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_type="api",
                    source_priority=3,
                    published_at=published_at,
                    now=now,
                )
            )

        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "ok",
            "items_collected": len(records),
        }
        return status, records
    except Exception as exc:
        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "error",
            "items_collected": 0,
            "detail": exc.__class__.__name__,
        }
        return status, []


def _fetch_nyt(
    *,
    api_key: str,
    query: str,
    lookback_cutoff: datetime,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provider_id = "nyt"
    provider_name = "New York Times"
    try:
        response = _http_get(
            "https://api.nytimes.com/svc/search/v2/articlesearch.json",
            params={
                "q": query,
                "sort": "newest",
                "begin_date": lookback_cutoff.strftime("%Y%m%d"),
                "api-key": api_key,
            },
        )
        response.raise_for_status()
        data = response.json()
        docs = ((data.get("response") or {}).get("docs") or []) if isinstance(data, dict) else []

        records: list[dict[str, Any]] = []
        for doc in docs:
            headline = doc.get("headline") or {}
            title = _clean_text(str(headline.get("main", "")))
            if not title:
                continue
            published_at = _parse_iso_datetime(doc.get("pub_date"))
            if published_at and published_at < lookback_cutoff:
                continue
            records.append(
                _headline_record(
                    title=title,
                    summary=_clean_text(str(doc.get("abstract", ""))),
                    link=str(doc.get("web_url", "")).strip(),
                    source_name=str(doc.get("source", "New York Times")),
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_type="api",
                    source_priority=3,
                    published_at=published_at,
                    now=now,
                )
            )

        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "ok",
            "items_collected": len(records),
        }
        return status, records
    except Exception as exc:
        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "error",
            "items_collected": 0,
            "detail": exc.__class__.__name__,
        }
        return status, []


def _fetch_mediastack(
    *,
    api_key: str,
    query: str,
    lookback_cutoff: datetime,
    now: datetime,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    provider_id = "mediastack"
    provider_name = "Mediastack"
    try:
        # Mediastack free tiers often require HTTP endpoint.
        response = _http_get(
            "http://api.mediastack.com/v1/news",
            params={
                "access_key": api_key,
                "keywords": query,
                "languages": "en",
                "sort": "published_desc",
                "limit": 100,
            },
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("data", []) if isinstance(data, dict) else []

        records: list[dict[str, Any]] = []
        for item in items:
            title = _clean_text(str(item.get("title", "")))
            if not title:
                continue
            published_at = _parse_iso_datetime(item.get("published_at"))
            if published_at and published_at < lookback_cutoff:
                continue
            records.append(
                _headline_record(
                    title=title,
                    summary=_clean_text(str(item.get("description", ""))),
                    link=str(item.get("url", "")).strip(),
                    source_name=str(item.get("source", "")),
                    provider_id=provider_id,
                    provider_name=provider_name,
                    provider_type="api",
                    source_priority=2,
                    published_at=published_at,
                    now=now,
                )
            )

        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "ok",
            "items_collected": len(records),
        }
        return status, records
    except Exception as exc:
        status = {
            "source": provider_name,
            "provider_id": provider_id,
            "provider_type": "api",
            "status": "error",
            "items_collected": 0,
            "detail": exc.__class__.__name__,
        }
        return status, []


def _api_provider_tasks(
    *,
    selected_provider_ids: set[str],
    include_api_sources: bool,
    lookback_cutoff: datetime,
    now: datetime,
) -> list[tuple[str, Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]]]]:
    settings = get_settings()
    if not include_api_sources or not settings.enable_api_news_sources:
        return []

    query = settings.live_query
    tasks: list[tuple[str, Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]]]] = []

    def add_task(provider_id: str, key: str, fn: Callable[..., tuple[dict[str, Any], list[dict[str, Any]]]]) -> None:
        if provider_id not in selected_provider_ids:
            return
        if not key.strip():
            tasks.append(
                (
                    provider_id,
                    lambda: (
                        {
                            "source": provider_id,
                            "provider_id": provider_id,
                            "provider_type": "api",
                            "status": "skipped",
                            "items_collected": 0,
                            "detail": "missing_api_key",
                        },
                        [],
                    ),
                )
            )
            return
        tasks.append(
            (
                provider_id,
                lambda: fn(
                    api_key=key,
                    query=query,
                    lookback_cutoff=lookback_cutoff,
                    now=now,
                ),
            )
        )

    add_task("newsapi", settings.newsapi_key, _fetch_newsapi)
    add_task("gnews", settings.gnews_key, _fetch_gnews)
    add_task("guardian", settings.guardian_key, _fetch_guardian)
    add_task("nyt", settings.nyt_key, _fetch_nyt)
    add_task("mediastack", settings.mediastack_key, _fetch_mediastack)
    return tasks


def fetch_live_intelligence(
    lookback_hours: int = 72,
    max_items: int = 40,
    selected_providers: list[str] | None = None,
    include_api_sources: bool = True,
) -> dict[str, Any]:
    """
    Pull live public feeds + optional major API providers, then extract signal-oriented threads.
    """
    settings = get_settings()
    provider_ids = _normalize_provider_selection(selected_providers)

    cache_key = (
        f"{lookback_hours}:{max_items}:{include_api_sources}:{settings.enable_api_news_sources}:"
        f"{sorted(provider_ids)}:{settings.live_query}:{settings.api_news_keys_present}"
    )
    now_monotonic = time.monotonic()

    with _CACHE_LOCK:
        if (
            _CACHE["key"] == cache_key
            and _CACHE["value"] is not None
            and now_monotonic - float(_CACHE["at"]) <= CACHE_TTL_SECONDS
        ):
            return _CACHE["value"]

    now = datetime.now(timezone.utc)
    lookback_cutoff = now - timedelta(hours=lookback_hours)

    tasks: list[tuple[str, Callable[[], tuple[dict[str, Any], list[dict[str, Any]]]]]] = []

    for source in RSS_SOURCES:
        if str(source["id"]) not in provider_ids:
            continue
        source_copy = dict(source)
        tasks.append(
            (
                str(source_copy["id"]),
                lambda src=source_copy: _fetch_rss_source(src, lookback_cutoff=lookback_cutoff, now=now),
            )
        )

    tasks.extend(
        _api_provider_tasks(
            selected_provider_ids=provider_ids,
            include_api_sources=include_api_sources,
            lookback_cutoff=lookback_cutoff,
            now=now,
        )
    )

    source_status: list[dict[str, Any]] = []
    fetched_items: list[dict[str, Any]] = []

    if tasks:
        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(tasks))) as pool:
            futures = {pool.submit(task_fn): task_id for task_id, task_fn in tasks}
            for future in as_completed(futures):
                try:
                    status, items = future.result()
                except Exception as exc:
                    task_id = futures[future]
                    status = {
                        "source": task_id,
                        "provider_id": task_id,
                        "provider_type": "unknown",
                        "status": "error",
                        "items_collected": 0,
                        "detail": exc.__class__.__name__,
                    }
                    items = []

                source_status.append(status)
                fetched_items.extend(items)

    deduped_items: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in fetched_items:
        key = f"{item['title'].strip().lower()}|{item['link'].strip()}"
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_items.append(item)

    deduped_items.sort(
        key=lambda item: (
            item["relevance_score"],
            item["published_utc"] or "",
        ),
        reverse=True,
    )

    before_focus_count = len(deduped_items)
    focused_items = [item for item in deduped_items if _is_focus_relevant(item)]
    if focused_items:
        deduped_items = focused_items

    headlines = deduped_items[:max_items]

    fetch_warnings = [
        f"{item.get('source')}: {item.get('detail')}"
        for item in source_status
        if item.get("status") in {"error", "skipped"}
    ]

    payload = {
        "generated_at_utc": now.isoformat(),
        "lookback_hours": lookback_hours,
        "max_items": max_items,
        "items_after_focus_filter": len(deduped_items),
        "focus_filter_applied": bool(focused_items) and len(deduped_items) < before_focus_count,
        "sources_checked": len(source_status),
        "sources_healthy": sum(1 for item in source_status if item.get("status") == "ok"),
        "source_status": sorted(source_status, key=lambda item: str(item.get("source", ""))),
        "provider_summary": _provider_summary(source_status, settings),
        "fetch_warnings": fetch_warnings,
        "signal_summary": _signal_summary(headlines),
        "thread_summary": _thread_summary(headlines),
        "headlines": headlines,
    }

    with _CACHE_LOCK:
        _CACHE["key"] = cache_key
        _CACHE["at"] = time.monotonic()
        _CACHE["value"] = payload

    return payload
