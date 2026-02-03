# Duplicate Aliases Fix

## Issue

PuppyGraph 0.112 validation was rejecting the schema due to duplicate aliases in edge definitions:

- `OWNS` edge: `id` and `toId` both used alias `account_id`
- `TO_ACCOUNT` edge: `id` and `toId` both used alias `to_account_id`
- `HAS_NOTE` edge: `id` and `toId` both used alias `note_id`
- `RESULTED_IN` edge: `id` and `toId` both used alias `sar_id`

## Solution

Made all edge field aliases unique by adding descriptive prefixes to `toId` aliases:

### Changes Made

1. **OWNS edge**:
   - `toId` alias: `account_id` → `owns_to_account_id`

2. **TO_ACCOUNT edge**:
   - `toId` alias: `to_account_id` → `to_account_to_id`

3. **HAS_NOTE edge**:
   - `toId` alias: `note_id` → `has_note_to_id`

4. **RESULTED_IN edge**:
   - `toId` alias: `sar_id` → `resulted_in_to_id`

## Additional Fix: Data Type

Also fixed data type mismatch:
- **Transaction.amount**: Changed from `Double` to `Decimal` to match PostgreSQL `DECIMAL(15,2)`

## Result

✅ Schema now uploads successfully via API
✅ Schema validation passes
✅ Schema is activated for query execution
✅ Queries should now work via Bolt protocol

## Verification

After uploading the schema:

```bash
# Upload schema
curl -X POST -u puppygraph:puppygraph123 \
  -H "Content-Type: application/json" \
  -d @puppygraph/aml-schema.json \
  http://localhost:8081/schema

# Expected response:
# {"Status":"OK","Message":"Schema updated and PuppyGraph server restarted"}
```

## Next Steps

1. **Test queries in UI**: Try Cypher queries in PuppyGraph UI
2. **Verify no error 244**: Queries should execute without error 244
3. **Test all edge types**: Verify all 8 edges work correctly
