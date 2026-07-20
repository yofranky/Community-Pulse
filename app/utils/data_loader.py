"""
Data loader for Community Pulse Stlite frontend.

Reads data.json and provides helper methods for the dashboard components.
In Stlite (Pyodide), files are loaded via HTTP from the repo.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def load_data(data_path: str | Path = "data/data.json") -> dict:
    """Load the community pulse data from a local or relative path."""
    with open(data_path) as f:
        return json.load(f)


def signals_to_dataframe(data: dict) -> pd.DataFrame:
    """Convert the signals array into a pandas DataFrame for charting.

    Includes competitor_intel fields flattened into columns.
    """
    records = []
    for s in data.get("signals", []):
        ci = s.get("competitor_intel", {})
        records.append(
            {
                "id": s["id"],
                "source": s["source"],
                "source_url": s.get("source_url", ""),
                "date": s["date"],
                "topic": s["topic"],
                "sentiment_score": s["sentiment_score"],
                "confidence": s["confidence"],
                "author": s.get("author", ""),
                "content_preview": s.get("content_preview", ""),
                "likes": s.get("engagement", {}).get("likes", 0),
                "replies": s.get("engagement", {}).get("replies", 0),
                "shares": s.get("engagement", {}).get("shares", 0),
                "tags": ", ".join(s.get("tags", [])),
                # Competitor intel fields
                "alert_level": ci.get("alert_level", 1),
                "classification": ci.get("classification", "neutral"),
                "entities_detected": ", ".join(ci.get("entities_detected", [])),
                "signal_text": ci.get("signal_text", ""),
<<<<<<< HEAD
                "explanation": ci.get("explanation", ""),
=======
>>>>>>> 7aa848706d4620cefaa2750ef34e3fe3d9b4aab9
            }
        )
    df = pd.DataFrame(records)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


def get_intel_stats(df: pd.DataFrame) -> dict[str, Any]:
    """Compute intelligence-focused KPI stats from the DataFrame.

    Returns:
        active_threats: count of signals with alert_level == 3
        migration_opportunities: count of signals with classification == "opportunity"
        new_technical_mentions: count of engineering/blog/cloud_native signals in last 7 days
        total_signals: total count
        overall_sentiment: average sentiment score
    """
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    active_threats = len(df[df["alert_level"] == 3]) if not df.empty else 0

    migration_opportunities = (
        len(df[df["classification"] == "opportunity"]) if not df.empty else 0
    )

    technical_sources = ["engineering", "blog", "cloud_native"]
    if not df.empty and "date" in df.columns:
        recent_technical = df[
            (df["source"].isin(technical_sources))
            & (df["date"] >= seven_days_ago)
        ]
        new_technical_mentions = len(recent_technical)
    else:
        new_technical_mentions = 0

    total_signals = len(df) if not df.empty else 0
    overall_sentiment = (
        round(df["sentiment_score"].mean(), 4) if not df.empty else 0.0
    )

    return {
        "active_threats": active_threats,
        "migration_opportunities": migration_opportunities,
        "new_technical_mentions": new_technical_mentions,
        "total_signals": total_signals,
        "overall_sentiment": overall_sentiment,
    }


def get_filtered_signals(df: pd.DataFrame, filter_mode: str) -> pd.DataFrame:
    """Apply sidebar filter to the DataFrame.

    Args:
        df: Full signals DataFrame
        filter_mode: "all", "competitor", or "community"

    Returns:
        Filtered DataFrame
    """
    if df.empty:
        return df

    competitor_sources = ["netapp_community", "dell_infohub"]
    community_sources = ["reddit", "discord", "github_discussions"]

    if filter_mode == "competitor":
        return df[df["source"].isin(competitor_sources)]
    elif filter_mode == "community":
        return df[df["source"].isin(community_sources)]
    else:
        return df


def get_summary_stats(data: dict) -> dict[str, Any]:
    """Extract key summary stats for dashboard KPI cards."""
    meta = data.get("meta", {})
    summary = data.get("summary", {})

    return {
        "total_signals": meta.get("total_signals", 0),
        "sources_count": len(meta.get("sources_aggregated", [])),
        "overall_sentiment": summary.get("overall_sentiment", 0.0),
        "top_topic": (
            summary.get("top_topics", [{}])[0].get("topic", "N/A")
            if summary.get("top_topics")
            else "N/A"
        ),
        "trend_days": len(summary.get("sentiment_trend", [])),
    }