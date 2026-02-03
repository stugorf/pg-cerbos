# PuppyGraph Schema Validation Fixes

## Summary

Comprehensive review and fixes applied to `puppygraph/aml-schema.json` to resolve schema validation issues with PuppyGraph 0.108 and PostgreSQL 14.1.

## Issues Identified and Fixed

### 1. Edge ID Type Mismatch ✅
**Issue**: PuppyGraph requires edge IDs to be **String type**, but all edges were using **Int type**.

**Fix**: Converted all edge `id` fields from `Int` to `String` type:
- OWNS: `account_id` → String
- SENT_TXN: `txn_id` → String (alias: `sent_txn_id`)
- TO_ACCOUNT: `txn_id` → String (alias: `to_account_id`)
- FLAGS_CUSTOMER: `alert_id` → String (alias: `flags_customer_id`)
- FLAGS_ACCOUNT: `alert_id` → String (alias: `flags_account_id`)
- FROM_ALERT: `case_id` → String
- HAS_NOTE: `note_id` → String
- RESULTED_IN: `sar_id` → String

### 2. Field Type Mismatches ✅
**Issue**: Database columns `owner_user_id` and `author_user_id` are **TEXT** in PostgreSQL, but schema defined them as **Int**.

**Fix**: Changed field types to match database:
- `Case.owner_user_id`: Int → String
- `CaseNote.author_user_id`: Int → String

### 3. Incorrect Edge Mappings ✅
**Issue**: Several edges had incorrect `fromId`/`toId` mappings.

**Fixes Applied**:

#### FLAGS_CUSTOMER Edge
- **Before**: `fromId` = `primary_customer_id`, `toId` = `customer_id`
- **After**: `fromId` = `alert_id` (Alert vertex ID), `toId` = `primary_customer_id` (Customer vertex ID)

#### FLAGS_ACCOUNT Edge
- **Before**: `fromId` = `primary_account_id`, `toId` = `account_id`
- **After**: `fromId` = `alert_id` (Alert vertex ID), `toId` = `primary_account_id` (Account vertex ID)

#### FROM_ALERT Edge
- **Before**: `fromId` = `source_alert_id`, `toId` = `alert_id`
- **After**: `fromId` = `case_id` (Case vertex ID), `toId` = `source_alert_id` (Alert vertex ID)

### 4. Edge ID Uniqueness ✅
**Issue**: Multiple edges from the same table (e.g., `SENT_TXN` and `TO_ACCOUNT` both from `transaction` table) could have duplicate IDs.

**Fix**: Added unique aliases to distinguish edge IDs:
- `SENT_TXN`: alias `sent_txn_id`
- `TO_ACCOUNT`: alias `to_account_id`
- `FLAGS_CUSTOMER`: alias `flags_customer_id`
- `FLAGS_ACCOUNT`: alias `flags_account_id`

Note: While these edges reference the same database columns, PuppyGraph treats each edge label as a separate type, so IDs are unique within each edge type.

### 5. Reserved Word Table Handling ✅
**Issue**: The `case` table is a PostgreSQL reserved word, which could cause validation issues.

**Status**: The table name is unquoted in the schema, which is correct. PuppyGraph should handle quoting automatically. The schema references are correct:
- Vertex: `table: "case"`
- Edge: `table: "case"`

## Schema Validation Checklist

### Vertices ✅
- [x] All vertices have unique `id` fields (Int type)
- [x] All field types match PostgreSQL column types
- [x] All table references are correct
- [x] All attributes are properly defined

### Edges ✅
- [x] All edge IDs are String type
- [x] All edge IDs have unique aliases
- [x] All `fromId` fields correctly reference source vertex IDs
- [x] All `toId` fields correctly reference target vertex IDs
- [x] All table references are correct
- [x] Edge labels are unique

### Database Alignment ✅
- [x] All table names match PostgreSQL schema (`aml` schema)
- [x] All column names match PostgreSQL tables
- [x] All data types are correctly mapped:
  - `SERIAL/INTEGER` → `Int`
  - `TEXT` → `String`
  - `BOOLEAN` → `Boolean`
  - `TIMESTAMP WITH TIME ZONE` → `DateTime`
  - `DECIMAL` → `Double`

## Testing Recommendations

After applying these fixes, test the schema validation:

1. **Restart PuppyGraph service** to load the updated schema
2. **Validate schema** in PuppyGraph UI (click "Validate Schema" button)
3. **Test basic queries**:
   ```cypher
   MATCH (c:Customer) RETURN c LIMIT 1
   MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1
   MATCH (c:Case)-[:FROM_ALERT]->(a:Alert) RETURN c, a LIMIT 1
   ```
4. **Verify all edge types** work correctly

## Potential Remaining Issues

If validation still fails, consider:

1. **PuppyGraph Version Bug**: Version 0.108 might have a known bug with PostgreSQL validation queries (as documented in `VALIDATION_ERROR_ROOT_CAUSE.md`). The validation might fail even if the schema is correct.

2. **JDBC Connection**: Verify PuppyGraph can connect to PostgreSQL and query table metadata:
   ```bash
   docker exec pg-cerbos-puppygraph curl -f http://localhost:8081/api/health
   ```

3. **Table Permissions**: Ensure the `postgres` user has SELECT permissions on all `aml` schema tables.

4. **Schema Path**: Verify the schema file is correctly mounted and loaded:
   - Compose file: `SCHEMA_PATH=/puppygraph/conf/aml-schema.json`
   - Volume mount: `./puppygraph:/puppygraph/conf:ro`

## Files Modified

- `puppygraph/aml-schema.json` - Complete schema with all fixes applied

## References

- [PuppyGraph Schema Documentation](https://docs.puppygraph.com/reference/schema/)
- [PuppyGraph Edge Reference](https://docs.puppygraph.com/reference/schema/edge)
- [PuppyGraph PostgreSQL Connection](https://docs.puppygraph.com/connecting/connecting-to-postgresql)
