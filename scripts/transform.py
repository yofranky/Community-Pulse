"""
Transform pipeline for Community Pulse.

Normalizes raw signals from all sources into the standard data.json schema.
Computes sentiment scores and generates summary rollups.

Includes a 'cleaner' function to:
- Remove noise (boilerplate, too-short content, low-confidence entries)
- Deduplicate based on URL and title similarity (fuzzy matching)
- Normalize technical jargon from enterprise storage / data infrastructure sources
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from scripts.slm import analyze_sentiment, classify_competitor_intel, infer_topic as slm_infer_topic


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

# ── Author Anonymization ────────────────────────────────────────────
# All author names are irreversibly hashed using SHA-256 to:
# 1. Preserve privacy (no PII stored in the repo)
# 2. Enable author tracking (same person = same hash across signals)
#    so we can detect repeat positive/negative contributors
# 3. Use a secret salt to prevent rainbow-table reversal
#
# IMPORTANT: the salt must come from an environment secret, not a literal
# in this file. A hardcoded salt provides no protection at all — anyone
# who can read this (public/committed) source can recompute the hash for
# any candidate username in milliseconds. Set ANON_SALT as a GitHub
# Actions secret (generate with `openssl rand -hex 32`).
AUTHOR_HASH_SALT = os.getenv("ANON_SALT")
if not AUTHOR_HASH_SALT:
    if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("COMMUNITY_PULSE_DRY_RUN") != "1":
        # Hard-fail in CI (except dry runs, which don't publish anything —
        # this matters because pull_request workflows from forks don't get
        # access to repo secrets, so a dry-run PR check needs to still pass).
        raise SystemExit(
            "[transform] FATAL: ANON_SALT is not set. Refusing to run in "
            "CI without it — add ANON_SALT as a GitHub Actions secret "
            "(Settings > Secrets and variables > Actions). "
            "Generate one with: openssl rand -hex 32"
        )
    AUTHOR_HASH_SALT = "local-dev-only-not-secure"
    print(
        "[transform] WARNING: ANON_SALT not set in environment. Using an "
        "insecure default salt. Set ANON_SALT as a secret before deploying, "
        "or author hashes will be crackable via rainbow table."
    )

# Sources whose `author` values represent real, individual community
# members (rather than official/first-party accounts) and therefore get
# hashed. Official sources are left attributed since they're not private
# individuals — keep this in sync with the `source` values rss_scraper.py
# assigns per feed.
COMMUNITY_SOURCES = {"reddit", "discord", "github_discussions"}


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
    # An empty/missing field (e.g. rss_scraper.py doesn't set `title`) isn't
    # boilerplate — it's just absent. MIN_CONTENT_LENGTH already catches
    # genuinely empty signals; don't double-penalize a missing title against
    # otherwise-valid content. Without this guard, is_boilerplate("") matches
    # the `^\s*$` pattern and every RSS-collected signal (which has no title
    # field) gets silently dropped as "noise" during cleaning.
    if not text_lower:
        return False
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


# ── Data Retention (30-day pruning) ────────────────────────────────
# Signals older than this threshold are rotated out to ensure relevance
# and minimize data footprint (privacy-by-design policy).
DATA_RETENTION_DAYS = 30


def prune_old_signals(signals: list[dict], max_age_days: int = DATA_RETENTION_DAYS) -> list[dict]:
    """
    Remove signals older than max_age_days from the current time.

    This implements the 30-day data rotation policy:
    - Signals older than 30 days are pruned
    - The pruning timestamp is logged so the audit trail is clear
    - Only signals with a valid date field are considered

    Args:
        signals: List of normalized signal dicts
        max_age_days: Maximum age in days before pruning (default 30)

    Returns:
        Pruned list of signals (younger than max_age_days)
    """
    if not signals:
        return signals

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max_age_days)
    kept = []
    pruned_count = 0

    for s in signals:
        date_str = s.get("date", "")
        if not date_str:
            # Keep signals without dates (don't prune what we can't evaluate)
            kept.append(s)
            continue
        try:
            signal_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if signal_date >= cutoff:
                kept.append(s)
            else:
                pruned_count += 1
        except (ValueError, TypeError):
            kept.append(s)

    if pruned_count > 0:
        print(f"[retention] Pruned {pruned_count} signals older than {max_age_days} days "
              f"(cutoff: {cutoff.strftime('%Y-%m-%d')})")

    return kept


# ── Competitor Watch ───────────────────────────────────────────────
# Defensive/Offensive intelligence: detects competitor mentions and
# classifies signals as Threat, Opportunity, or Neutral.

COMPETITOR_PATTERNS: dict[str, re.Pattern] = {
    # "pure" is our internal label for the real company this project tracks.
    # The regex itself still has to match the real company's actual current
    # and former names as they appear in scraped text — only the label used
    # in entities_detected / UI output is pseudonymized. See PRIVACY.md.
    "pure": re.compile(r"\b(everpure|pure\s?storage)\b", re.IGNORECASE),
    "netapp": re.compile(r"\bnetapp\b", re.IGNORECASE),
    "dell": re.compile(r"\bdell\b", re.IGNORECASE),
    "dell_emc": re.compile(r"\bdell[-\s]?emc\b", re.IGNORECASE),
    "emc": re.compile(r"\bemc\b", re.IGNORECASE),
    "hpe": re.compile(r"\bhpe\b|hewlett[\s-]?packard[\s-]?enterprise", re.IGNORECASE),
    "ibm": re.compile(r"\bibm\b", re.IGNORECASE),
    "hitachi": re.compile(r"\bhitachi\b", re.IGNORECASE),
    "nutanix": re.compile(r"\bnutanix\b", re.IGNORECASE),
}

# ── Brand Collision Disambiguation ─────────────────────────────────
# The real company's current name is shared by two unrelated businesses:
# an enterprise storage vendor, and a decades-old commercial water-
# filtration brand. Any match scraped from the open web could be about
# either one. We disambiguate using surrounding context rather than
# assuming every hit is about us — misattributing water-filter chatter
# as storage "competitor intel" would poison the sentiment numbers with
# noise.
PURE_WATER_FILTER_CONTEXT = re.compile(
    r"\b(water\s?filter|filtration|cartridge|foodservice|food\s?service|"
    r"restaurant|kitchen|ice\s?machine|espresso|coffee|beverage|faucet|"
    r"nsf\s?certif|pentair|drinking\s?water|tap\s?water)\b",
    re.IGNORECASE,
)
PURE_STORAGE_CONTEXT = re.compile(
    r"\b(storage|flash|array|nvme|iops|latency|throughput|kubernetes|"
    r"cloud|data\s?management|backup|replication|purity|evergreen|"
    r"portworx|san\b|nas\b|enterprise\s?data)\b",
    re.IGNORECASE,
)


def _is_probably_wrong_pure(combined_text: str) -> bool:
    """
    Return True if a "pure" mention is more likely about the water-filter
    brand than the storage company, based on surrounding keyword context.
    Ambiguous or storage-flavored text is given the benefit of the doubt
    and treated as ours (False).
    """
    has_water_context = bool(PURE_WATER_FILTER_CONTEXT.search(combined_text))
    has_storage_context = bool(PURE_STORAGE_CONTEXT.search(combined_text))
    return has_water_context and not has_storage_context

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

    This is also used as the keyword-based fallback in scripts/slm.py when
    the Groq API is unavailable.

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
        if not pattern.search(combined):
            continue
        # Brand-collision guard: a "pure" hit that reads like it's about
        # the water-filter brand, not us, gets skipped rather than
        # counted as a self-mention.
        if name == "pure" and _is_probably_wrong_pure(combined):
            continue
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

    # Determine if we (Pure) are one of the entities mentioned
    pure_mentioned = "pure" in entities_detected
    competitor_entities = [e for e in entities_detected if e != "pure"]

    # ── Classification Logic ────────────────────────────────────
    # Threat: Competitor praised OR we're criticized
    if (competitor_entities and has_praise and not has_criticism) or \
       (pure_mentioned and has_criticism and not has_praise):
        classification = "threat"
        alert_level = 3
    # Opportunity: Competitor criticized OR we're praised OR migration inquiry
    elif (competitor_entities and has_criticism and not has_praise) or \
         (pure_mentioned and has_praise and not has_criticism) or \
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
        # Use SLM for sentiment analysis (falls back to keyword-based if unavailable)
        slm_result = analyze_sentiment(content)
        sentiment = slm_result["sentiment_score"]
        confidence = slm_result["confidence"]

    # Parse / normalize date
    date_str = raw.get("date", "")
    if isinstance(date_str, (int, float)):
        date_str = datetime.fromtimestamp(date_str, tz=timezone.utc).isoformat()

    # Hash the author name (privacy-by-design, preserves tracking).
    # Only community sources (real individuals) get hashed — official
    # first-party accounts (blog, engineering, etc.) are left attributed.
    raw_author = raw.get("author", "anonymous")
    if raw_author and raw_author != "anonymous" and source in COMMUNITY_SOURCES:
        hashed = hashlib.sha256(
            f"{AUTHOR_HASH_SALT}:{source}:{raw_author}".encode()
        ).hexdigest()[:16]
        author = f"usr_{hashed}"
    else:
        author = raw_author

    return {
        "id": signal_id,
        "source": source,
        "source_url": raw.get("source_url", ""),
        "date": date_str,
        "topic": raw.get("topic", "general"),
        "sentiment_score": max(-1.0, min(1.0, sentiment)),
        "confidence": max(0.0, min(1.0, confidence if confidence is not None else 0.5)),
        "author": author,
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
            # Prefer the signal's own `source` field (set per-entry by
            # rss_scraper.py, which aggregates many feeds — reddit,
            # netapp_community, dell_infohub, blog, engineering, etc. —
            # under one registry key "rss"). Without this, every
            # RSS-sourced signal collapses to source="rss" and
            # SOURCE_BIAS_MAP lookups (keyed on "netapp_community" /
            # "dell_infohub") never match.
            effective_source = raw.get("source", source)
            signal = normalize_signal(raw, effective_source)
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
                                      f"'{effective_source}' matches '{earliest_source}' "
                                      f"(fingerprint: {fingerprint})")
                                continue
                        except (ValueError, TypeError):
                            pass

                seen_fingerprints[fingerprint] = (signal_date, effective_source)

                # ── Competitor watch with SLM (includes explanation) ──
                intel = classify_competitor_intel(content, title)
                if intel["alert_level"] > 1:
                    # Apply source bias penalty: competitor-owned channels
                    # get +1 to alert_level (their self-praise is expected)
                    bias = SOURCE_BIAS_MAP.get(effective_source, 0)
                    if bias > 0 and intel["classification"] == "threat":
                        # Downgrade biased threat to opportunity
                        intel["alert_level"] = 2
                        intel["classification"] = "opportunity"
                        intel["source_bias_applied"] = True
                        print(f"[intel] BIAS ADJUSTED: {effective_source} self-praise "
                              f"downgraded to opportunity")
                    signal["competitor_intel"] = intel
                    print(f"[intel] {intel['classification'].upper()}: "
                          f"{intel['entities_detected']} (level {intel['alert_level']})")
                    if intel.get("explanation"):
                        print(f"[intel] Why: {intel['explanation']}")
                normalized.append(signal)

    # Step 3: Prune old signals from existing data (30-day retention policy)
    if existing_data and "signals" in existing_data:
        existing_data["signals"] = prune_old_signals(existing_data["signals"])
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
                "author": "pure_eng",
                "tags": ["nvme-of", "performance", "all-flash"],
            },
            {
                "title": "NVMe-oF Performance Deep Dive",  # duplicate
                "content_preview": "In this post we explore NVMe over Fabrics performance characteristics for all-flash arrays.",
                "date": "2026-07-19T10:00:00Z",
                "author": "pure_eng",
            },
            {
                "title": "Subscribe to our newsletter",  # boilerplate
                "content_preview": "Sign up for the latest updates from Pure.",
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