# Community Pulse — Everpure

A serverless community sentiment monitoring system for Everpure. Collects signals from Reddit, Discord, and GitHub Discussions, runs sentiment analysis, and visualizes the results in a browser-based dashboard — all with no backend servers.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   Reddit API    │     │   Discord API    │     │  GitHub API      │
│   (PRAW)        │     │   (discord.py)   │     │  (PyGithub)      │
└────────┬────────┘     └────────┬─────────┘     └────────┬─────────┘
         │                       │                        │
         ▼                       ▼                        ▼
┌───────────────────────────────────────────────────────────────────┐
│                    scripts/collect.py (Orchestrator)               │
│                                                                   │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐               │
│   │ reddit   │  │ discord  │  │ github_discussions│               │
│   │ .collect()│  │ .collect()│  │ .collect()       │               │
│   └──────────┘  └──────────┘  └──────────────────┘               │
└──────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│                    scripts/transform.py                            │
│   • Normalize signals to standard schema                          │
│   • Compute sentiment scores (TextBlob)                           │
│   • Generate summary rollups (top topics, trend)                  │
└──────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│                    data/data.json                                  │
│   • Single source-of-truth artifact                               │
│   • Committed to repo (data-as-code)                              │
│   • Validated against schemas/data-schema.json                    │
└──────────────────────────┬────────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────────┐
│                    app/ (Stlite Frontend)                          │
│   • Streamlit dashboard running in the browser (no server)        │
│   • Deployed to GitHub Pages                                      │
│   • Reads data.json directly                                      │
└───────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
├── .github/workflows/
│   ├── collect-data.yml       # Scheduled ETL (cron + manual trigger)
│   ├── validate-data.yml      # Schema + quality checks on PR
│   └── deploy-app.yml         # Build & deploy Stlite to GitHub Pages
│
├── scripts/
│   ├── collect.py             # ETL orchestrator
│   ├── transform.py           # Normalization + sentiment analysis
│   ├── validate.py            # JSON Schema validation + quality gates
│   ├── requirements.txt
│   └── sources/
│       ├── __init__.py        # Source registry
│       ├── reddit.py          # Reddit collector
│       ├── discord.py         # Discord collector
│       └── github_discussions.py  # GitHub Discussions collector
│
├── app/
│   ├── app.py                 # Stlite/Streamlit entry point
│   ├── requirements.txt
│   ├── components/
│   │   ├── dashboard.py       # KPI summary cards
│   │   ├── timeline.py        # Sentiment-over-time chart
│   │   └── topic_cloud.py     # Topic breakdown bar chart
│   └── utils/
│       └── data_loader.py     # JSON loader + DataFrame helpers
│
├── data/
│   └── data.json              # Single source-of-truth artifact
│
├── schemas/
│   └── data-schema.json       # JSON Schema for validation
│
├── README.md
└── .gitignore
```

## Data Schema

Each signal in `data.json` captures:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique signal identifier (`sig_<hash>`) |
| `source` | enum | `reddit`, `discord`, or `github_discussions` |
| `source_url` | string | Link to the original post/message |
| `date` | ISO 8601 | When the signal was created |
| `topic` | string | Normalized topic label |
| `sentiment_score` | float | -1.0 (negative) to 1.0 (positive) |
| `confidence` | float | 0.0 (low) to 1.0 (high) |
| `author` | string | Username (anonymized if needed) |
| `content_preview` | string | First 500 chars of content |
| `engagement` | object | `{likes, replies, shares}` |
| `tags` | string[] | Categorization tags |

The `summary` block includes pre-computed rollups: `overall_sentiment`, `top_topics`, and `sentiment_trend` by day.

## Getting Started

### Local Development

```bash
# Install ETL dependencies
pip install -r scripts/requirements.txt

# Run the ETL pipeline (sources without credentials will skip)
python scripts/collect.py

# Validate the output
python scripts/validate.py

# Run the frontend (requires stlite)
pip install stlite
stlite run app/app.py
```

### GitHub Actions Setup

1. Push this repo to GitHub
2. Add the following repository secrets (if using live sources):
   - `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`
   - `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_IDS`
   - `GITHUB_TOKEN` (auto-provided, but override if needed)
3. Enable GitHub Pages (Settings > Pages > Source: GitHub Actions)
4. The `collect-data.yml` workflow runs daily at 06:00 UTC

### Adding a New Source

1. Create `scripts/sources/<name>.py` with a `collect() -> list[dict]` function
2. Register it in `scripts/sources/__init__.py` under the `SOURCES` dict
3. Add API credentials to GitHub Secrets
4. That's it — the orchestrator picks it up automatically

## Workflow Automation

| Workflow | Trigger | Action |
|---|---|---|
| **collect-data.yml** | Daily cron + manual | Runs ETL, validates, commits updated `data.json` |
| **validate-data.yml** | PR to `data/`, `scripts/`, `schemas/` | Validates schema + runs dry-run ETL |
| **deploy-app.yml** | Push to `main` (app/ or data/ changes) | Builds Stlite app, deploys to GitHub Pages |

## Council Review

**3 perspectives on the serverless / GitHub Actions approach:**

**👷 Blue-Collar & Logistics (Warehouse Manager):**
> "Relying on GitHub Actions for your ETL means your data pipeline stops the second GitHub has an outage or you hit your action-minutes cap. What happens when the cron misses a window? I'd want a local fallback script documented so someone can run it from a terminal without needing the CI machinery."

**🧑‍🏫 Education & Growth (Teacher / Community Educator):**
> "The schema is clean, but new contributors will need a clear 'how to add a source' guide. If adding a Reddit scraper requires touching `collect.py`, `sources/reddit.py`, the schema, and the workflow — that's four touchpoints. Consider a plugin-style registration pattern so adding a source is a one-file change."

**👩‍💻 Technical & Architecture (Infrastructure Engineer):**
> "Committing data.json back to the repo from a GitHub Action creates a write loop that can trigger infinite CI runs if not careful. You'll need `[skip ci]` in the commit message and a path filter on the deploy workflow to avoid cascading builds. Also, for anything beyond ~500 signals, a single JSON file will become a git-blame nightmare — consider sharding by month or using JSON Lines."

---

Built with Stlite + Streamlit. No servers required.