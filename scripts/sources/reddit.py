"""
Reddit source collector for Community Pulse.

Collects posts and comments from target Everpure subreddits.
Uses PRAW (Python Reddit API Wrapper) when credentials are available.
Falls back to a placeholder returning an empty list for local dev.
"""

import os

# Placeholder: real implementation requires PRAW and Reddit API credentials
# import praw

SUBREDDITS = ["everpure", "waterfiltration", "commercialkitchen"]

def collect() -> list[dict]:
    """Collect signals from Reddit. Returns a list of raw signal dicts."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("[reddit] No credentials configured. Skipping.")
        return []

    # --- Real implementation (uncomment when ready) ---
    # reddit = praw.Reddit(
    #     client_id=client_id,
    #     client_secret=client_secret,
    #     user_agent="community-pulse/v1 by /u/everpure_dev",
    # )
    # signals = []
    # for subreddit_name in SUBREDDITS:
    #     subreddit = reddit.subreddit(subreddit_name)
    #     for post in subreddit.hot(limit=50):
    #         signals.append({
    #             "id": f"reddit_{post.id}",
    #             "source": "reddit",
    #             "source_url": f"https://reddit.com{post.permalink}",
    #             "date": post.created_utc,
    #             "topic": infer_topic(post.title + " " + post.selftext),
    #             "content_preview": post.selftext[:500] if post.selftext else post.title[:500],
    #             "author": str(post.author) if post.author else "[deleted]",
    #             "engagement": {"likes": post.score, "replies": post.num_comments, "shares": 0},
    #         })
    # return signals

    print("[reddit] Collector registered. Implement with PRAW + API keys.")
    return []


def infer_topic(text: str) -> str:
    """Basic keyword-based topic inference. Replace with ML classifier later."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["filter", "filtration", "pressure", "flow"]):
        return "water_filtration_performance"
    if any(w in text_lower for w in ["support", "customer service", "refund"]):
        return "customer_support"
    if any(w in text_lower for w in ["install", "setup", "fitting"]):
        return "installation_difficulty"
    if any(w in text_lower for w in ["durable", "build quality", "last"]):
        return "product_durability"
    if any(w in text_lower for w in ["feature", "wish", "would love", "api"]):
        return "feature_request"
    return "general"