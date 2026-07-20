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

## Technical Deep Dive

### How the Stlite Deployment Works

Community Pulse uses [Stlite](https://github.com/whitphx/stlite) (a WebAssembly-based Python runtime) to run a Streamlit dashboard entirely in the browser with no backend server. Here's the technical flow:

1. **Build Time** (`scripts/build_stlite_site.py`):
   - Downloads `@stlite/browser@1.8.1` npm package (~87MB)
   - Copies the Stlite runtime to `_site/stlite/`
   - Inlines all Python source files and `data.json` as JavaScript template literals in `_site/index.html`
   - The HTML uses a dynamic `import("./stlite/stlite.js")` to load the runtime

2. **Runtime** (browser):
   - Stlite's Pyodide runtime loads in the browser
   - Mounts the Streamlit app from the inlined files
   - The app reads `data/data.json` directly from the virtual filesystem
   - All rendering happens client-side via WebAssembly

3. **Deployment** (`.github/workflows/deploy-app.yml`):
   - Triggers on push to `main` when `app/`, `data/`, or build script changes
   - Runs `python3 scripts/build_stlite_site.py`
   - Uploads `_site/` as a GitHub Pages artifact
   - Deploys to `https://yofranky.github.io/Community-Pulse/`

### Critical Implementation Details

#### The Module/Package Conflict

**Problem:** In Stlite's virtual filesystem, we have both:
- `app/app.py` (a module file)
- `app/` (a package directory with `__init__.py`)

Python's import system sees `app.py` first and treats `app` as a module, not a package. This causes:
```
ModuleNotFoundError: No module named 'app.components'; 'app' is not a package
```

**Solution:** Add the parent directory to `sys.path` at the top of `app/app.py`:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

This tells Python to look in the parent directory for packages, bypassing the module/package conflict.

#### The GitHub Pages Path Resolution Issue

**Problem:** The original build script included an external script tag:
```html
<script type="module" src="/stlite/stlite.js"></script>
```

When served from GitHub Pages at `/Community-Pulse/`, this resolves to:
- `https://yofranky.github.io/stlite/stlite.js` (WRONG - 404 error)

Instead of:
- `https://yofranky.github.io/Community-Pulse/stlite/stlite.js` (CORRECT)

**Solution:** Remove the external script tag entirely. The inline dynamic import already handles loading:
```javascript
const stlite = await import("./stlite/stlite.js");
```

This uses a relative path that resolves correctly regardless of the deployment subdirectory.

#### Required Package Markers

All directories in the `app/` tree need `__init__.py` files to be recognized as Python packages:
- `app/__init__.py`
- `app/components/__init__.py`
- `app/utils/__init__.py`

These are inlined into the generated HTML by the build script alongside the actual source files.

### Known Limitations & Improvement Opportunities

#### 1. Build Artifacts in Git Ignore
The `_site/` directory is git-ignored, which is correct for production. However:
- **Issue:** The GitHub Actions workflow rebuilds from scratch on every deploy
- **Improvement:** Cache the `@stlite/browser` npm package between runs to speed up builds (~87MB download)

#### 2. Data Freshness
- **Current:** `data.json` is committed to the repo and updated by GitHub Actions
- **Limitation:** Data is only as fresh as the last successful workflow run
- **Improvement:** Add a webhook trigger to refresh data on demand, or implement a TTL-based cache invalidation

#### 3. Error Handling in Stlite
- **Current:** Generic error message displayed in the UI
- **Improvement:** Add structured logging to a remote endpoint (e.g., Sentry) to track Pyodide initialization failures in production

#### 4. Bundle Size
- **Current:** ~89MB total (mostly Stlite runtime)
- **Improvement:** Investigate lazy loading or code splitting to reduce initial load time. Consider using a CDN for the Stlite runtime with a local fallback.

#### 5. Import Path Fragility
- **Current:** `sys.path.insert()` hack to resolve module/package conflict
- **Improvement:** Restructure the project to avoid the conflict entirely. Options:
  - Rename `app/app.py` to `app/main.py` and update the entrypoint
  - Use a flat module structure without subpackages
  - Implement a custom Stlite filesystem loader

#### 6. No Local Development Parity
- **Current:** `stlite run app/app.py` works locally, but the exact runtime differs from the GitHub Actions build
- **Improvement:** Add a Dockerfile or dev container to ensure identical environments

#### 7. Missing RSS Scraper
- **Current:** `scripts/sources/rss_scraper.py` exists but isn't integrated
- **Improvement:** Complete the RSS integration to pull from industry news sites

#### 8. Schema Validation Timing
- **Current:** `validate-data.yml` runs on PRs, but `collect-data.yml` commits data without validation
- **Improvement:** Add validation as a pre-commit step in the ETL workflow

### File-by-File Breakdown

#### Core Application
- **`app/app.py`** - Streamlit entry point with sys.path fix
- **`app/components/dashboard.py`** - KPI cards (threats, opportunities, technical mentions)
- **`app/components/timeline.py`** - Altair scatter chart (source vs sentiment, last 30 days)
- **`app/components/signal_table.py`** - Color-coded triage table (threats/opportunities only)
- **`app/components/topic_cloud.py`** - Topic breakdown bar chart with sentiment coloring
- **`app/utils/data_loader.py`** - JSON loader, DataFrame conversion, filtering, stats computation

#### ETL Pipeline
- **`scripts/collect.py`** - Orchestrator that runs all source collectors
- **`scripts/sources/reddit.py`** - Reddit API collector (PRAW)
- **`scripts/sources/discord.py`** - Discord API collector (discord.py)
- **`scripts/sources/github_discussions.py`** - GitHub Discussions collector (PyGithub)
- **`scripts/sources/rss_scraper.py`** - RSS feed scraper (incomplete)
- **`scripts/transform.py`** - Normalization, sentiment analysis (TextBlob), summary rollups
- **`scripts/validate.py`** - JSON Schema validation + quality gates

#### Build & Deployment
- **`scripts/build_stlite_site.py`** - Downloads Stlite, inlines files, generates `_site/index.html`
- **`.github/workflows/deploy-app.yml`** - Builds and deploys to GitHub Pages
- **`.github/workflows/collect-data.yml`** - Daily ETL cron job
- **`.github/workflows/validate-data.yml`** - PR validation for data/schema changes

#### Data & Configuration
- **`data/data.json`** - Single source-of-truth artifact (committed to repo)
- **`schemas/data-schema.json`** - JSON Schema for validation
- **`rss_feeds.json`** - RSS feed configuration
- **`app/requirements.txt`** - Streamlit, Altair, Pandas (for Pyodide)
- **`scripts/requirements.txt`** - PRAW, discord.py, PyGithub, TextBlob, pandas

### Recent Fixes (Git History)

- **`eaa4afe`** - Added `sys.path.insert()` to resolve app package imports in Stlite
- **`664b2b4`** - Added missing `__init__.py` files for Python package structure
- **`4aa9890`** - Removed duplicate Stlite script tag causing GitHub Pages 404

---

## Council Review

**3 perspectives on the serverless / GitHub Actions approach:**

**👷 Blue-Collar & Logistics (Warehouse Manager):**
> "Relying on GitHub Actions for your ETL means your data pipeline stops the second GitHub has an outage or you hit your action-minutes cap. What happens when the cron misses a window? I'd want a local fallback script documented so someone can run it from a terminal without needing the CI machinery."

**🧑‍🏫 Education & Growth (Teacher / Community Educator):**
> "The schema is clean, but new contributors will need a clear 'how to add a source' guide. If adding a Reddit scraper requires touching `collect.py`, `sources/reddit.py`, the schema, and the workflow — that's four touchpoints. Consider a plugin-style registration pattern so adding a source is a one-file change."

**👩‍💻 Technical & Architecture (Infrastructure Engineer):**
> "Committing data.json back to the repo from a GitHub Action creates a write loop that can trigger infinite CI runs if not careful. You'll need `[skip ci]` in the commit message and a path filter on the deploy workflow to avoid cascading builds. Also, for anything beyond ~500 signals, a single JSON file will become a git-blame nightmare — consider sharding by month or using JSON Lines."

**🧑‍🔬 Additional Perspective (QA Engineer / Tester):**
> "The Stlite runtime is ~87MB and loads entirely in the browser. There's no apparent test coverage for the frontend components, and the error handling is generic. I'd want to see: (1) unit tests for `data_loader.py` functions, (2) integration tests that verify the build script produces valid HTML, and (3) a staging deployment to test changes before they hit production."

**👨‍👩‍👧‍👦 General Consumer (Everyday Working Parent):**
> "I appreciate that this works without installing anything, but waiting 30-60 seconds for the first load is a long time. Can you add a progress indicator or skeleton UI? Also, what happens if my internet is slow? Is there a way to cache the Stlite runtime locally so it doesn't re-download every time?"

---

Built with Stlite + Streamlit. No servers required.
