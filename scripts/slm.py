"""
Small Language Model (SLM) integration for Community Pulse.

Uses Groq API (Llama 3.1 8B Instant) for:
- Sentiment analysis
- Competitor intelligence classification with explanations
- Topic inference

Requires GROQ_API_KEY environment variable to be set.
Falls back to keyword-based analysis if the API is unavailable.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests

# ── Configuration ────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_TIMEOUT = int(os.getenv("GROQ_TIMEOUT", "30"))


def _groq_available() -> bool:
    """Check if GROQ_API_KEY is configured (fast check, no network call)."""
    return bool(GROQ_API_KEY)


def _groq_chat(system_prompt: str, user_prompt: str) -> Optional[dict]:
    """
    Call the Groq API with a system prompt and user message.
    Expects a JSON object response.

    Returns the parsed JSON dict, or None on failure.
    """
    if not _groq_available():
        return None

    try:
        resp = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
                "max_tokens": 256,
            },
            timeout=GROQ_TIMEOUT,
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            return json.loads(content)
        else:
            print(f"[slm] Groq API error: {resp.status_code} {resp.text[:200]}")
            return None
    except (requests.ConnectionError, requests.Timeout, requests.RequestException, json.JSONDecodeError, KeyError) as e:
        print(f"[slm] Groq API call failed: {e}")
        return None


# ── Sentiment Analysis ───────────────────────────────────────────────

SENTIMENT_SYSTEM_PROMPT = (
    "You are a sentiment analysis engine for enterprise storage community signals. "
    "Analyze the sentiment of the given text and respond with a JSON object "
    "with two fields: 'sentiment_score' (float -1.0 to 1.0) and 'confidence' (float 0.0 to 1.0)."
)


def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of a text using the SLM (Groq API).

    Returns dict with 'sentiment_score' (float -1.0 to 1.0) and 'confidence' (float 0.0 to 1.0).

    Falls back to keyword-based heuristic if Groq is unavailable.
    """
    if not text or not text.strip():
        return {"sentiment_score": 0.0, "confidence": 0.0}

    truncated = text[:500]

    result = _groq_chat(SENTIMENT_SYSTEM_PROMPT, f"Analyze the sentiment of this text:\n\n{truncated}")
    if result:
        try:
            return {
                "sentiment_score": max(-1.0, min(1.0, float(result.get("sentiment_score", 0.0)))),
                "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.5)))),
            }
        except (ValueError, TypeError):
            pass

    # Fallback: keyword-based heuristic
    return _keyword_sentiment(truncated)


def _keyword_sentiment(text: str) -> dict:
    """Simple keyword-based sentiment fallback when SLM is unavailable."""
    text_lower = text.lower()

    positive_words = [
        "great", "excellent", "amazing", "best", "leader", "outperform",
        "superior", "impressive", "reliable", "innovative", "love",
        "fantastic", "outstanding", "remarkable", "breakthrough",
        "groundbreaking", "efficient", "seamless", "robust", "scalable",
    ]
    negative_words = [
        "poor", "terrible", "unreliable", "slow", "expensive", "overpriced",
        "outdated", "buggy", "frustrating", "disappointing", "failure",
        "downtime", "issue", "problem", "struggle", "worse", "mediocre",
        "inconsistent", "complex", "difficult", "painful", "broken",
    ]

    pos_count = sum(1 for w in positive_words if w in text_lower)
    neg_count = sum(1 for w in negative_words if w in text_lower)
    total = pos_count + neg_count

    if total == 0:
        return {"sentiment_score": 0.0, "confidence": 0.3}

    score = (pos_count - neg_count) / (total + 1)
    confidence = min(0.7, total / 10.0)

    return {
        "sentiment_score": max(-1.0, min(1.0, round(score, 4))),
        "confidence": round(confidence, 4),
    }


# ── Competitor Intelligence with Explanation ─────────────────────────

INTEL_SYSTEM_PROMPT = (
    "You are a competitive intelligence analyst for Pure, an enterprise storage company. "
    "Analyze the given text and respond with a JSON object with these fields:\n"
    "- 'classification': one of 'threat', 'opportunity', or 'neutral'\n"
    "- 'alert_level': integer 1 (neutral), 2 (opportunity), or 3 (threat)\n"
    "- 'entities_detected': list of company/competitor names mentioned\n"
    "- 'explanation': a short 1-2 sentence explanation of WHY this classification was made\n\n"
    "Rules:\n"
    "- 'threat' = competitor praised, Pure criticized, or competitor product announcement\n"
    "- 'opportunity' = competitor criticized, Pure praised, or migration inquiry TO Pure\n"
    "- 'neutral' = no clear competitive signal"
)


# Groq extracts whatever name literally appears in the text (e.g.
# "everpure", "pure storage") — it doesn't know our internal pseudonym
# convention. Normalize any variant onto "pure" so entities_detected is
# consistent regardless of which classification backend produced it.
_PURE_NAME_VARIANTS = re.compile(r"^(everpure|pure\s?storage|pure)$", re.IGNORECASE)

# Free-text fields (the LLM's own explanation, and raw excerpts pulled
# from source content) aren't structured the way entities_detected is —
# they can contain the real company name verbatim if it appears in the
# scraped text or if the model quotes it directly, even though the
# system prompt establishes "Pure" as the identity. Scrub these before
# they reach data.json / the dashboard, same as everywhere else in this
# codebase that avoids displaying the real trademarked name.
_PURE_NAME_INLINE = re.compile(r"\b(everpure|pure\s?storage)\b", re.IGNORECASE)


def _scrub_pure_name(text: str) -> str:
    """Replace any literal mention of the real company name with 'Pure'."""
    if not text:
        return text
    return _PURE_NAME_INLINE.sub("Pure", text)


def classify_competitor_intel(text: str, title: str = "") -> dict:
    """
    Classify a signal as threat/opportunity/neutral with an explanation.

    Args:
        text: Main content body
        title: Optional title

    Returns:
        dict with keys: classification, alert_level, entities_detected, explanation, signal_text
    """
    combined = f"{title} {text}".strip()
    if not combined:
        return {
            "classification": "neutral",
            "alert_level": 1,
            "entities_detected": [],
            "explanation": "No content to analyze.",
            "signal_text": "",
        }

    truncated = combined[:500]

    result = _groq_chat(INTEL_SYSTEM_PROMPT, f"Analyze this text for competitive intelligence signals:\n\n{truncated}")
    if result:
        try:
            entities = result.get("entities_detected", [])
            if isinstance(entities, list):
                entities = [
                    "pure" if _PURE_NAME_VARIANTS.match(str(e).strip()) else str(e).lower()
                    for e in entities
                ]
            else:
                entities = []

            return {
                "classification": str(result.get("classification", "neutral")),
                "alert_level": max(1, min(3, int(result.get("alert_level", 1)))),
                "entities_detected": sorted(set(entities)),
                "explanation": _scrub_pure_name(str(result.get("explanation", "Groq API classification."))),
                "signal_text": _scrub_pure_name(truncated[:200]),
            }
        except (ValueError, TypeError):
            pass

    # Fallback: keyword-based
    return _keyword_intel(truncated)


def _keyword_intel(text: str) -> dict:
    """Keyword-based competitor intel fallback when SLM is unavailable."""
    from scripts.transform import competitor_watch
    result = competitor_watch(text)
    if result["classification"] == "threat":
        explanation = f"Competitor praise or Pure criticism detected involving: {', '.join(result['entities_detected'])}."
    elif result["classification"] == "opportunity":
        explanation = f"Competitor criticism or migration inquiry detected involving: {', '.join(result['entities_detected'])}."
    else:
        explanation = "No significant competitive signal detected."
    result["explanation"] = explanation
    return result


# ── Topic Inference ──────────────────────────────────────────────────

TOPIC_SYSTEM_PROMPT = (
    "You are a topic classifier for enterprise storage content. "
    "Classify the text into exactly one topic and respond with a JSON object "
    "with a single field 'topic' containing the topic name.\n\n"
    "Valid topics: storage_performance, enterprise_data_cloud, security_compliance, "
    "ai_ml_infrastructure, cloud_native_storage, devops_sre, industry_analysis, "
    "data_protection, product_release, engineering_deep_dive, developer_ecosystem, "
    "open_source_community, competitor_news, community_discussion, general"
)


def infer_topic(text: str, topic_hint: Optional[str] = None) -> str:
    """
    Infer the topic of a text using the SLM.

    Falls back to keyword-based inference if Groq is unavailable.
    """
    if not text or not text.strip():
        return topic_hint or "general"

    truncated = text[:500]

    result = _groq_chat(TOPIC_SYSTEM_PROMPT, f"Classify this text into one topic:\n\n{truncated}")
    if result:
        topic = str(result.get("topic", "")).strip().lower()
        valid_topics = [
            "storage_performance", "enterprise_data_cloud", "security_compliance",
            "ai_ml_infrastructure", "cloud_native_storage", "devops_sre",
            "industry_analysis", "data_protection", "product_release",
            "engineering_deep_dive", "developer_ecosystem", "open_source_community",
            "competitor_news", "community_discussion", "general",
        ]
        if topic in valid_topics:
            return topic

    # Fallback
    from scripts.sources.rss_scraper import infer_topic as keyword_topic
    return keyword_topic(text, topic_hint)