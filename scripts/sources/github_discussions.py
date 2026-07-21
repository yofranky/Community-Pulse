"""
GitHub Discussions source collector for Community Pulse.

Collects discussions from the Pure community repository.
Uses PyGithub when a token is configured. Falls back gracefully.
"""

import os

# Placeholder: real implementation requires PyGithub and a token
# from github import Github

REPO_OWNER = os.getenv("GITHUB_REPO_OWNER", "pure")
REPO_NAME = os.getenv("GITHUB_REPO_NAME", "community")


def collect() -> list[dict]:
    """Collect signals from GitHub Discussions. Returns a list of raw signal dicts."""
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        print("[github_discussions] No GITHUB_TOKEN configured. Skipping.")
        return []

    # --- Real implementation (uncomment when ready) ---
    # g = Github(token)
    # repo = g.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
    # signals = []
    #
    # # GitHub Discussions API (requires PyGithub >= 2.1.0 with discussion support)
    # for discussion in repo.get_discussions(state="all"):
    #     # Skip if too old (configured horizon)
    #     signals.append({
    #         "id": f"ghdisc_{discussion.id}",
    #         "source": "github_discussions",
    #         "source_url": discussion.html_url,
    #         "date": discussion.created_at.isoformat(),
    #         "topic": infer_topic(discussion.title + " " + (discussion.body or "")),
    #         "content_preview": (discussion.body or discussion.title)[:500],
    #         "author": discussion.user.login if discussion.user else "unknown",
    #         "engagement": {
    #             "likes": discussion.upvote_count,
    #             "replies": discussion.comments_count,
    #             "shares": 0,
    #         },
    #     })
    # return signals

    print("[github_discussions] Collector registered. Implement with PyGithub + token.")
    return []


def infer_topic(text: str) -> str:
    """Basic keyword-based topic inference."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["filter", "filtration", "pressure", "flow"]):
        return "water_filtration_performance"
    if any(w in text_lower for w in ["support", "customer service", "refund"]):
        return "customer_support"
    if any(w in text_lower for w in ["install", "setup", "fitting"]):
        return "installation_difficulty"
    if any(w in text_lower for w in ["durable", "build quality", "last"]):
        return "product_durability"
    if any(w in text_lower for w in ["feature", "request", "suggestion", "idea"]):
        return "feature_request"
    return "general"