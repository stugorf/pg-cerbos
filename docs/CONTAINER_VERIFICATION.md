# Container File Verification

## Verification Date
$(date)

## PuppyGraph Container Verification

### ✅ Schema File Mount
- **Mount Point**: `/puppygraph/conf/aml-schema.json`
- **Source**: `./puppygraph/aml-schema.json` (read-only)
- **Status**: ✅ File exists and is accessible

### ✅ File Content Verification
- **Host File**: `puppygraph/aml-schema.json`
- **Container File**: `/puppygraph/conf/aml-schema.json`
- **Status**: ✅ Files match exactly (diff shows no differences)

### ✅ Schema Format Verification
- **mappedTableSource format**: ✅ 8 edges using correct format
- **Old format (fromVertex/toVertex)**: ✅ 0 instances found (correctly removed)
- **JDBC Connection**: ✅ Includes `currentSchema=aml` parameter

### ✅ TO_ACCOUNT Edge Fix Verification
The critical fix is present in the container:
```json
{
  "label": "TO_ACCOUNT",
  "from": "Transaction",
  "to": "Account",
  "mappedTableSource": {
    "metaFields": {
      "id": "txn_id",
      "from": "txn_id",
      "to": "to_account_id"  // ✅ Fixed - was "account_id" (non-existent)
    }
  }
}
```

## PostgreSQL Container Verification

### ✅ Database Schema
- **Database**: `demo_data`
- **Schema**: `aml`
- **Tables**: All 7 tables exist with proper structure
- **Columns**: All referenced columns exist in their respective tables

### ✅ Transaction Table Columns
Verified columns exist:
- ✅ `txn_id` (primary key)
- ✅ `from_account_id` (foreign key to account)
- ✅ `to_account_id` (foreign key to account)
- ❌ `account_id` (does NOT exist - correctly not referenced)

## Container Status

### Running Containers
- ✅ `pg-cerbos-puppygraph` - PuppyGraph service
- ✅ `pg-cerbos-postgres14` - PostgreSQL database

## Next Steps

### Restart PuppyGraph to Load Updated Schema
Since the schema file is mounted as read-only, PuppyGraph should pick up changes on restart:

```bash
docker compose restart puppygraph
```

### Verify Schema Loaded
After restart, check PuppyGraph logs:
```bash
docker logs pg-cerbos-puppygraph --tail 50
```

Look for:
- Schema loaded successfully
- Configuration ready
- No validation errors

### Test Validation
1. Access PuppyGraph UI: http://localhost:8081
2. Navigate to Schema section
3. Click "Validate Schema" button
4. Should see success (no error 244)

## Verification Commands

### Check Schema File in Container
```bash
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | jq '.edges[2]'
```

### Verify File Match
```bash
diff <(cat puppygraph/aml-schema.json) <(docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json)
```

### Check Edge Format
```bash
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | grep -c 'mappedTableSource'
# Should return: 8
```

### Check Old Format Removed
```bash
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | grep -c 'fromVertex\|toVertex'
# Should return: 0
```

## Summary

✅ **All containers have the updated files**
- Schema file is correctly mounted and accessible
- File content matches between host and container
- All fixes are present (TO_ACCOUNT edge fix, mappedTableSource format)
- PostgreSQL schema matches PuppyGraph schema references
- Ready for PuppyGraph restart to load updated schema
