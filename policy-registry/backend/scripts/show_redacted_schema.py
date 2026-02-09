#!/usr/bin/env python3
"""
Print the graph schema with credentials redacted, using the same redaction
as the NL-to-Cypher workflow (_redact_schema_for_llm in nl_to_cypher.py).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nl_to_cypher import _redact_schema_for_llm

# policy-registry/backend/scripts -> repo root is ../../..
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DEFAULT_SCHEMA_PATH = os.path.join(_REPO_ROOT, "puppygraph", "aml-schema.json")


def main() -> None:
    p = argparse.ArgumentParser(description="Show schema with credentials redacted (same as LLM workflow).")
    p.add_argument(
        "schema_file",
        nargs="?",
        default=_DEFAULT_SCHEMA_PATH,
        help=f"Path to schema JSON (default: {_DEFAULT_SCHEMA_PATH})",
    )
    p.add_argument("-c", "--compact", action="store_true", help="Output compact JSON (no indent)")
    args = p.parse_args()
    if not os.path.isfile(args.schema_file):
        print(f"Schema file not found: {args.schema_file}", file=sys.stderr)
        sys.exit(1)
    with open(args.schema_file) as f:
        schema = json.load(f)
    redacted = _redact_schema_for_llm(schema)
    indent = None if args.compact else 2
    print(json.dumps(redacted, indent=indent))


if __name__ == "__main__":
    main()
