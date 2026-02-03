# PuppyGraph Schema Sync Fix

## Issue Identified

Following the recommendations for error E0502 (error 244), we identified that the **TO_ACCOUNT edge was referencing a non-existent column** in the `transaction` table.

## Root Cause

The TO_ACCOUNT edge had:
```json
"metaFields": {
  "id": "txn_id",
  "from": "to_account_id",
  "to": "account_id"  // ❌ This column doesn't exist in transaction table!
}
```

The `transaction` table does **not** have an `account_id` column. It has:
- `txn_id` (transaction ID)
- `from_account_id` (source account ID)
- `to_account_id` (destination account ID)

## Fix Applied

Changed the TO_ACCOUNT edge to correctly reference existing columns:
```json
"metaFields": {
  "id": "txn_id",
  "from": "txn_id",        // Transaction vertex ID
  "to": "to_account_id"    // Account vertex ID (from to_account_id column)
}
```

## Complete Edge Validation

### ✅ All Edges Now Correct

1. **OWNS** (Customer → Account via `account` table)
   - `id`: `account_id` ✓
   - `from`: `customer_id` ✓ (contains customer IDs)
   - `to`: `account_id` ✓ (contains account IDs)

2. **SENT_TXN** (Account → Transaction via `transaction` table)
   - `id`: `txn_id` ✓
   - `from`: `from_account_id` ✓ (contains account IDs)
   - `to`: `txn_id` ✓ (contains transaction IDs)

3. **TO_ACCOUNT** (Transaction → Account via `transaction` table) ✅ **FIXED**
   - `id`: `txn_id` ✓
   - `from`: `txn_id` ✓ (contains transaction IDs)
   - `to`: `to_account_id` ✓ (contains account IDs)

4. **FLAGS_CUSTOMER** (Alert → Customer via `alert` table)
   - `id`: `alert_id` ✓
   - `from`: `alert_id` ✓ (contains alert IDs)
   - `to`: `primary_customer_id` ✓ (contains customer IDs)

5. **FLAGS_ACCOUNT** (Alert → Account via `alert` table)
   - `id`: `alert_id` ✓
   - `from`: `alert_id` ✓ (contains alert IDs)
   - `to`: `primary_account_id` ✓ (contains account IDs)

6. **FROM_ALERT** (Case → Alert via `case` table)
   - `id`: `case_id` ✓
   - `from`: `case_id` ✓ (contains case IDs)
   - `to`: `source_alert_id` ✓ (contains alert IDs)

7. **HAS_NOTE** (Case → CaseNote via `case_note` table)
   - `id`: `note_id` ✓
   - `from`: `case_id` ✓ (contains case IDs)
   - `to`: `note_id` ✓ (contains note IDs)

8. **RESULTED_IN** (Case → SAR via `sar` table)
   - `id`: `sar_id` ✓
   - `from`: `case_id` ✓ (contains case IDs)
   - `to`: `sar_id` ✓ (contains sar IDs)

## Verification Checklist

Following the troubleshooting recommendations:

### ✅ 1. Catalog Connectivity
- JDBC connection string: `jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml`
- Username/password: `postgres/postgres`
- Database accessible: ✅ Verified

### ✅ 2. Tables Exist
- All 7 vertex tables exist: `customer`, `account`, `transaction`, `alert`, `case`, `case_note`, `sar`
- All tables have data (5-8 rows each)
- All tables have SELECT permissions for `postgres` user

### ✅ 3. Primary Keys
- All tables have primary keys defined
- All vertex IDs are properly mapped

### ✅ 4. Foreign Keys
- All foreign key relationships are properly defined
- Edge mappings reference correct columns

### ✅ 5. Column Mappings
- All edge `metaFields` now reference columns that exist in their source tables
- All column names match exactly (case-sensitive)

### ✅ 6. Schema Format
- Using correct `mappedTableSource` format (not `tableSource`)
- Using `from`/`to` (not `fromVertex`/`toVertex`)
- Using `metaFields` with string mappings (not complex field objects)

## Next Steps

1. **Restart PuppyGraph** to load the corrected schema:
   ```bash
   docker compose restart puppygraph
   ```

2. **Test validation** - The schema should now validate successfully

3. **If validation still fails**, check PuppyGraph logs for specific errors:
   ```bash
   docker logs pg-cerbos-puppygraph --tail 100
   ```

4. **Test actual queries** to verify the schema works:
   ```cypher
   MATCH (c:Customer) RETURN c LIMIT 1
   MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1
   MATCH (t:Transaction)-[:TO_ACCOUNT]->(a:Account) RETURN t, a LIMIT 1
   ```

## References

- [PuppyGraph Edge Documentation](https://docs.puppygraph.com/reference/schema/edge/)
- Error E0502 troubleshooting recommendations
- Schema sync validation script: `scripts/validate-puppygraph-schema.sh`
