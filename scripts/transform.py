"""
Transform pipeline for Community Pulse.

Normalizes raw signals from all sources into the standard data.json schema.
Computes sentiment scores and generates summary rollups.
"""

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from textblob import TextBlob


def normalize_signal(raw: dict, source: str) -> dict | None:
    """Convert a raw signal dict into the standard schema. Returns None if invalid."""
    content = raw.get("content_preview", "")
    if not content:
        return None

    # Generate deterministic ID if not provided
    signal_id = raw.get("id") or hashlib.sha256(
        f"{source}:{raw.get('date', '')}:{content[:100]}".encode()
    ).hexdigest()[:12]
    signal_id = f"sig_{signal_id}"

    # Compute sentiment if not already present
    sentiment = raw.get("sentiment_score")
    confidence = raw.get("confidence")
    if sentiment is None:
        blob = TextBlob(content)
        sentiment = round(blob.sentiment.polarity, 4)
        confidence = round(blob.sentiment.subjectivity, 4)

    # Parse / normalize date
    date_str = raw.get("date", "")
    if isinstance(date_str, (int, float)):
        date_str = datetime.fromtimestamp(date_str, tz=timezone.utc).isoformat()

    return {
        "id": signal_id,
        "source": source,
        "source_url": raw.get("source_url", ""),
        "date": date_str,
        "topic": raw.get("topic", "general"),
        "sentiment_score": max(-1.0, min(1.0, sentiment)),
        "confidence": max(0.0, min(1.0, confidence if confidence is not None else 0.5)),
        "author": raw.get("author", "anonymous"),
        "content_preview": content[:500],
        "engagement": {
            "likes": raw.get("engagement", {}).get("likes", 0),
            "replies": raw.get("engagement", {}).get("replies", 0),
            "shares": raw.get("engagement", {}).get("shares", 0),
        },
        "tags": raw.get("tags", []),
    }


def compute_summary(signals: list[dict]) -> dict:
    """Compute summary rollups from the normalized signal list."""
    if not signals:
        return {
            "overall_sentiment": 0.0,
            "top_topics": [],
            "sentiment_trend": [],
        }

    # Topic aggregation
    topics: dict[str, dict] = {}
    for s in signals:
        topic = s["topic"]
        if topic not in topics:
            topics[topic] = {"count": 0, "total_sentiment": 0.0}
        topics[topic]["count"] += 1
        topics[topic]["total_sentiment"] += s["sentiment_score"]

    top_topics = sorted(
        [
            {
                "topic": t,
                "count": d["count"],
                "avg_sentiment": round(d["total_sentiment"] / d["count"], 4),
            }
            for t, d in topics.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    # Sentiment trend by day
    day_buckets: dict[str, list[float]] = {}
    for s in signals:
        day = s["date"][:10]  # YYYY-MM-DD
        if day not in day_buckets:
            day_buckets[day] = []
        day_buckets[day].append(s["sentiment_score"])

    sentiment_trend = sorted(
        [
            {
                "date": day,
                "avg_sentiment": round(sum(scores) / len(scores), 4),
                "signal_count": len(scores),
            }
            for day, scores in day_buckets.items()
        ],
        key=lambda x: x["date"],
    )

    overall = round(
        sum(s["sentiment_score"] for s in signals) / len(signals), 4
    )

    return {
        "overall_sentiment": overall,
        "top_topics": top_topics,
        "sentiment_trend": sentiment_trend,
    }


def transform(
    raw_signals: dict[str, list[dict]],
    existing_data: dict | None = None,
) -> dict:
    """
    Transform raw signals into the full data.json structure.

    Args:
        raw_signals: Dict mapping source name -> list of raw signal dicts
        existing_data: Previous data.json content (for merging, optional)

    Returns:
        Complete data.json dict ready for serialization
    """
    # Normalize all signals
    normalized: list[dict] = []
    sources_aggregated = []

    for source, signals in raw_signals.items():
        if signals:
            sources_aggregated.append(source)
        for raw in signals:
            signal = normalize_signal(raw, source)
            if signal:
                normalized.append(signal)

    # Merge with existing signals if provided (dedup by ID)
    if existing_data and "signals" in existing_data:
        existing_ids = {s["id"] for s in normalized}
        for s in existing_data["signals"]:
            if s["id"] not in existing_ids:
                normalized.append(s)
                if s["source"] not in sources_aggregated:
                    sources_aggregated.append(s["source"])

    # Sort by date descending
    normalized.sort(key=lambda s: s.get("date", ""), reverse=True)

    # Compute summaries
    summary = compute_summary(normalized)

    return {
        "meta": {
            "version": (existing_data or {}).get("meta", {}).get("version", 1),
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_signals": len(normalized),
            "sources_aggregated": sorted(set(sources_aggregated)),
        },
        "signals": normalized,
        "summary": summary,
    }


if __name__ == "__main__":
    # Quick test with sample data
    test_raw = {
        "reddit": [
            {
                "content_preview": "This filter is amazing, best purchase ever!",
                "date": "2026-07-19T10:00:00Z",
                "author": "test_user",
                "engagement": {"likes": 10, "replies": 2, "shares": 0},
            }
        ]
    }
    result = transform(test_raw)
    print(json.dumps(result, indent=2))