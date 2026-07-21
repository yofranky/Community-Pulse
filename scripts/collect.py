"""
Community Pulse - ETL Orchestrator.

Runs all configured source collectors, transforms raw signals,
and writes the result to data/data.json.

Usage:
    python scripts/collect.py                          # Run all sources
    python scripts/collect.py --sources reddit,discord  # Run specific sources
    python scripts/collect.py --dry-run                 # Print without writing
"""

import importlib
import json
import os
import sys
from pathlib import Path

# Add project root to path so we can import scripts.sources
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Detect --dry-run before importing transform, so transform.py's CI
# hard-fail on a missing ANON_SALT can be skipped for dry runs. This
# matters specifically for validate-data.yml: GitHub Actions doesn't give
# pull_request workflows triggered from forks access to repo secrets, so
# an external contributor's PR would otherwise always fail here even
# though a dry-run never publishes anything and doesn't need a secure salt.
if "--dry-run" in sys.argv:
    os.environ.setdefault("COMMUNITY_PULSE_DRY_RUN", "1")

from scripts.sources import SOURCES
from scripts.transform import transform


def collect_from_source(source_name: str) -> list[dict]:
    """Dynamically import and run a source collector."""
    module_path = SOURCES.get(source_name)
    if not module_path:
        print(f"[collect] Unknown source: {source_name}")
        return []

    try:
        module = importlib.import_module(module_path.replace("/", "."))
        signals = module.collect()
        print(f"[collect] {source_name}: {len(signals)} signals collected")
        return signals
    except Exception as e:
        print(f"[collect] ERROR collecting from {source_name}: {e}")
        return []


def load_existing_data() -> dict | None:
    """Load existing data.json if it exists."""
    data_path = PROJECT_ROOT / "data" / "data.json"
    if data_path.exists():
        try:
            with open(data_path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[collect] WARNING: Could not load existing data.json: {e}")
            return None
    return None


def write_data(data: dict, dry_run: bool = False):
    """Write the transformed data to data/data.json."""
    data_path = PROJECT_ROOT / "data" / "data.json"
    output = json.dumps(data, indent=2, ensure_ascii=False)

    if dry_run:
        print("\n[collect] DRY RUN - would write:")
        print(output[:500] + "\n... (truncated)")
        return

    # Ensure data directory exists
    data_path.parent.mkdir(parents=True, exist_ok=True)

    with open(data_path, "w") as f:
        f.write(output)
        f.write("\n")  # trailing newline

    print(f"\n[collect] Wrote {data['meta']['total_signals']} signals to {data_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Community Pulse ETL Orchestrator")
    parser.add_argument(
        "--sources",
        default=",".join(SOURCES.keys()),
        help=f"Comma-separated sources to collect from (default: all: {', '.join(SOURCES.keys())})",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print output without writing")
    parser.add_argument("--no-merge", action="store_true", help="Don't merge with existing data")
    args = parser.parse_args()

    # Determine which sources to run
    requested = [s.strip() for s in args.sources.split(",")]
    sources_to_run = [s for s in requested if s in SOURCES]

    if not sources_to_run:
        print(f"[collect] No valid sources specified. Available: {', '.join(SOURCES.keys())}")
        sys.exit(1)

    print(f"[collect] Starting collection from: {', '.join(sources_to_run)}")

    # Collect from each source
    raw_signals: dict[str, list[dict]] = {}
    for source_name in sources_to_run:
        raw_signals[source_name] = collect_from_source(source_name)

    # Load existing data for merging
    existing = None
    if not args.no_merge:
        existing = load_existing_data()
        if existing:
            print(f"[collect] Loaded {existing['meta']['total_signals']} existing signals for merge")

    # Transform
    print("[collect] Transforming signals...")
    data = transform(raw_signals, existing_data=existing)

    # Write
    write_data(data, dry_run=args.dry_run)

    print("[collect] Done.")


if __name__ == "__main__":
    main()