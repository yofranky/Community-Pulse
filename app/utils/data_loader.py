"""
Data loader for Community Pulse Stlite frontend.

Reads data.json and provides helper methods for the dashboard components.
In Stlite (Pyodide), files are loaded via HTTP from the repo.
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd


def load_data(data_path: str | Path = "data/data.json") -> dict:
    """Load the community pulse data from a local or relative path."""
    with open(data_path) as f:
        return json.load(f)


def signals_to_dataframe(data: dict) -> pd.DataFrame:
    """Convert the signals array into a pandas DataFrame for charting."""
    records = []
    for s in data.get("signals", []):
        records.append(
            {
                "id": s["id"],
                "source": s["source"],
                "date": s["date"],
                "topic": s["topic"],
                "sentiment_score": s["sentiment_score"],
                "confidence": s["confidence"],
                "author": s.get("author", ""),
                "likes": s.get("engagement", {}).get("likes", 0),
                "replies": s.get("engagement", {}).get("replies", 0),
                "shares": s.get("engagement", {}).get("shares", 0),
                "tags": ", ".join(s.get("tags", [])),
            }
        )
    df = pd.DataFrame(records)
    if not df.empty and "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
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