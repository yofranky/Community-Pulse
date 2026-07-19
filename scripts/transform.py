"""
Transform pipeline for Community Pulse.

Normalizes raw signals from all sources into the standard data.json schema.
Computes sentiment scores and generates summary rollups.

Includes a 'cleaner' function to:
- Remove noise (boilerplate, too-short content, low-confidence entries)
- Deduplicate based on URL and title similarity (fuzzy matching)
- Normalize technical jargon from enterprise storage / data infrastructure sources
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from textblob import TextBlob


# ── Jargon Normalization Map ───────────────────────────────────────
# Maps technical abbreviations and variants to canonical forms.
# Applied to content_preview, topic, and tags during cleaning.
JARGON_MAP = {
    # Storage
    r"\bnvme-of\b": "nvme_over_fabrics",
    r"\bnvme[-\s]?of\b": "nvme_over_fabrics",
    r"\ball[-\s]?flash\b": "all_flash",
    r"\bqlc\b": "qlc_nand",
    r"\btlc\b": "tlc_nand",
    r"\bscm\b": "storage_class_memory",
    r"\biops\b": "io_per_second",
    r"\brpo\b": "recovery_point_objective",
    r"\brto\b": "recovery_time_objective",
    r"\bha\b": "high_availability",
    r"\bdedup\b": "deduplication",
    r"\bcompression\b": "data_compression",
    r"\btiering\b": "storage_tiering",
    r"\bsds\b": "software_defined_storage",
    r"\bhci\b": "hyperconverged_infrastructure",
    r"\bdsl\b": "domain_specific_language",
    # Cloud / Kubernetes
    r"\bk8s\b": "kubernetes",
    r"\bcsi\b": "container_storage_interface",
    r"\bci/cd\b": "ci_cd",
    r"\bgitops\b": "gitops",
    r"\biaac\b": "infrastructure_as_code",
    r"\bmlops\b": "ml_ops",
    r"\baiops\b": "ai_ops",
    r"\bsre\b": "site_reliability_engineering",
    r"\bgrpc\b": "gRPC",
    r"\bistio\b": "istio_service_mesh",
    # AI / ML
    r"\bllm\b": "large_language_model",
    r"\bml\b": "machine_learning",
    r"\bai\b": "artificial_intelligence",
    r"\bgpu\b": "graphics_processing_unit",
    r"\bhpc\b": "high_performance_computing",
    r"\bmlops\b": "ml_ops",
    # Protocols
    r"\bs3\b": "s3_object_storage",
    r"\bnfs\b": "nfs_network_file_system",
    r"\bsmb\b": "smb_protocol",
    r"\biscsi\b": "iscsi_storage",
    r"\bfc\b": "fibre_channel",
    r"\bfcoe\b": "fibre_channel_over_ethernet",
    # Enterprise
    r"\bga\b": "general_availability",
    r"\bsox\b": "sarbanes_oxley",
    r"\bgdpr\b": "general_data_protection_regulation",
    r"\bhipaa\b": "health_insurance_portability_accountability_act",
}

# Boilerplate patterns to filter out (noise removal)
BOILERPLATE_PATTERNS = [
    r"^subscribe to our newsletter",
    r"^click here to",
    r"^read more",
    r"^sign up for",
    r"^copyright \d{4}",
    r"^all rights reserved",
    r"^this is a sponsored post",
    r"^advertisement",
    r"^\s*$",
]

# Minimum content length (characters) for a signal to be considered meaningful
MIN_CONTENT_LENGTH = 50

# Title similarity threshold for deduplication (0.0 = identical, higher = more different)
TITLE_SIMILARITY_THRESHOLD = 0.15

# Cross-source content dedup window in seconds (72 hours)
CROSS_SOURCE_DEDUP_WINDOW = 259200

# Source bias penalty: competitor-owned channels get +1 to alert_level
# so their self-praise doesn't trigger false threat alerts.
# 0 = neutral/third-party, 1 = biased (competitor-owned)
SOURCE_BIAS_MAP: dict[str, int] = {
    "netapp_community": 1,
    "dell_infohub": 1,
}


def content_fingerprint(text: str) -> str:
    """
    Generate a simple content fingerprint for cross-source deduplication.

    Uses a hash of the first 200 characters after stripping whitespace
    and lowercasing. This catches syndicated content that appears across
    multiple feeds (e.g., a press release on NetApp's blog + StorageNewsletter).

    Returns a 16-char hex string.
    """
    normalized = re.sub(r"\s+", " ", text.lower().strip())[:200]
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def normalize_jargon(text: str) -> str:
    """
    Normalize technical jargon in text using the JARGON_MAP.

    Expands abbreviations and standardizes terminology so that
    "k8s", "K8s", and "Kubernetes" all map to the same canonical form
    for topic classification and deduplication.
    """
    for pattern, replacement in JARGON_MAP.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def is_boilerplate(text: str) -> bool:
    """Check if text matches known boilerplate/noise patterns."""
    text_lower = text.strip().lower()
    for pattern in BOILERPLATE_PATTERNS:
        if re.match(pattern, text_lower):
            return True
    return False


def title_similarity(title_a: str, title_b: str) -> float:
    """
    Compute normalized Levenshtein similarity between two title strings.

    Returns a float in [0.0, 1.0] where 1.0 = identical.
    Uses a simple character-level approach suitable for short titles.
    """
    if not title_a or not title_b:
        return 0.0

    a, b = title_a.lower().strip(), title_b.lower().strip()

    # Quick exact match
    if a == b:
        return 1.0

    # Quick containment check (one title is a substring of the other)
    if a in b or b in a:
        return 0.9

    # Levenshtein distance for fuzzy matching
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            cost = 0 if a[i - 1] == b[j - 1] else 1
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
            prev = temp

    max_len = max(m, n)
    if max_len == 0:
        return 1.0
    return 1.0 - (dp[n] / max_len)


def clean_signals(raw_signals: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """
    Clean and deduplicate raw signals before normalization.

    Steps:
    1. Remove boilerplate / noise entries (short content, ads, signup prompts)
    2. Normalize technical jargon in content_preview and tags
    3. Deduplicate by URL (exact match)
    4. Deduplicate by title similarity (fuzzy match within same source)

    Args:
        raw_signals: Dict mapping source name -> list of raw signal dicts

    Returns:
        Cleaned dict with the same structure, minus noise and duplicates
    """
    cleaned: dict[str, list[dict]] = {}

    for source, signals in raw_signals.items():
        if not signals:
            cleaned[source] = []
            continue

        # Step 1: Remove noise
        filtered: list[dict] = []
        for s in signals:
            content = s.get("content_preview", "") or ""
            title = s.get("title", "") or ""

            # Skip empty or too-short content
            if len(content.strip()) < MIN_CONTENT_LENGTH and len(title.strip()) < MIN_CONTENT_LENGTH:
                continue

            # Skip boilerplate
            if is_boilerplate(content) or is_boilerplate(title):
                continue

            filtered.append(s)

        # Step 2: Normalize jargon in content and tags
        for s in filtered:
            if "content_preview" in s and s["content_preview"]:
                s["content_preview"] = normalize_jargon(s["content_preview"])
            if "tags" in s and s["tags"]:
                s["tags"] = [normalize_jargon(t) for t in s["tags"]]

        # Step 3: Deduplicate by URL (exact match)
        seen_urls: set[str] = set()
        url_deduped: list[dict] = []
        for s in filtered:
            url = s.get("source_url", "") or ""
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            url_deduped.append(s)

        # Step 4: Deduplicate by title similarity (fuzzy match within source)
        title_deduped: list[dict] = []
        seen_titles: list[str] = []
        for s in url_deduped:
            title = s.get("title", "") or s.get("content_preview", "")[:80] or ""
            title_normalized = normalize_jargon(title).lower().strip()

            is_duplicate = False
            for seen in seen_titles:
                if title_similarity(title_normalized, seen) >= (1.0 - TITLE_SIMILARITY_THRESHOLD):
                    is_duplicate = True
                    break

            if not is_duplicate:
                seen_titles.append(title_normalized)
                title_deduped.append(s)

        dedup_count = len(signals) - len(title_deduped)
        if dedup_count > 0:
            print(f"[clean] {source}: removed {dedup_count} duplicate/noise signals ({len(title_deduped)} kept)")

        cleaned[source] = title_deduped

    return cleaned


# ── Competitor Watch ───────────────────────────────────────────────
# Defensive/Offensive intelligence: detects competitor mentions and
# classifies signals as Threat, Opportunity, or Neutral.

COMPETITOR_PATTERNS: dict[str, re.Pattern] = {
    "everpure": re.compile(r"\b(everpure|pure\s?storage)\b", re.IGNORECASE),
    "netapp": re.compile(r"\bnetapp\b", re.IGNORECASE),
    "dell": re.compile(r"\bdell\b", re.IGNORECASE),
    "dell_emc": re.compile(r"\bdell[-\s]?emc\b", re.IGNORECASE),
    "emc": re.compile(r"\bemc\b", re.IGNORECASE),
    "hpe": re.compile(r"\bhpe\b|hewlett[\s-]?packard[\s-]?enterprise", re.IGNORECASE),
    "ibm": re.compile(r"\bibm\b", re.IGNORECASE),
    "hitachi": re.compile(r"\bhitachi\b", re.IGNORECASE),
    "nutanix": re.compile(r"\bnutanix\b", re.IGNORECASE),
    "pure_storage": re.compile(r"\bpure\s?storage\b", re.IGNORECASE),
}

PRAISE_PATTERNS = re.compile(
    r"\b(great|excellent|amazing|best[-\s]?in[-\s]?class|leader|outperform|"
    r"superior|impressive|reliable|innovative|game[-\s]?changer|"
    r"love|fantastic|outstanding|remarkable)\b",
    re.IGNORECASE,
)

CRITICISM_PATTERNS = re.compile(
    r"\b(poor|terrible|unreliable|slow|expensive|overpriced|outdated|"
    r"buggy|frustrating|disappointing|failure|downtime|issue|problem|"
    r"struggl|worse|mediocre|inconsistent|complex|difficult)\b",
    re.IGNORECASE,
)

INQUIRY_PATTERNS = re.compile(
    r"\b(how\s+does|compare|vs\.?|versus|alternative|migrate|"
    r"switching|considering|evaluating|review|thoughts\?|"
    r"anyone\s+use|recommend|experience\s+with)\b",
    re.IGNORECASE,
)


def competitor_watch(text: str, title: str = "") -> dict:
    """
    Scan text for competitor mentions and classify the competitive signal.

    Args:
        text: Main content body to scan
        title: Optional title to scan as well

    Returns:
        dict with keys:
            - alert_level: int (1=neutral, 2=opportunity, 3=threat)
            - classification: str ("neutral", "opportunity", "threat")
            - entities_detected: list[str] of competitor names found
            - signal_text: str excerpt of the relevant mention
    """
    combined = f"{title} {text}".lower()
    entities_detected: list[str] = []

    # Step 1: Find which entities are mentioned
    for name, pattern in COMPETITOR_PATTERNS.items():
        if pattern.search(combined):
            entities_detected.append(name)

    if not entities_detected:
        return {
            "alert_level": 1,
            "classification": "neutral",
            "entities_detected": [],
            "signal_text": "",
        }

    # Step 2: Determine sentiment toward detected entities
    has_praise = bool(PRAISE_PATTERNS.search(combined))
    has_criticism = bool(CRITICISM_PATTERNS.search(combined))
    has_inquiry = bool(INQUIRY_PATTERNS.search(combined))

    # Determine if Everpure/Pure is one of the entities mentioned
    everpure_mentioned = "everpure" in entities_detected or "pure_storage" in entities_detected
    competitor_entities = [e for e in entities_detected if e not in ("everpure", "pure_storage")]

    # ── Classification Logic ────────────────────────────────────
    # Threat: Competitor praised OR Everpure criticized
    if (competitor_entities and has_praise and not has_criticism) or \
       (everpure_mentioned and has_criticism and not has_praise):
        classification = "threat"
        alert_level = 3
    # Opportunity: Competitor criticized OR Everpure praised OR migration inquiry
    elif (competitor_entities and has_criticism and not has_praise) or \
         (everpure_mentioned and has_praise and not has_criticism) or \
         (has_inquiry and competitor_entities):
        classification = "opportunity"
        alert_level = 2
    # Mixed sentiment: both praise and criticism detected
    elif has_praise and has_criticism:
        # If competitor is praised AND criticized, it's mixed — lean toward threat
        if competitor_entities:
            classification = "threat"
            alert_level = 3
        else:
            classification = "neutral"
            alert_level = 1
    else:
        classification = "neutral"
        alert_level = 1

    # Step 3: Extract a short signal excerpt (first 150 chars of relevant area)
    signal_text = ""
    for entity in entities_detected:
        # Find the entity in the combined text and grab surrounding context
        idx = combined.find(entity)
        if idx != -1:
            start = max(0, idx - 40)
            end = min(len(combined), idx + len(entity) + 80)
            signal_text = combined[start:end].strip()
            break

    return {
        "alert_level": alert_level,
        "classification": classification,
        "entities_detected": sorted(set(entities_detected)),
        "signal_text": signal_text[:200],
    }


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

    The pipeline runs:
        1. clean_signals()  — noise removal, dedup, jargon normalization
        2. normalize_signal() — per-signal schema conversion
        3. Merge with existing data
        4. compute_summary() — rollup generation

    Args:
        raw_signals: Dict mapping source name -> list of raw signal dicts
        existing_data: Previous data.json content (for merging, optional)

    Returns:
        Complete data.json dict ready for serialization
    """
    # Step 1: Clean — remove noise, deduplicate, normalize jargon
    cleaned = clean_signals(raw_signals)

    # Step 2: Normalize all signals and run competitor watch
    normalized: list[dict] = []
    sources_aggregated = []

    # Cross-source content fingerprint tracker
    # Maps fingerprint -> (earliest_date, source)
    seen_fingerprints: dict[str, tuple[str, str]] = {}

    for source, signals in cleaned.items():
        if signals:
            sources_aggregated.append(source)
        for raw in signals:
            signal = normalize_signal(raw, source)
            if signal:
                content = signal.get("content_preview", "")
                title = raw.get("title", "")

                # ── Cross-source content dedup ──────────────────────
                # If the same content appears across multiple feeds
                # (e.g., a press release on NetApp's blog + StorageNewsletter),
                # keep only the earliest occurrence.
                fingerprint = content_fingerprint(content)
                signal_date = signal.get("date", "")

                if fingerprint in seen_fingerprints:
                    earliest_date, earliest_source = seen_fingerprints[fingerprint]
                    # Only suppress if the current signal is newer (within 72h window)
                    if earliest_date and signal_date:
                        try:
                            earliest_dt = datetime.fromisoformat(earliest_date)
                            current_dt = datetime.fromisoformat(signal_date)
                            diff_seconds = (current_dt - earliest_dt).total_seconds()
                            if 0 <= diff_seconds <= CROSS_SOURCE_DEDUP_WINDOW:
                                print(f"[dedup] Cross-source duplicate suppressed: "
                                      f"'{source}' matches '{earliest_source}' "
                                      f"(fingerprint: {fingerprint})")
                                continue
                        except (ValueError, TypeError):
                            pass

                seen_fingerprints[fingerprint] = (signal_date, source)

                # ── Competitor watch with source bias ───────────────
                intel = competitor_watch(content, title)
                if intel["alert_level"] > 1:
                    # Apply source bias penalty: competitor-owned channels
                    # get +1 to alert_level (their self-praise is expected)
                    bias = SOURCE_BIAS_MAP.get(source, 0)
                    if bias > 0 and intel["classification"] == "threat":
                        # Downgrade biased threat to opportunity
                        intel["alert_level"] = 2
                        intel["classification"] = "opportunity"
                        intel["source_bias_applied"] = True
                        print(f"[intel] BIAS ADJUSTED: {source} self-praise "
                              f"downgraded to opportunity")
                    signal["competitor_intel"] = intel
                    print(f"[intel] {intel['classification'].upper()}: "
                          f"{intel['entities_detected']} (level {intel['alert_level']})")
                normalized.append(signal)

    # Step 3: Merge with existing signals if provided (dedup by ID)
    if existing_data and "signals" in existing_data:
        existing_ids = {s["id"] for s in normalized}
        for s in existing_data["signals"]:
            if s["id"] not in existing_ids:
                normalized.append(s)
                if s["source"] not in sources_aggregated:
                    sources_aggregated.append(s["source"])

    # Sort by date descending
    normalized.sort(key=lambda s: s.get("date", ""), reverse=True)

    # Step 4: Compute summaries
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
    # Quick test with sample enterprise storage data
    test_raw = {
        "engineering": [
            {
                "title": "NVMe-oF Performance Deep Dive",
                "content_preview": "In this post we explore NVMe over Fabrics performance characteristics for all-flash arrays. Our QLC-based systems achieve 2M IOPS with sub-100μs latency.",
                "date": "2026-07-19T10:00:00Z",
                "author": "everpure_eng",
                "tags": ["nvme-of", "performance", "all-flash"],
            },
            {
                "title": "NVMe-oF Performance Deep Dive",  # duplicate
                "content_preview": "In this post we explore NVMe over Fabrics performance characteristics for all-flash arrays.",
                "date": "2026-07-19T10:00:00Z",
                "author": "everpure_eng",
            },
            {
                "title": "Subscribe to our newsletter",  # boilerplate
                "content_preview": "Sign up for the latest updates from Everpure.",
                "date": "2026-07-19T12:00:00Z",
            },
        ],
        "industry_news": [
            {
                "title": "K8s CSI Driver for Enterprise Storage Reaches GA",
                "content_preview": "The Container Storage Interface driver for enterprise storage has reached general availability, enabling stateful workloads on Kubernetes.",
                "date": "2026-07-18T08:00:00Z",
                "author": "storage_news",
            },
        ],
    }
    result = transform(test_raw)
    print(json.dumps(result, indent=2))
    print(f"\nSignals after cleaning: {result['meta']['total_signals']} (expected: 2)")