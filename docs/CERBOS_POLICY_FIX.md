# Cerbos Policy Syntax Fix

## Issue Identified

The Cerbos policies were using incorrect syntax for accessing resource attributes in condition expressions.

## Problem

The policies were using:
```yaml
condition:
  match:
    expr: request.method == "POST"
```

But Cerbos uses a different syntax for accessing attributes.

## Solution

In Cerbos, resource attributes are accessed via `R.attr.*` and principal attributes via `P.attr.*`.

### Corrected Syntax

```yaml
condition:
  match:
    expr: R.attr.method == "POST" && R.attr.path.startsWith("/v1/statement")
```

## Changes Made

### Files Updated:
1. `cerbos/policies/resource_policies/postgres.yaml`
2. `cerbos/policies/resource_policies/iceberg.yaml`

### Changes:
- `request.method` → `R.attr.method`
- `request.path` → `R.attr.path`
- `request.body` → `R.attr.body`

## Cerbos Expression Syntax

In Cerbos condition expressions:
- `R` = Resource
- `R.attr.*` = Resource attributes (passed in the resource.attr object)
- `P` = Principal
- `P.attr.*` = Principal attributes (passed in the principal.attr object)

## Verification

After fixing, policies should validate correctly. Test with:

```bash
# If Cerbos CLI is installed
cerbos compile cerbos/policies

# Or via Docker
docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest compile /policies
```

## Related Files

The adapter (`cerbos-adapter/adapter.py`) correctly passes attributes as:
```python
"resource": {
    "kind": resource_kind,
    "attr": {
        "method": method,
        "path": path,
        "body": query_body,
        "catalog": resource_kind
    }
}
```

So the policies can access them via `R.attr.method`, `R.attr.path`, etc.
