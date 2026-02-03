# Search Path Resolution for PuppyGraph

## Problem
PuppyGraph's parallelized metadata retrieval (introduced in version 0.109+) queries PostgreSQL's `information_schema` and `pg_catalog` to get table and column metadata. If the `aml` schema is not in PostgreSQL's `search_path`, these queries can return empty results, causing the error:

```
can not access data source table attributes:map[]
```

## Solution

We've implemented a **three-layer approach** to ensure the `aml` schema is always accessible:

### 1. User-Level Search Path (Persistent)
**File**: `postgres/init/00-create-databases.sql`

Added to the database initialization script:
```sql
ALTER USER postgres SET search_path = aml, public;
```

This ensures that whenever the `postgres` user connects, the `search_path` will automatically include `aml` first, then `public`.

**Benefits**:
- Persistent across database restarts
- Applies to all connections made by the `postgres` user
- No need to modify connection strings

### 2. JDBC Connection Parameter (Explicit)
**File**: `puppygraph/aml-schema.json`

Added `currentSchema=aml` to the JDBC connection string:
```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml"
```

**Benefits**:
- Explicitly sets the current schema for JDBC connections
- Works even if user-level search_path is not set
- Ensures PuppyGraph always uses the correct schema

### 3. Database-Level Default (Optional)
If needed, you can also set a database-level default:
```sql
ALTER DATABASE demo_data SET search_path = aml, public;
```

This is less commonly needed since user-level settings take precedence.

## Verification

### Check User-Level Search Path
```sql
SELECT rolname, rolconfig FROM pg_roles WHERE rolname = 'postgres';
-- Should show: {"search_path=aml, public"}
```

### Check Current Session Search Path
```sql
SHOW search_path;
-- Should show: aml, public
```

### Check JDBC Connection String
```bash
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | jq '.catalogs[0].jdbc.jdbcUri'
-- Should include: ?currentSchema=aml
```

### Test Metadata Access
```sql
-- These queries should work without schema qualification:
SELECT table_name FROM information_schema.tables WHERE table_name = 'customer';
SELECT column_name FROM information_schema.columns WHERE table_name = 'customer';
```

## Why This Matters

PuppyGraph's metadata queries use `information_schema` views which respect the `search_path`. When PuppyGraph queries:
- `information_schema.tables`
- `information_schema.columns`
- `pg_catalog.pg_class`
- `pg_catalog.pg_attribute`

If `aml` is not in the `search_path`, these queries may:
1. Return empty results (no tables found)
2. Only find tables in the `public` schema
3. Cause PuppyGraph to fail with "can not access data source table attributes"

## Testing

After applying these fixes:

1. **Restart PuppyGraph** to pick up the new JDBC connection string:
   ```bash
   docker restart pg-cerbos-puppygraph
   ```

2. **Test a simple vertex query**:
   ```cypher
   MATCH (c:Customer) RETURN c LIMIT 1
   ```

3. **Test an edge query**:
   ```cypher
   MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1
   ```

4. **Check PuppyGraph logs** for any remaining metadata errors:
   ```bash
   docker logs pg-cerbos-puppygraph | grep -i "error\|exception\|metadata"
   ```

## Persistence

The fix is now **persistent** because:
- ✅ User-level `search_path` is set in the init script (`00-create-databases.sql`)
- ✅ JDBC connection string includes `currentSchema=aml` in the schema file
- ✅ Both will be applied automatically when the database is initialized

## Next Steps

If issues persist after applying these fixes:
1. Verify PuppyGraph has restarted and loaded the new schema
2. Check PuppyGraph logs for specific error messages
3. Test with a simpler schema (e.g., `aml-schema-minimal.json`) to isolate the issue
4. Consider testing with PuppyGraph 0.108 (before parallelization changes) if the issue is version-specific
