# Data Handling & Privacy Policy — Community Pulse

Community Pulse collects public posts and messages from Reddit, Discord,
GitHub Discussions, and RSS feeds, classifies them using a small language
model (Groq API, Llama 3.1 8B Instant), and publishes a processed version
of that data (`data/data.json`) in this repository and — when manually
deployed — on a GitHub Pages dashboard. This document is explicit about
what happens to that data and why, including where this tool falls short
of "pure community support" and is honestly closer to competitive/sentiment
profiling, even with identity stripped out.

## A note on naming

This repo refers to the company being tracked as **"Pure"** in all
human-facing text — titles, docs, dashboard UI, code comments, prompts
sent to the SLM, and sample data — rather than using their actual
trademarked name. That's deliberate: this is an independent project, not
an official or endorsed company tool, and shouldn't wave a real company's
trademark around without their say-so — including in front of a
third-party API provider.

Two things still use the real name, because pseudonymizing them would
break functionality or factual accuracy rather than reduce exposure:
- `scripts/transform.py`'s `COMPETITOR_PATTERNS["pure"]` regex, which has
  to match the company's actual current and former names as they appear
  in real scraped text.
- The RSS feed URLs in `rss_feeds.json`, which point to the company's real
  blog domain because that's where the actual feed lives.

## What gets published

| Field | Community sources (reddit, discord, github_discussions) | Official sources (blog, engineering, industry_news, etc.) |
|---|---|---|
| `author` | **Anonymized.** Hashed to `usr_<hash>` via `scripts/transform.py::normalize_signal()`. Same person maps to the same pseudonym within a source, so repeat-contributor patterns are still visible without exposing a real handle. | Published as-is (institutional accounts, not private individuals). |
| `content_preview` | Published, truncated to 500 characters. | Published as-is. |
| `competitor_intel.explanation` | Published — a short SLM-generated rationale for the classification. | Published. |
| `source_url` | Published — already points to the public post. | Published. |

Signals older than 30 days are pruned on each run (`prune_old_signals()`
in `scripts/transform.py`) — this is a real retention limit, not just a
display filter; old signals don't persist in `data.json` indefinitely.

## Anonymization mechanism

- Implemented in `scripts/transform.py` (`normalize_signal`) and enforced
  by `scripts/validate.py` (`check_privacy_gates`), which **always
  blocks** publication — regardless of `--strict` — if a community-source
  signal has an author that doesn't look like a hash.
- Hashing uses a salt (`ANON_SALT`) stored as a GitHub Actions secret, not
  committed to source. **This matters more than it might look**: an
  earlier version of this file hardcoded the salt as a literal string in
  committed source, which provides no real protection — anyone reading
  the file can recompute the hash for any candidate username instantly.
  The salt must come from the environment.
- If you rotate `ANON_SALT`, existing pseudonyms in already-published
  history won't match new ones going forward — that's intentional; treat
  a salt rotation as a deliberate "reset" of the pseudonym mapping.

## Third-party processing (Groq API)

Signal content (not just usernames — the actual post text) is sent to
Groq's API for sentiment analysis and competitor classification. Per
Groq's published data policy: inputs/outputs are not used for model
training, and are not retained by default except brief (up to 30-day)
logs kept for abuse monitoring / troubleshooting reliability issues.
Zero Data Retention can be enabled in the Groq console for a stricter
guarantee. If you want that guarantee here, turn it on — this repo
doesn't currently assume or require it.

Practically: author identity is anonymized before it ever reaches Groq
(sentiment/classification calls only send `content_preview` and `title`,
not `author`), but the raw post text itself is not anonymized or
redacted before being sent — a post containing self-identifying details
in its body text is still exposed to Groq as an API input, even though
the `author` field is hashed downstream.

## Still open — needs a decision before wider rollout

1. **Platform ToS review.** Confirm scraping + republishing (even
   anonymized) complies with Reddit's API terms and Discord's Developer
   Policy for each source in scope.
2. **Legal sign-off on GDPR/CCPA basis.** Anonymized data may still carry
   re-identification risk (a quoted sentence can itself be identifying).
3. **Repo/dashboard visibility.** Keep this private and deploy manually
   only when you deliberately intend to — see "Running Locally" in
   README.md. A deployed GitHub Pages site is public regardless of the
   repo's visibility.
4. **Scope-limit collection** to channels explicitly meant for vendor
   feedback, rather than general hobbyist/community spaces, if this ever
   moves beyond a portfolio/demo context.

Items 1–4 are policy/legal decisions, not code changes — flagging them
here so they don't get lost.
