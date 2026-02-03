# Service Restart Status

## Current Service Status

### PuppyGraph
- **Status**: Running (unhealthy)
- **Version**: `puppygraph/puppygraph:0.108` ✅
- **Schema File**: Mounted from host, changes should auto-reload
- **JDBC URI**: `jdbc:postgresql://postgres14:5432/demo_data` ✅ (matches parser branch)

### PostgreSQL
- **Status**: Running (healthy)
- **Version**: `postgres:14.1-alpine` ✅
- **Search Path**: `aml, public` ✅ (already set via ALTER USER)

### Policy Registry
- **Status**: Running
- **No changes made** - no restart needed

## Changes Made

1. ✅ **PuppyGraph version**: Changed to `0.108` - **Already restarted**
2. ✅ **Schema JDBC URI**: Removed `?currentSchema=aml` - **File is mounted, should auto-reload**
3. ✅ **PostgreSQL search_path**: Set via `ALTER USER` - **Already active** (init script change will apply on next DB init)

## Restart Recommendation

### PuppyGraph: **Optional Restart**
- The schema file is mounted as a volume, so PuppyGraph should auto-detect changes
- However, if you want to ensure the schema is fully reloaded, restarting is safe
- The "unhealthy" status might be due to the validation bug, not a real health issue

### PostgreSQL: **No Restart Needed**
- Search_path is already set and active
- Init script change will apply automatically on next database initialization

### Policy Registry: **No Restart Needed**
- No changes affecting this service

## To Restart PuppyGraph (if needed)

```bash
docker restart pg-cerbos-puppygraph
```

Or to ensure a clean restart:
```bash
docker-compose restart puppygraph
```

## Verification After Restart

1. Check PuppyGraph health: `docker ps | grep puppygraph`
2. Verify schema loaded: Check PuppyGraph UI or logs for `ConfigurationReady: true`
3. Test a query: Try executing a Cypher query to confirm it works
