"""
Small Language Model (SLM) integration for Community Pulse.

Wraps Ollama's API to run Phi-3.5 (or compatible models) for:
- Sentiment analysis (replacing TextBlob)
- Competitor intelligence classification with explanations
- Topic inference

Designed to work in GitHub Actions where Ollama can be installed
as a step in the workflow, or locally if Ollama is running.

Privacy: No PII is sent to the model. Content is truncated to 500 chars
before inference. All processing stays local (Ollama runs on the same machine).
"""

import json
import os
import re
from typing import Any

import requests

# ── Configuration ────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3.5:3.8b-mini-instruct-q4_K_M")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# Fallback: if Ollama is unavailable, use keyword-based analysis
# so the pipeline never hard-fails on model unavailability.
FALLBACK_ON_UNAVAILABLE = os.getenv("SLM_FALLBACK", "true").lower() == "true"


def _check_ollama_available() -> bool:
    """Check if Ollama is running and the model is available."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False
        models = resp.json().get("models", [])
        model_names = [m.get("name", "") for m in models]
        # Check if our model (or a partial match) is available
        for m in model_names:
            if OLLAMA_MODEL.split(":")[0] in m:
                return True
        return False
    except (requests.ConnectionError, requests.Timeout):
        return False


def _call_ollama(prompt: str, system_prompt: str | None = None) -> str | None:
    """Call Ollama's generate API with a prompt. Returns the response text or None."""
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temperature for consistent classification
            "num_predict": 256,
        },
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        if resp.status_code == 200:
            return resp.json().get("response", "").strip()
        return None
    except (requests.ConnectionError, requests.Timeout, requests.RequestException):
        return None


# ── Sentiment Analysis ───────────────────────────────────────────────

SENTIMENT_SYSTEM_PROMPT = (
    "You are a sentiment analysis engine for enterprise storage community signals. "
    "Analyze the sentiment of the given text and respond with ONLY a JSON object "
    "with two fields: 'sentiment_score' (float -1.0 to 1.0) and 'confidence' (float 0.0 to 1.0). "
    "Do not include any other text, markdown, or explanation."
)


def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of a text using the SLM.

    Returns dict with 'sentiment_score' (float -1.0 to 1.0) and 'confidence' (float 0.0 to 1.0).

    Falls back to keyword-based heuristic if Ollama is unavailable.
    """
    if not text or not text.strip():
        return {"sentiment_score": 0.0, "confidence": 0.0}

    # Truncate to keep inference fast
    truncated = text[:500]

    if _check_ollama_available():
        response = _call_ollama(
            f"Analyze the sentiment of this text:\n\n{truncated}",
            system_prompt=SENTIMENT_SYSTEM_PROMPT,
        )
        if response:
            try:
                # Try to parse JSON from the response (handle potential markdown wrapping)
                json_match = re.search(r"\{[^}]+\}", response)
                if json_match:
                    result = json.loads(json_match.group())
                    return {
                        "sentiment_score": max(-1.0, min(1.0, float(result.get("sentiment_score", 0.0)))),
                        "confidence": max(0.0, min(1.0, float(result.get("confidence", 0.5)))),
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
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

    score = (pos_count - neg_count) / (total + 1)  # +1 to avoid division by zero
    confidence = min(0.7, total / 10.0)  # More matches = higher confidence, capped at 0.7

    return {
        "sentiment_score": max(-1.0, min(1.0, round(score, 4))),
        "confidence": round(confidence, 4),
    }


# ── Competitor Intelligence with Explanation ─────────────────────────

INTEL_SYSTEM_PROMPT = (
    "You are a competitive intelligence analyst for Everpure, an enterprise storage company. "
    "Analyze the given text for competitive signals and respond with ONLY a JSON object "
    "with these fields:\n"
    "- 'classification': one of 'threat', 'opportunity', or 'neutral'\n"
    "- 'alert_level': integer 1 (neutral), 2 (opportunity), or 3 (threat)\n"
    "- 'entities_detected': list of company/competitor names mentioned\n"
    "- 'explanation': a short 1-2 sentence explanation of WHY this classification was made\n\n"
    "Rules:\n"
    "- 'threat' = competitor praised, Everpure criticized, or competitor announces a competitive product\n"
    "- 'opportunity' = competitor criticized, Everpure praised, or user asks about migrating TO Everpure\n"
    "- 'neutral' = no clear competitive signal\n"
    "Do not include any other text, markdown, or explanation outside the JSON."
)


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

    if _check_ollama_available():
        response = _call_ollama(
            f"Analyze this text for competitive intelligence signals:\n\n{truncated}",
            system_prompt=INTEL_SYSTEM_PROMPT,
        )
        if response:
            try:
                json_match = re.search(r"\{[^}]+\}", response)
                if json_match:
                    result = json.loads(json_match.group())
                    entities = result.get("entities_detected", [])
                    if isinstance(entities, list):
                        entities = [str(e).lower() for e in entities]
                    else:
                        entities = []

                    return {
                        "classification": result.get("classification", "neutral"),
                        "alert_level": max(1, min(3, int(result.get("alert_level", 1)))),
                        "entities_detected": sorted(set(entities)),
                        "explanation": result.get("explanation", "SLM classification."),
                        "signal_text": truncated[:200],
                    }
            except (json.JSONDecodeError, ValueError, TypeError):
                pass

    # Fallback: use the existing keyword-based logic from transform.py
    return _keyword_intel(truncated)


def _keyword_intel(text: str) -> dict:
    """Keyword-based competitor intel fallback when SLM is unavailable."""
    from scripts.transform import competitor_watch
    result = competitor_watch(text)
    # Add a basic explanation
    if result["classification"] == "threat":
        explanation = f"Competitor praise or Everpure criticism detected involving: {', '.join(result['entities_detected'])}."
    elif result["classification"] == "opportunity":
        explanation = f"Competitor criticism or migration inquiry detected involving: {', '.join(result['entities_detected'])}."
    else:
        explanation = "No significant competitive signal detected."
    result["explanation"] = explanation
    return result


# ── Topic Inference ──────────────────────────────────────────────────

TOPIC_SYSTEM_PROMPT = (
    "You are a topic classifier for enterprise storage and data infrastructure content. "
    "Given a text, classify it into exactly one topic from this list:\n"
    "- storage_performance\n"
    "- enterprise_data_cloud\n"
    "- security_compliance\n"
    "- ai_ml_infrastructure\n"
    "- cloud_native_storage\n"
    "- devops_sre\n"
    "- industry_analysis\n"
    "- data_protection\n"
    "- product_release\n"
    "- engineering_deep_dive\n"
    "- developer_ecosystem\n"
    "- open_source_community\n"
    "- competitor_news\n"
    "- community_discussion\n"
    "- general\n\n"
    "Respond with ONLY the topic name, no other text."
)


def infer_topic(text: str, topic_hint: str | None = None) -> str:
    """
    Infer the topic of a text using the SLM.

    Falls back to keyword-based inference if Ollama is unavailable.
    """
    if not text or not text.strip():
        return topic_hint or "general"

    truncated = text[:500]

    if _check_ollama_available():
        response = _call_ollama(
            f"Classify this text into one topic:\n\n{truncated}",
            system_prompt=TOPIC_SYSTEM_PROMPT,
        )
        if response:
            topic = response.strip().lower()
            valid_topics = [
                "storage_performance", "enterprise_data_cloud", "security_compliance",
                "ai_ml_infrastructure", "cloud_native_storage", "devops_sre",
                "industry_analysis", "data_protection", "product_release",
                "engineering_deep_dive", "developer_ecosystem", "open_source_community",
                "competitor_news", "community_discussion", "general",
            ]
            if topic in valid_topics:
                return topic

    # Fallback to keyword-based inference
    from scripts.sources.rss_scraper import infer_topic as keyword_topic
    return keyword_topic(text, topic_hint)