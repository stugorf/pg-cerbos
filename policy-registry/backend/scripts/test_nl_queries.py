#!/usr/bin/env python3
"""
Run sample complex NL queries through nl_to_cypher (with schema from file).
Use for monitoring LLM/rules output and validating generated Cypher.
Set OPENAI_API_KEY to test LLM path; otherwise uses rule-based only.
"""
import json
import os
import sys

# Run from backend dir so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nl_to_cypher import nl_to_cypher, get_vertex_labels, get_edges_by_label

# From policy-registry/backend/scripts -> repo root is ../../..
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCHEMA_PATH = os.path.join(_REPO_ROOT, "puppygraph", "aml-schema.json")


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


COMPLEX_QUERIES = [
    "Show me all customers",
    "Customers who own accounts that sent transactions over 50000",
    "Find accounts that received transactions",
    "List alerts that flag customers",
    "Show cases that have notes",
    "Transactions over 100000",
    "Top 10 customers by risk",
    "How many customers own accounts?",
]

# Analyst-style queries (AML workflows: screening, monitoring, alerts, cases)
ANALYST_QUERIES = [
    "Show me all customers",
    "Transactions over 50000",
    "Transactions over 100000",
    "Customers who own accounts that sent transactions over 50000",
    "Find accounts that received transactions",
    "List alerts that flag customers",
    "List alerts that flag accounts",
    "Show cases that have notes",
    "Show me all alerts",
    "Show me all cases",
    "Cases that resulted in SAR",
    "Top 10 customers by risk",
    "Show me the top 10 customers by risk and order in decreasing order, please.",
]


def main():
    import argparse
    p = argparse.ArgumentParser(description="Run sample NL queries through nl_to_cypher.")
    p.add_argument("--analyst", action="store_true", help="Run analyst-style AML queries only")
    args = p.parse_args()
    queries = ANALYST_QUERIES if args.analyst else COMPLEX_QUERIES
    if args.analyst:
        print("(Analyst query set)")
    if not os.path.isfile(SCHEMA_PATH):
        print("Schema not found at", SCHEMA_PATH)
        sys.exit(1)
    schema = load_schema()
    vertices = sorted(get_vertex_labels(schema))
    edges = list(get_edges_by_label(schema).keys())
    print("Schema: vertices =", vertices)
    print("Schema: edges =", edges)
    print("OPENAI_API_KEY set:", bool(os.environ.get("OPENAI_API_KEY", "").strip()))
    print("-" * 60)
    for q in queries:
        print("Q:", q)
        result = nl_to_cypher(q, schema)
        print("  source:", result.get("source"))
        print("  valid:", result.get("valid"))
        if result.get("validation_errors"):
            print("  validation_errors:", result["validation_errors"])
        cypher = result.get("cypher", "")
        if cypher:
            print("  cypher:")
            for line in cypher.strip().split("\n"):
                print("   ", line)
        else:
            print("  cypher: (empty)")
        print()


if __name__ == "__main__":
    main()
