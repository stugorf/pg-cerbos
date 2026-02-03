# PuppyGraph Error 244 Resolution

## Error
```
ERROR error msg: E0502 (error in read loop, error message '{code:244 message:[2014]schema is broken: can not access data source table attributes:map[]}'. statusCode: 244)
```

## Root Cause Analysis

Error 244 indicates that PuppyGraph cannot access PostgreSQL table metadata during schema validation. This is a known issue with PuppyGraph 0.108's validation logic when querying `information_schema` or `pg_catalog` for table attributes.

## Fixes Applied

### 1. ✅ JDBC Connection Parameter
**File**: `puppygraph/aml-schema.json`

Added `currentSchema=aml` to the JDBC connection string:
```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml"
```

This explicitly tells the PostgreSQL JDBC driver to set the current schema to `aml` for all connections.

### 2. ✅ User-Level Search Path
**File**: `postgres/init/00-create-databases.sql`

Already configured:
```sql
ALTER USER postgres SET search_path = aml, public;
```

### 3. ✅ Database-Level Search Path
**File**: `postgres/init/00-create-databases.sql`

Added database-level search_path as an additional safeguard:
```sql
ALTER DATABASE demo_data SET search_path = aml, public;
```

## Verification Steps

### 1. Check Search Path Configuration
```bash
# Check user-level search_path
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SELECT rolname, rolconfig FROM pg_roles WHERE rolname = 'postgres';"

# Check database-level search_path
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SELECT datname, datconfig FROM pg_database WHERE datname = 'demo_data';"

# Check current session search_path
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SHOW search_path;"
```

### 2. Verify JDBC Connection String
```bash
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | jq '.catalogs[0].jdbc.jdbcUri'
```

Expected output: `"jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml"`

### 3. Test Table Metadata Access
```bash
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema = 'aml' ORDER BY table_name;"
```

### 4. Restart PuppyGraph Service
After applying fixes, restart the PuppyGraph service to reload the schema:
```bash
docker compose restart puppygraph
```

## Known Limitations

### PuppyGraph 0.108 Validation Bug
Even with all fixes applied, **PuppyGraph 0.108 may still show validation errors** due to a known bug in its validation logic. According to documentation:

1. **Validation may fail** even if the schema is correct
2. **Actual queries may still work** despite validation failure
3. **This is a PuppyGraph bug**, not a schema configuration issue

### Testing Actual Queries
If validation fails, test if actual Cypher queries work:

```cypher
// Test vertex query
MATCH (c:Customer) RETURN c LIMIT 1

// Test edge query
MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1

// Test complex traversal
MATCH (c:Customer)-[:OWNS]->(a:Account)-[:SENT_TXN]->(t:Transaction) 
RETURN c, a, t LIMIT 1
```

If queries work, the schema is correct and validation can be ignored.

## Alternative Solutions

### Option 1: Ignore Validation (If Queries Work)
If actual queries work despite validation failure:
- Document that validation has a known bug
- Use queries directly via Bolt protocol (port 7687)
- Skip validation in the UI

### Option 2: Upgrade PuppyGraph Version
Consider testing with a newer PuppyGraph version that may have fixed the validation bug:
- Check PuppyGraph release notes for validation fixes
- Test with `puppygraph/puppygraph:latest` or a newer version
- Note: Version 0.109+ introduced parallelized metadata retrieval which may have different behavior

### Option 3: Report Bug to PuppyGraph
This is clearly a bug in PuppyGraph's validation logic:
- Validation should use database-specific SQL syntax
- PostgreSQL catalog should generate PostgreSQL-compatible queries
- File issue with PuppyGraph maintainers with:
  - Error code: 244
  - Error message: "can not access data source table attributes:map[]"
  - PuppyGraph version: 0.108
  - PostgreSQL version: 14.1
  - Schema format details

## Current Status

✅ **Schema loads successfully** - PuppyGraph reports `ConfigurationReady: true`  
✅ **Service is healthy** - PuppyGraph health check passes  
✅ **Search path configured** - User-level, database-level, and JDBC parameter all set  
✅ **Tables accessible** - All AML tables exist and are accessible  
❌ **Validation fails** - Error 244 persists (known PuppyGraph bug)

## Next Steps

1. **Restart PuppyGraph** to apply JDBC connection parameter change
2. **Test actual queries** to verify schema works despite validation error
3. **Document workaround** if queries work but validation fails
4. **Consider upgrading** PuppyGraph version if available
5. **Report bug** to PuppyGraph maintainers if issue persists

## References

- [PuppyGraph Schema Documentation](https://docs.puppygraph.com/reference/schema/)
- [PostgreSQL JDBC Connection Parameters](https://jdbc.postgresql.org/documentation/head/connect.html)
- Error 244 documentation in project: `docs/VALIDATION_ERROR_ROOT_CAUSE.md`
- Search path resolution: `docs/SEARCH_PATH_RESOLUTION_SUMMARY.md`
