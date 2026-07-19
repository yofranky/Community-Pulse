"""
Validation pipeline for Community Pulse.

Validates data.json against the JSON Schema and enforces quality gates:
- sentiment_score must be in [-1.0, 1.0]
- No duplicate signal IDs
- Required fields present
- Confidence thresholds
"""

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import validate as json_validate


def load_schema(path: str | Path = "schemas/data-schema.json") -> dict:
    """Load the JSON Schema file."""
    with open(path) as f:
        return json.load(f)


def load_data(path: str | Path = "data/data.json") -> dict:
    """Load the data.json file."""
    with open(path) as f:
        return json.load(f)


def check_quality_gates(data: dict) -> list[str]:
    """Run quality checks beyond schema validation. Returns list of error messages."""
    errors = []

    # Check for duplicate IDs
    ids = [s["id"] for s in data.get("signals", [])]
    if len(ids) != len(set(ids)):
        seen = set()
        dups = {id_ for id_ in ids if id_ in seen or seen.add(id_)}
        errors.append(f"Duplicate signal IDs found: {dups}")

    # Check sentiment_score range (schema catches this too, but double-check)
    for s in data.get("signals", []):
        score = s.get("sentiment_score", 0)
        if score < -1.0 or score > 1.0:
            errors.append(f"Signal {s['id']}: sentiment_score {score} out of range [-1.0, 1.0]")

    # Check confidence is reasonable
    for s in data.get("signals", []):
        conf = s.get("confidence", 0)
        if conf < 0.0 or conf > 1.0:
            errors.append(f"Signal {s['id']}: confidence {conf} out of range [0.0, 1.0]")

    # Check meta consistency
    meta = data.get("meta", {})
    if meta.get("total_signals", 0) != len(data.get("signals", [])):
        errors.append(
            f"meta.total_signals ({meta.get('total_signals')}) does not match "
            f"actual signal count ({len(data.get('signals', []))})"
        )

    return errors


def validate(
    data_path: str | Path = "data/data.json",
    schema_path: str | Path = "schemas/data-schema.json",
    fail_on_warning: bool = False,
) -> bool:
    """
    Run full validation pipeline. Returns True if valid, False otherwise.

    Args:
        data_path: Path to data.json
        schema_path: Path to schema JSON
        fail_on_warning: If True, treat quality warnings as failures
    """
    print(f"Validating {data_path} against {schema_path}...")

    try:
        schema = load_schema(schema_path)
        data = load_data(data_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Could not load files: {e}")
        return False

    # Schema validation
    try:
        json_validate(instance=data, schema=schema)
        print("PASS: Schema validation passed.")
    except jsonschema.exceptions.ValidationError as e:
        print(f"FAIL: Schema validation error: {e.message}")
        print(f"  Path: {'.'.join(str(p) for p in e.absolute_path)}")
        return False

    # Quality gates
    quality_errors = check_quality_gates(data)
    if quality_errors:
        for err in quality_errors:
            print(f"WARN: {err}")
        if fail_on_warning:
            print("FAIL: Quality gates failed (--strict mode).")
            return False
        print("NOTE: Quality warnings found but non-blocking (pass --strict to enforce).")
    else:
        print("PASS: Quality gates passed.")

    print(f"OK: {data['meta']['total_signals']} signals from {len(data['meta']['sources_aggregated'])} sources.")
    return True


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate Community Pulse data.json")
    parser.add_argument("--data", default="data/data.json", help="Path to data.json")
    parser.add_argument("--schema", default="schemas/data-schema.json", help="Path to schema")
    parser.add_argument("--strict", action="store_true", help="Fail on quality warnings")
    args = parser.parse_args()

    success = validate(args.data, args.schema, args.strict)
    sys.exit(0 if success else 1)