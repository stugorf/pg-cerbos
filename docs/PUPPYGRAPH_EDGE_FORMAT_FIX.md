# PuppyGraph Edge Format Fix

## Issue Identified

The schema was using an **incorrect edge format** that doesn't match the [official PuppyGraph Edge documentation](https://docs.puppygraph.com/reference/schema/edge/).

## Changes Made

### ❌ Old Format (Incorrect)
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
        "type": "String",
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

### ✅ New Format (Correct - Per Documentation)
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

## Key Changes

1. **`fromVertex` → `from`**: Changed to match documentation
2. **`toVertex` → `to`**: Changed to match documentation
3. **`tableSource` → `mappedTableSource`**: Changed to match documentation
4. **Complex field objects → Simple string mappings**: Replaced `id`/`fromId`/`toId` field objects with `metaFields` string mappings

## Edge ID Uniqueness Consideration

According to the documentation, **edge IDs must be string and unique**. We have some edges that share the same ID field:

- `SENT_TXN` and `TO_ACCOUNT` both use `txn_id` from `transaction` table
- `FLAGS_CUSTOMER` and `FLAGS_ACCOUNT` both use `alert_id` from `alert` table

**Note**: Since these are different edge labels, PuppyGraph may handle them as separate edge types with IDs unique within each type. However, if validation still fails, we may need to create dedicated edge views or tables with unique composite IDs.

## All Edges Converted

1. ✅ **OWNS**: Customer → Account (via `account` table)
2. ✅ **SENT_TXN**: Account → Transaction (via `transaction` table)
3. ✅ **TO_ACCOUNT**: Transaction → Account (via `transaction` table)
4. ✅ **FLAGS_CUSTOMER**: Alert → Customer (via `alert` table)
5. ✅ **FLAGS_ACCOUNT**: Alert → Account (via `alert` table)
6. ✅ **FROM_ALERT**: Case → Alert (via `case` table)
7. ✅ **HAS_NOTE**: Case → CaseNote (via `case_note` table)
8. ✅ **RESULTED_IN**: Case → SAR (via `sar` table)

## Next Steps

1. **Restart PuppyGraph** to load the corrected schema format
2. **Test validation** - The schema should now match the official format
3. **If validation still fails**, check edge ID uniqueness requirements
4. **Test actual queries** to verify the schema works

## References

- [PuppyGraph Edge Documentation](https://docs.puppygraph.com/reference/schema/edge/)
- Official format requires `mappedTableSource` with `metaFields` as simple string mappings
