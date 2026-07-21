"""
RSS feed aggregator for Community Pulse.

Iterates through feeds configured in rss_feeds.json and converts
each entry into the standardized signal schema.

Handles connectivity errors gracefully so one dead feed never
brings down the entire collection pipeline.

Tuned for enterprise-grade RSS feeds in the data storage and
infrastructure sector (Pure Engineering Blog, StorageNewsletter,
Kubernetes.io, AI Infrastructure Alliance, etc.).
"""

import hashlib
import json
import os
import re
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
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        time_struct = getattr(entry, attr, None)
        if time_struct:
            try:
                return datetime(*time_struct[:6], tzinfo=timezone.utc).isoformat()
            except (ValueError, TypeError):
                continue

    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            return raw

    return datetime.now(timezone.utc).isoformat()


def get_content_preview(entry: feedparser.FeedParserDict) -> str:
    """Extract a text preview from the entry, trying summary then content then title."""
    if hasattr(entry, "summary") and entry.summary:
        return _strip_html(entry.summary)[:500]

    if hasattr(entry, "content") and entry.content:
        for c in entry.content:
            if isinstance(c, dict) and "value" in c:
                return _strip_html(c["value"])[:500]

    if hasattr(entry, "title") and entry.title:
        return entry.title[:500]

    return ""


def _strip_html(text: str) -> str:
    """Very basic HTML tag stripping. Keeps it lightweight (no BeautifulSoup dependency)."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def infer_topic(text: str, topic_hint: str | None = None) -> str:
    """
    Keyword-based topic inference tuned for enterprise storage and data infrastructure.

    Covers: Enterprise Data Cloud, AI-ready infrastructure, Cloud-Native storage,
    Kubernetes, DevOps, and industry trends.
    """
    text_lower = text.lower()

    # ── Enterprise Data Cloud & Storage ──────────────────────────
    if any(w in text_lower for w in [
        "enterprise data cloud", "data cloud", "hybrid cloud", "multi-cloud",
        "data fabric", "data management", "unified storage",
    ]):
        return "enterprise_data_cloud"

    if any(w in text_lower for w in [
        "all-flash", "nvme", "nvme-of", "storage performance", "io latency",
        "throughput", "iops", "storage efficiency", "data reduction",
        "deduplication", "compression", "tiering", "storage class memory",
        "scm", "qlc", "tlc", "hdd", "spinning disk",
    ]):
        return "storage_performance"

    if any(w in text_lower for w in [
        "data protection", "backup", "disaster recovery", "replication",
        "snapshot", "clone", "restore", "rpo", "rto", "business continuity",
        "high availability", "ha pair", "failover",
    ]):
        return "data_protection"

    if any(w in text_lower for w in [
        "security", "ransomware", "encryption", "immutable", "air-gap",
        "zero trust", "compliance", "audit", "data governance", "gdpr",
        "sox", "hipaa", "data sovereignty",
    ]):
        return "security_compliance"

    # ── AI-Ready Infrastructure ──────────────────────────────────
    if any(w in text_lower for w in [
        "ai infrastructure", "ai-ready", "machine learning", "deep learning",
        "llm", "large language model", "training", "inference", "gpu",
        "hpc", "high performance computing", "data pipeline", "mlops",
        "model training", "vector database", "embedding",
    ]):
        return "ai_ml_infrastructure"

    # ── Cloud-Native Storage ─────────────────────────────────────
    if any(w in text_lower for w in [
        "cloud-native", "cloud native", "kubernetes", "k8s", "container",
        "container storage", "csi", "container storage interface",
        "persistent volume", "stateful workload", "operator", "helm",
        "service mesh", "istio", "docker", "pod", "orchestration",
    ]):
        return "cloud_native_storage"

    if any(w in text_lower for w in [
        "devops", "ci/cd", "gitops", "infrastructure as code", "iac",
        "terraform", "ansible", "pulumi", "automation", "sre",
        "observability", "monitoring", "prometheus", "grafana",
    ]):
        return "devops_sre"

    # ── Industry & Market ────────────────────────────────────────
    if any(w in text_lower for w in [
        "industry trend", "market share", "forecast", "gartner",
        "idc", "forrester", "magic quadrant", "wave", "report",
        "acquisition", "partnership", "funding", "series",
    ]):
        return "industry_analysis"

    if any(w in text_lower for w in [
        "open source", "open-source", "community", "contribution",
        "cncf", "linux foundation", "foundation",
    ]):
        return "open_source_community"

    # ── Product & Engineering ────────────────────────────────────
    if any(w in text_lower for w in [
        "release", "announce", "launch", "new feature", "roadmap",
        "beta", "ga", "general availability", "version",
    ]):
        return "product_release"

    if any(w in text_lower for w in [
        "engineering", "architecture", "design", "technical deep dive",
        "how we built", "under the hood", "internals", "performance",
    ]):
        return "engineering_deep_dive"

    if any(w in text_lower for w in [
        "api", "sdk", "integration", "developer", "rest", "grpc",
        "s3", "nfs", "smb", "iscsi", "protocol",
    ]):
        return "developer_ecosystem"

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