# Community Pulse — Pure

A serverless community intelligence pipeline for enterprise storage. Collects signals from RSS feeds, Reddit, Discord, and GitHub Discussions, runs SLM-powered sentiment analysis and competitor classification, and visualizes the results in a browser-based dashboard — all with no backend servers.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│   RSS Feeds     │     │   Reddit API     │     │   Discord API    │     │  GitHub API          │
│   (feedparser)  │     │   (PRAW)         │     │   (discord.py)   │     │  (PyGithub)          │
└────────┬────────┘     └────────┬─────────┘     └────────┬─────────┘     └────────┬─────────────┘
         │                       │                        │                        │
         ▼                       ▼                        ▼                        ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                          scripts/collect.py (Orchestrator)                                    │
│                                                                                              │
│   ┌──────────┐  ┌──────────┐  ┌──────────────────┐  ┌──────────────┐                       │
│   │  rss     │  │ reddit   │  │    discord       │  │ github_      │                       │
│   │ .collect()│  │ .collect()│  │  .collect()     │  │ discussions  │                       │
│   └──────────┘  └──────────┘  └──────────────────┘  │ .collect()   │                       │
│                                                      └──────────────┘                       │
└──────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                          scripts/transform.py                                                 │
│   • Clean signals (boilerplate removal, dedup, jargon normalization)                         │
│   • Anonymize authors (SHA-256 hashing — privacy-by-design)                                  │
│   • SLM sentiment analysis (Phi-3.5 via Ollama, falls back to keyword-based)                 │
│   • Competitor intelligence with explanation (Threat/Opportunity/Neutral)                    │
│   • 30-day data retention pruning                                                           │
└──────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                          data/data.json                                                       │
│   • Single source-of-truth artifact                                                          │
│   • Committed to repo (data-as-code)                                                         │
│   • Validated against schemas/data-schema.json                                               │
└──────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────────────────────────────────────────────────────────────────┐
│                          app/ (Stlite Frontend)                                               │
│   • Streamlit dashboard running in the browser (no server)                                   │
│   • Deployed to GitHub Pages                                                                 │
│   • Reads data.json directly                                                                 │
│   • KPI cards, sentiment timeline, triage table with explanations, topic breakdown           │
└──────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
├── .github/workflows/
│   ├── collect-data.yml       # Scheduled ETL (cron + manual trigger, includes Ollama)
│   ├── validate-data.yml      # Schema + quality checks on PR (includes Ollama)
│   └── deploy-app.yml         # Build & deploy Stlite to GitHub Pages
│
├── scripts/
│   ├── __init__.py            # Package marker
│   ├── collect.py             # ETL orchestrator
│   ├── transform.py           # Normalization, SLM sentiment, competitor intel, pruning
│   ├── slm.py                 # SLM wrapper (Ollama + Phi-3.5) with keyword fallback
│   ├── validate.py            # JSON Schema validation + quality gates
│   ├── build_stlite_site.py   # Builds static site for GitHub Pages
│   ├── requirements.txt
│   └── sources/
│       ├── __init__.py        # Source registry
│       ├── rss_scraper.py     # RSS feed aggregator (fully integrated)
│       ├── reddit.py          # Reddit collector
│       ├── discord.py         # Discord collector
│       └── github_discussions.py  # GitHub Discussions collector
│
├── app/
│   ├── __init__.py
│   ├── app.py                 # Stlite/Streamlit entry point
│   ├── requirements.txt
│   ├── components/
│   │   ├── __init__.py
│   │   ├── dashboard.py       # KPI summary cards
│   │   ├── signal_table.py    # Threat/opportunity triage table with explanations
│   │   ├── timeline.py        # Sentiment-over-time chart
│   │   └── topic_cloud.py     # Topic breakdown bar chart
│   └── utils/
│       ├── __init__.py
│       └── data_loader.py     # JSON loader + DataFrame helpers
│
├── data/
│   └── data.json              # Single source-of-truth artifact
│
├── schemas/
│   └── data-schema.json       # JSON Schema for validation
│
├── rss_feeds.json             # RSS feed configuration
├── README.md
└── .gitignore
```

## Data Schema

Each signal in `data.json` captures:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique signal identifier (`sig_<hash>`) |
| `source` | enum | `reddit`, `discord`, `github_discussions`, `blog`, `industry_news`, etc. |
| `source_url` | string | Link to the original post/message |
| `date` | ISO 8601 | When the signal was created |
| `topic` | string | Normalized topic label |
| `sentiment_score` | float | -1.0 (negative) to 1.0 (positive) — computed by SLM |
| `confidence` | float | 0.0 (low) to 1.0 (high) |
| `author` | string | SHA-256 hashed username (`usr_<hash>`) — no PII stored |
| `content_preview` | string | First 500 chars of content |
| `engagement` | object | `{likes, replies, shares}` |
| `tags` | string[] | Categorization tags |
| `competitor_intel` | object | `{alert_level, classification, entities_detected, explanation, signal_text}` |

The `summary` block includes pre-computed rollups: `overall_sentiment`, `top_topics`, and `sentiment_trend` by day.

## Key Features

### SLM-Powered Analysis (Phi-3.5 via Ollama)

Sentiment analysis and competitor intelligence are powered by a Small Language Model (Phi-3.5) running locally via Ollama. The SLM:

- **Analyzes sentiment** with nuanced understanding of enterprise storage context
- **Classifies competitive signals** as Threat, Opportunity, or Neutral with a human-readable explanation
- **Infers topics** from content (15 topic categories)
- **Falls back gracefully** to keyword-based analysis if Ollama is unavailable

### Privacy-by-Design

- **All author names are irreversibly hashed** using SHA-256 with a salt — no PII is ever stored in the repo
- **Deterministic hashing** means the same author always produces the same hash, enabling repeat-contributor tracking without revealing identities
- **30-day data retention** — signals older than 30 days are automatically pruned during each ETL run

### Audit Trail

Every Threat or Opportunity classification includes an `explanation` field describing why the SLM made that decision. This provides a transparent audit trail for all competitive intelligence signals.

## Getting Started

### Local Development

```bash
# Install ETL dependencies
pip install -r scripts/requirements.txt

# Run the ETL pipeline (sources without credentials will skip)
python3 scripts/collect.py

# Validate the output
python3 scripts/validate.py

# Run the frontend (requires stlite)
pip install stlite
stlite run app/app.py
```

### Running with SLM (Optional)

The pipeline works without Ollama (falls back to keyword-based analysis). To enable SLM-powered analysis:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the model
ollama pull phi3.5:3.8b-mini-instruct-q4_K_M

# Start Ollama
ollama serve

# Run the pipeline (it will auto-detect Ollama)
python3 scripts/collect.py
```

### GitHub Actions Setup

1. Push this repo to GitHub
2. Add the following repository secrets (if using live sources):
   - `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`
   - `DISCORD_BOT_TOKEN` / `DISCORD_CHANNEL_IDS`
   - `GITHUB_TOKEN` (auto-provided, but override if needed)
3. Enable GitHub Pages (Settings > Pages > Source: GitHub Actions)
4. The `collect-data.yml` workflow runs daily at 06:00 UTC
5. Ollama and Phi-3.5 are automatically installed in the workflow runner

### Adding a New Source

1. Create `scripts/sources/<name>.py` with a `collect() -> list[dict]` function
2. Register it in `scripts/sources/__init__.py` under the `SOURCES` dict
3. Add API credentials to GitHub Secrets
4. That's it — the orchestrator picks it up automatically

## Workflow Automation

| Workflow | Trigger | Action |
|---|---|---|
| **collect-data.yml** | Daily cron + manual | Installs Ollama, runs ETL with SLM, validates, commits updated `data.json` |
| **validate-data.yml** | PR to `data/`, `scripts/`, `schemas/` | Installs Ollama, validates schema + runs dry-run ETL |
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

#### 7. Ollama Model Download Time
- **Current:** The GitHub Actions workflow downloads the Phi-3.5 model (~2.3GB) on every run
- **Improvement:** Cache the Ollama model between workflow runs using GitHub Actions cache

#### 8. Schema Validation Timing
- **Current:** `validate-data.yml` runs on PRs, but `collect-data.yml` commits data without validation
- **Improvement:** Add validation as a pre-commit step in the ETL workflow

### File-by-File Breakdown

#### Core Application
- **`app/app.py`** - Streamlit entry point with sys.path fix
- **`app/components/dashboard.py`** - KPI cards (threats, opportunities, technical mentions)
- **`app/components/timeline.py`** - Altair scatter chart (source vs sentiment, last 30 days)
- **`app/components/signal_table.py`** - Color-coded triage table with explanation column
- **`app/components/topic_cloud.py`** - Topic breakdown bar chart with sentiment coloring
- **`app/utils/data_loader.py`** - JSON loader, DataFrame conversion, filtering, stats computation

#### ETL Pipeline
- **`scripts/collect.py`** - Orchestrator that runs all source collectors
- **`scripts/slm.py`** - SLM wrapper (Ollama + Phi-3.5) for sentiment, competitor intel, topic inference
- **`scripts/transform.py`** - Cleaning, SLM sentiment, competitor intel with explanations, 30-day pruning, author hashing
- **`scripts/validate.py`** - JSON Schema validation + quality gates
- **`scripts/sources/rss_scraper.py`** - RSS feed aggregator (fully integrated)
- **`scripts/sources/reddit.py`** - Reddit API collector (PRAW)
- **`scripts/sources/discord.py`** - Discord API collector (discord.py)
- **`scripts/sources/github_discussions.py`** - GitHub Discussions collector (PyGithub)

#### Build & Deployment
- **`scripts/build_stlite_site.py`** - Downloads Stlite, inlines files, generates `_site/index.html`
- **`.github/workflows/deploy-app.yml`** - Builds and deploys to GitHub Pages
- **`.github/workflows/collect-data.yml`** - Daily ETL cron job (with Ollama)
- **`.github/workflows/validate-data.yml`** - PR validation for data/schema changes (with Ollama)

#### Data & Configuration
- **`data/data.json`** - Single source-of-truth artifact (committed to repo)
- **`schemas/data-schema.json`** - JSON Schema for validation (includes `explanation` field)
- **`rss_feeds.json`** - RSS feed configuration (10 feeds configured)
- **`app/requirements.txt`** - Streamlit, Altair, Pandas (for Pyodide)
- **`scripts/requirements.txt`** - requests, jsonschema, feedparser, python-dateutil

### Recent Changes

- **`23f968a`** - Author hashing: all usernames irreversibly hashed with SHA-256 for PII-safe tracking
- **`978366e`** - 30-day data retention: automatic pruning of signals older than 30 days
- **`e94e50d`** - SLM integration: Phi-3.5 via Ollama for sentiment analysis and competitor intel with explanations
- **`eaa4afe`** - Added `sys.path.insert()` to resolve app package imports in Stlite
- **`664b2b4`** - Added missing `__init__.py` files for Python package structure
- **`4aa9890`** - Removed duplicate Stlite script tag causing GitHub Pages 404

---

## Privacy & Ethics

Full policy detail lives in [PRIVACY.md](./PRIVACY.md); this section is a
summary of what this tool does, what safeguards are in place, and where
it's honest about its own limits.

**What this tool actually does.** Community Pulse scrapes public posts
from Reddit, Discord, GitHub Discussions, and RSS feeds, and uses an SLM
(Groq API) to classify each one as a competitive "Threat," "Opportunity,"
or "Neutral" signal with a short explanation. That's a real form of
profiling — anonymized author identity doesn't change the fact that
individual people's public statements are being scored for a company's
competitive advantage. We're not going to describe this tool as purely
"for community support" when the code it runs is a competitor-watch
classifier; that framing would be more flattering than accurate.

**Where the "community support" framing is genuinely true.** Alongside
the competitive-intelligence signals, the same classification surfaces
things a community team should actually act on — repeated frustration
with a specific feature, a support gap, a migration-inquiry pattern. A
Community Program Manager using this well would be responding to that,
not just monitoring it. Both uses are real; neither should be presented
as the whole story.

**Safeguards in place:**
- **Author anonymization.** Real usernames from community sources are
  SHA-256 hashed (salted via a required `ANON_SALT` secret, never
  committed to source) before they reach `data.json`. Official/first-party
  accounts (company blog, engineering) are left attributed since they're
  not private individuals.
- **A hard privacy gate.** `scripts/validate.py` refuses to pass — and
  CI refuses to commit — any community-source signal whose author isn't
  properly hashed. This isn't a warning that can be silently ignored.
- **30-day data retention.** Signals older than 30 days are pruned
  automatically on each run, not kept indefinitely.
- **Third-party processing is disclosed, not hidden.** Signal content is
  sent to Groq's API for classification. Per Groq's policy, that data
  isn't used for training and isn't retained by default beyond brief
  abuse-monitoring logs — but the raw post text itself (not just the
  author) is what's sent, and that's not redacted before the API call.
  See PRIVACY.md for the full breakdown of what that means in practice.
- **No real company/brand name in public-facing text.** The company
  this project tracks is referred to as "Pure" throughout code comments,
  UI, docs, and SLM prompts — including in what's sent to Groq — since
  this is an independent project, not an official or company-endorsed
  tool.
- **Deploy is manual, not automatic.** `deploy-app.yml` only runs on
  manual trigger, not on every push, so publishing to a public GitHub
  Pages site is a deliberate choice rather than a side effect.

**What isn't solved yet** — genuinely open items, not just disclaimers:
platform ToS compliance for republishing scraped content, a formal
GDPR/CCPA legal basis, and the fact that anonymized text can still be
re-identifying even without a username attached. These are called out
directly in PRIVACY.md rather than glossed over.

---

## Council Review

**3 perspectives on the SLM-powered competitive intelligence approach:**

**👩‍💻 Technical & Architecture (Infrastructure Engineer):**
> "Running Ollama in a GitHub Actions runner is clever but expensive — the Phi-3.5 model is ~2.3GB and takes several minutes to download on every run. I'd cache the model between runs. Also, the keyword fallback is a good safety net, but you should test that the fallback path doesn't silently degrade quality without alerting anyone."

**🧑‍🏫 Education & Growth (Teacher / Community Educator):**
> "The `explanation` field on every Threat/Opportunity classification is exactly what I'd want to see. It turns the dashboard from a black box into a teaching tool — anyone can understand *why* something was flagged. The author hashing is also a nice touch: you can track repeat contributors without exposing identities."

**👷 Blue-Collar & Logistics (Warehouse Manager):**
> "The 30-day data rotation makes sense — keeps things lean and relevant. But what happens if the workflow fails for a week? Do you lose a full week of signals? I'd want a grace period or a warning when pruning removes more signals than expected."

---

Built with Stlite + Streamlit + Ollama. No servers required.