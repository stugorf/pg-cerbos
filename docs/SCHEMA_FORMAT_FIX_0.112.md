# Schema Format Fix for PuppyGraph 0.112

## Issue

PuppyGraph 0.112 was rejecting the schema with errors:
- `meaningless key 'mappedTableSource from to'`
- `fromVertex: missing name`
- `toVertex: missing name`
- `tableSource: is required`
- `fromId: is required`
- `toId: is required`

## Root Cause

**PuppyGraph 0.112 expects the OLD edge format**, not the `mappedTableSource` format shown in the API documentation. There's a discrepancy between:
- **API Documentation Format**: Uses `mappedTableSource` with `metaFields` (simple string mappings)
- **JSON File Format (0.112)**: Requires `tableSource` with `fromVertex`/`toVertex` and complex `id`/`fromId`/`toId` field objects

## Solution

Converted all edges from `mappedTableSource` format to `tableSource` format:

### ❌ Old Format (Rejected by 0.112)
```json
{
  "label": "OWNS",
  "from": "Customer",
  "to": "Account",
  "mappedTableSource": {
    "catalog": "aml_postgres",
    "schema": "aml",
    "table": "account",
    "metaFields": {
      "id": "account_id",
      "from": "customer_id",
      "to": "account_id"
    }
  },
  "attributes": []
}
```

### ✅ New Format (Accepted by 0.112)
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
    "fields": [
      {
        "type": "Int",
        "field": "account_id",
        "alias": "account_id"
      }
    ]
  },
  "fromId": {
    "fields": [
      {
        "type": "Int",
        "field": "customer_id",
        "alias": "customer_id"
      }
    ]
  },
  "toId": {
    "fields": [
      {
        "type": "Int",
        "field": "account_id",
        "alias": "account_id"
      }
    ]
  }
}
```

## Key Changes

1. **`from`/`to` → `fromVertex`/`toVertex`**: Changed to match 0.112 requirements
2. **`mappedTableSource` → `tableSource`**: Changed to match 0.112 requirements
3. **`metaFields` → `id`/`fromId`/`toId` field objects**: Replaced simple string mappings with complex field objects
4. **Removed `attributes` array**: Not required for edges in this format
5. **Added unique aliases**: For edges sharing the same source table (e.g., `SENT_TXN` and `TO_ACCOUNT` both use `transaction` table)

## Edge ID Uniqueness

To ensure edge IDs are unique when multiple edges share the same source table, unique aliases were added:
- `SENT_TXN`: Uses alias `sent_txn_id` for edge ID
- `TO_ACCOUNT`: Uses alias `to_account_id` for edge ID
- `FLAGS_CUSTOMER`: Uses alias `flags_customer_id` for edge ID
- `FLAGS_ACCOUNT`: Uses alias `flags_account_id` for edge ID
- `FROM_ALERT`: Uses alias `from_alert_id` for edge ID

## All Edges Converted

1. ✅ `OWNS` - Customer → Account
2. ✅ `SENT_TXN` - Account → Transaction
3. ✅ `TO_ACCOUNT` - Transaction → Account
4. ✅ `FLAGS_CUSTOMER` - Alert → Customer
5. ✅ `FLAGS_ACCOUNT` - Alert → Account
6. ✅ `FROM_ALERT` - Case → Alert
7. ✅ `HAS_NOTE` - Case → CaseNote
8. ✅ `RESULTED_IN` - Case → SAR

## Verification

After this fix, the schema should:
- ✅ Load successfully via `SCHEMA_PATH`
- ✅ Display in the PuppyGraph UI
- ✅ Pass validation
- ✅ Allow queries to execute

## Next Steps

1. Restart PuppyGraph to reload the schema:
   ```bash
   docker compose restart puppygraph
   ```

2. Verify schema appears in UI:
   - Open http://localhost:8081
   - Navigate to Schema page
   - Verify all vertices and edges are displayed

3. Test validation:
   - Click "Validate Schema" in UI
   - Should pass without errors

4. Test queries:
   ```cypher
   MATCH (c:Customer) RETURN c LIMIT 1
   MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1
   ```
