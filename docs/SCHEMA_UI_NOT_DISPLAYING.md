# Schema Not Displaying in UI - Issue Analysis

## Problem
The AML schema is configured to load via `SCHEMA_PATH` environment variable, but it doesn't appear in the PuppyGraph UI.

## Current Status

### ✅ Configuration Correct
- `SCHEMA_PATH=/puppygraph/conf/aml-schema.json` is set
- Schema file exists and is readable
- Volume mount is correct: `./puppygraph:/puppygraph/conf:ro`
- Logs show: "Starting gremlin server, with initial schema"

### ❌ Schema Validation Failing
- **Error**: `"Install schema error: schema validation failed"`
- **API Response**: `{"Status":"Error","Message":"unable to decode schema"}`
- **HTTP Status**: 400 Bad Request when trying to POST schema

## Root Cause

PuppyGraph 0.112 is **rejecting the schema during validation**, which prevents it from:
1. Loading successfully at startup
2. Being accessible via `/schemajson` endpoint
3. Displaying in the UI

## Error Evidence

```bash
# From logs:
[Frontend] [2026-02-03 22:03:51] INFO  Install schema error: schema validation failed
[GIN] 2026/02/03 - 22:03:51 | 400 |  171.583291ms | POST "/schema"

# From API:
curl http://localhost:8081/schemajson
{"Status":"Error","Message":"unable to decode schema"}
```

## Schema Format

Current schema uses:
- ✅ `mappedTableSource` format (per documentation)
- ✅ `metaFields` with string mappings
- ✅ `from`/`to` (not `fromVertex`/`toVertex`)
- ✅ Valid JSON structure

## Possible Causes

1. **PuppyGraph 0.112 Validation Bug**: Version 0.112 might have stricter validation or a bug
2. **Schema Format Mismatch**: The `mappedTableSource` format might not be compatible with file-based loading (`SCHEMA_PATH`) vs API upload
3. **Edge ID Uniqueness**: Edges sharing the same ID field might be causing validation to fail
4. **PostgreSQL Connection**: Schema validation might be trying to connect to PostgreSQL and failing

## Next Steps

### 1. Get Detailed Validation Error
Try uploading the schema manually through the UI to see the specific validation error:
1. Open http://localhost:8081
2. Navigate to Schema page
3. Click "Upload Schema"
4. Select `puppygraph/aml-schema.json`
5. Check the error message displayed

### 2. Check PuppyGraph Logs for Details
```bash
docker logs pg-cerbos-puppygraph 2>&1 | grep -i "validation\|error\|schema" | tail -50
```

### 3. Test with Minimal Schema
Create a minimal schema with just one vertex and one edge to isolate the issue:
```bash
# Test with minimal schema
cat > puppygraph/aml-schema-minimal-test.json << 'EOF'
{
  "catalogs": [
    {
      "name": "aml_postgres",
      "type": "postgresql",
      "jdbc": {
        "username": "postgres",
        "password": "postgres",
        "jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml",
        "driverClass": "org.postgresql.Driver"
      }
    }
  ],
  "graph": {
    "vertices": [
      {
        "label": "Customer",
        "oneToOne": {
          "tableSource": {
            "catalog": "aml_postgres",
            "schema": "aml",
            "table": "customer"
          },
          "id": {
            "fields": [
              {
                "type": "Int",
                "field": "customer_id",
                "alias": "customer_id"
              }
            ]
          },
          "attributes": []
        }
      }
    ],
    "edges": []
  }
}
EOF
```

Then test if this minimal schema loads:
```bash
# Update SCHEMA_PATH temporarily
docker compose stop puppygraph
# Edit compose.yml to point to minimal schema
docker compose up -d puppygraph
```

### 4. Consider Version Rollback
If validation is failing due to a 0.112 bug, consider:
- Testing with 0.110 (validation enhancements)
- Testing with 0.105 (before parallelization changes)
- Testing with 0.108 (previous working version)

## Workaround

If schema validation continues to fail, you may need to:
1. **Upload via UI**: Even with `SCHEMA_PATH` set, manually upload through the Web UI
2. **Use API Upload**: Try uploading via the `/schema` API endpoint with detailed error logging
3. **Simplify Schema**: Remove edges temporarily to see if vertices load successfully

## Verification Commands

```bash
# Check if schema is loaded
curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq .

# Check validation errors
docker logs pg-cerbos-puppygraph 2>&1 | grep -i "validation\|error" | tail -20

# Test schema upload via API
curl -X POST -u puppygraph:puppygraph123 \
  -H "Content-Type: application/json" \
  -d @puppygraph/aml-schema.json \
  http://localhost:8081/schema
```
