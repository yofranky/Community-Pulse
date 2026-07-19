"""
RSS feed aggregator for Community Pulse.

Iterates through feeds configured in rss_feeds.json and converts
each entry into the standardized signal schema.

Handles connectivity errors gracefully so one dead feed never
brings down the entire collection pipeline.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser

# Path to feed configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FEEDS_CONFIG_PATH = PROJECT_ROOT / "rss_feeds.json"


def load_feed_config() -> list[dict]:
    """Load the RSS feed configuration from rss_feeds.json."""
    if not FEEDS_CONFIG_PATH.exists():
        print(f"[rss] No config found at {FEEDS_CONFIG_PATH}. Skipping.")
        return []
    try:
        with open(FEEDS_CONFIG_PATH) as f:
            feeds = json.load(f)
        print(f"[rss] Loaded {len(feeds)} feed(s) from config")
        return feeds
    except (json.JSONDecodeError, OSError) as e:
        print(f"[rss] ERROR: Failed to load feed config: {e}")
        return []


def parse_date(entry: feedparser.FeedParserDict) -> str:
    """Extract and normalize a published/updated date from an RSS entry."""
    # Try multiple date fields in order of reliability
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        time_struct = getattr(entry, attr, None)
        if time_struct:
            try:
                return datetime(*time_struct[:6], tzinfo=timezone.utc).isoformat()
            except (ValueError, TypeError):
                continue

    # Fall back to raw string if available
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            return raw

    return datetime.now(timezone.utc).isoformat()


def get_content_preview(entry: feedparser.FeedParserDict) -> str:
    """Extract a text preview from the entry, trying summary then content then title."""
    # RSS <description> or Atom <summary>
    if hasattr(entry, "summary") and entry.summary:
        return _strip_html(entry.summary)[:500]

    # Atom <content> (may be a list of dicts)
    if hasattr(entry, "content") and entry.content:
        for c in entry.content:
            if isinstance(c, dict) and "value" in c:
                return _strip_html(c["value"])[:500]

    # Fall back to title
    if hasattr(entry, "title") and entry.title:
        return entry.title[:500]

    return ""


def _strip_html(text: str) -> str:
    """Very basic HTML tag stripping. Keeps it lightweight (no BeautifulSoup dependency)."""
    import re

    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def infer_topic(text: str, topic_hint: str | None = None) -> str:
    """Keyword-based topic inference with fallback to configured hint."""
    text_lower = text.lower()

    if any(w in text_lower for w in ["filter", "filtration", "pressure", "flow", "cartridge"]):
        return "water_filtration_performance"
    if any(w in text_lower for w in ["support", "customer service", "refund", "warranty"]):
        return "customer_support"
    if any(w in text_lower for w in ["install", "setup", "fitting", "mount"]):
        return "installation_difficulty"
    if any(w in text_lower for w in ["durable", "build quality", "lifetime", "robust"]):
        return "product_durability"
    if any(w in text_lower for w in ["feature", "release", "announce", "new", "launch"]):
        return "product_release"
    if any(w in text_lower for w in ["api", "sdk", "integration", "developer"]):
        return "developer_ecosystem"
    if any(w in text_lower for w in ["industry", "trend", "market", "regulation"]):
        return "industry_trends"

    # Fall back to configured hint if available
    if topic_hint:
        return topic_hint

    return "general"


def collect() -> list[dict]:
    """
    Iterate through all configured RSS feeds and collect signals.

    Each feed is fetched independently. If one feed fails (timeout, DNS error,
    malformed XML), the error is logged and processing continues with the next feed.

    Returns:
        list[dict]: Raw signal dicts ready for the transform pipeline.
    """
    feeds = load_feed_config()
    if not feeds:
        return []

    all_signals: list[dict] = []

    for feed_cfg in feeds:
        feed_id = feed_cfg.get("id", "unknown")
        feed_url = feed_cfg.get("url", "")
        source_label = feed_cfg.get("source_label", "rss")
        topic_hint = feed_cfg.get("topic_hint")
        max_entries = feed_cfg.get("max_entries_per_run", 20)

        if not feed_url:
            print(f"[rss] WARNING: Feed '{feed_id}' has no URL. Skipping.")
            continue

        print(f"[rss] Fetching feed '{feed_id}' from {feed_url}")

        try:
            parsed = feedparser.parse(feed_url)
        except (ConnectionError, TimeoutError, OSError) as e:
            print(f"[rss] ERROR: Feed '{feed_id}' connection failed: {e}")
            continue
        except Exception as e:
            print(f"[rss] ERROR: Feed '{feed_id}' unexpected error during fetch: {e}")
            continue

        # Check for feedparser-level errors (bozo bit)
        if parsed.bozo and not parsed.entries:
            bozo_msg = getattr(parsed, "bozo_exception", "unknown parse error")
            print(f"[rss] WARNING: Feed '{feed_id}' returned no entries (bozo: {bozo_msg})")
            continue

        entry_count = len(parsed.entries)
        print(f"[rss] Feed '{feed_id}': {entry_count} entries found")

        for entry in parsed.entries[:max_entries]:
            try:
                title = getattr(entry, "title", "")
                link = getattr(entry, "link", "")
                content = get_content_preview(entry)
                date_str = parse_date(entry)
                author = getattr(entry, "author", "") or getattr(entry, "author_detail", {}).get("name", "")

                # Build a deterministic ID from the feed URL + entry link or title
                dedup_key = f"rss:{feed_id}:{link or title}"
                signal_id = hashlib.sha256(dedup_key.encode()).hexdigest()[:12]

                full_text = f"{title} {content}"
                topic = infer_topic(full_text, topic_hint)

                signal = {
                    "id": f"sig_{signal_id}",
                    "source": source_label,
                    "source_url": link,
                    "date": date_str,
                    "topic": topic,
                    "sentiment_score": None,  # Will be computed by transform.py
                    "confidence": None,
                    "author": author or feed_cfg.get("name", source_label),
                    "content_preview": content[:500],
                    "engagement": {"likes": 0, "replies": 0, "shares": 0},
                    "tags": [feed_id, source_label, topic],
                }

                all_signals.append(signal)

            except Exception as e:
                print(f"[rss] WARNING: Feed '{feed_id}' failed to process entry: {e}")
                continue

    print(f"[rss] Total signals collected: {len(all_signals)}")
    return all_signals


if __name__ == "__main__":
    """Quick test: run the collector and print results."""
    signals = collect()
    print(f"\nCollected {len(signals)} signals:")
    for s in signals[:5]:
        print(f"  [{s['source']}] {s['topic']}: {s['content_preview'][:80]}...")
    if len(signals) > 5:
        print(f"  ... and {len(signals) - 5} more")