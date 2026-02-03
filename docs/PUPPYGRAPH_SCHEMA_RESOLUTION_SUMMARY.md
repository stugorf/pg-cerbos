# PuppyGraph Schema Resolution Summary

## Issue
PuppyGraph schema validation fails with error: **"can not access data source table attributes:map[]"** when edges are defined in the schema.

## Root Cause Analysis

### What Works
- ✅ Vertices work correctly - queries return results when only vertices are defined
- ✅ JDBC connectivity is working - PuppyGraph can connect to PostgreSQL 14.1
- ✅ Permissions are correct - all tables and views have SELECT grants
- ✅ Schema structure matches PuppyGraph documentation format

### What Fails
- ❌ Any edge definition causes the "can not access data source table attributes" error
- ❌ Error occurs regardless of:
  - Edge table format (views vs physical tables)
  - Edge ID type (integer vs string)
  - Schema format (`tableSource` vs `mappedTableSource`)
  - Field naming (`fromVertex`/`toVertex` vs `from`/`to`)

## Attempted Solutions

1. **Added edge attributes** - All edges now have proper attribute definitions
2. **Created dedicated edge views** - 8 edge views with explicit `id`, `from_id`, `to_id` columns
3. **Created physical edge tables** - Converted views to physical tables
4. **Converted to `mappedTableSource` format** - Changed from `tableSource` to `mappedTableSource` with `metaFields` as per [Edge documentation](https://docs.puppygraph.com/reference/schema/edge/)
5. **Updated field names** - Changed `fromVertex`/`toVertex` to `from`/`to` as per documentation
6. **Updated attribute format** - Changed from `field/alias/type` to `name/type` format
7. **String ID conversion** - Created edge tables with string IDs (as documentation requires)
8. **Verified permissions** - All tables have proper SELECT grants

## Current Schema Format (Parser Branch - Working Format)

### Vertices (Working)
```json
{
  "label": "Customer",
  "oneToOne": {
    "tableSource": {
      "catalog": "aml_postgres",
      "schema": "aml",
      "table": "customer"
    },
    "id": {
      "fields": [{"type": "Int", "field": "customer_id", "alias": "customer_id"}]
    },
    "attributes": [...]
  }
}
```

### Edges (Parser Branch Format - Should Work)
```json
{
  "label": "OWNS",
  "fromVertex": "Customer",
  "toVertex": "Account",
  "tableSource": {
    "catalog": "aml_postgres",
    "schema": "aml",
    "table": "account"
  },
  "id": {
    "fields": [{"type": "Int", "field": "account_id", "alias": "account_id"}]
  },
  "fromId": {
    "fields": [{"type": "Int", "field": "customer_id", "alias": "customer_id"}]
  },
  "toId": {
    "fields": [{"type": "Int", "field": "account_id", "alias": "account_id"}]
  }
}
```

**Key Differences from Documentation:**
- Uses `tableSource` (not `mappedTableSource`)
- Uses `fromVertex`/`toVertex` (not `from`/`to`)
- Uses complex `id`/`fromId`/`toId` field objects (not `metaFields` with simple strings)
- Edges point to **vertex tables** (like `account`), not dedicated edge tables
- No `attributes` defined on edges (null)

## Hypothesis

The error "can not access data source table attributes:map[]" suggests PuppyGraph is:
1. Successfully connecting to PostgreSQL via JDBC
2. Attempting to query table metadata (columns, types, constraints)
3. Getting an empty map/result when querying edge table metadata

This could indicate:
- **PuppyGraph version compatibility issue** - Version 0.111 might have a bug with PostgreSQL 14.1 edge table metadata queries
- **JDBC driver issue** - The PostgreSQL JDBC driver might not be returning metadata in the format PuppyGraph expects
- **Schema format mismatch** - There might be a difference between the API reference format (`mappedTableSource`) and the JSON upload format (`tableSource` with `oneToOne`)

## Parser Branch Analysis

The `parser` branch contains a working schema format that uses:
- `tableSource` format (not `mappedTableSource` from API docs)
- Edges pointing directly to vertex tables (e.g., `account` table for `OWNS` edge)
- No `attributes` on edges
- `fromVertex`/`toVertex` field names

**Current Status:** Schema has been restored to match parser branch format, but error persists. This suggests:
- The schema format is correct (matches working branch)
- The issue may be environmental (PuppyGraph version, PostgreSQL state, or data differences)
- Or the error occurs in a different context than the parser branch

## Next Steps

1. **Compare Full Environment** - Check if parser branch uses different:
   - PuppyGraph image version
   - PostgreSQL data state
   - Environment variables
   - Docker compose configuration

2. **Test on Parser Branch Directly** - Check out parser branch and verify it works in current environment

3. **Check PuppyGraph Backend Logs** - Look for more detailed error messages in backend logs

4. **Verify Data State** - Ensure PostgreSQL data matches parser branch state

## References

- [PuppyGraph Edge Documentation](https://docs.puppygraph.com/reference/schema/edge/)
- [PuppyGraph Vertex Documentation](https://docs.puppygraph.com/reference/schema/vertex/)
- [PuppyGraph PostgreSQL Getting Started](https://docs.puppygraph.com/getting-started/querying-postgresql-data-as-a-graph/)
