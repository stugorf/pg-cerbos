# PostgreSQL Search Path Fix for PuppyGraph

## Issue Identified
The `aml` schema was not in PostgreSQL's default `search_path`, which could cause PuppyGraph's metadata queries to fail when trying to access tables in the `aml` schema.

## Fixes Applied

### 1. User-Level Search Path
Set the search_path for the `postgres` user:
```sql
ALTER USER postgres SET search_path = aml, public;
```

This ensures that when PuppyGraph connects as the `postgres` user, it will automatically search in the `aml` schema first.

### 2. JDBC Connection Parameter
Added `currentSchema=aml` to the JDBC connection string:
```
jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml
```

This explicitly tells the PostgreSQL JDBC driver to set the current schema to `aml` for all connections.

## Testing
After applying these fixes, PuppyGraph should be able to:
1. Access table metadata via `information_schema` queries
2. Resolve table names without explicit schema qualification
3. Execute queries against tables in the `aml` schema

## Next Steps
1. Test a simple vertex query: `MATCH (c:Customer) RETURN c LIMIT 1`
2. Test an edge query: `MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1`
3. Monitor PuppyGraph logs for any remaining metadata access errors
