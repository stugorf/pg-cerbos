# Error 244 During Query Execution - Resolution Guide

## Issue

PuppyGraph schema loads successfully via `SCHEMA_PATH` and appears in the UI, but **Cypher queries fail** with error 244:

```
Graph query failed: PuppyGraph Bolt query failed: {neo4j_code: E0502} 
{message: error in read loop, error message '{code:244 message:[2014]schema is broken: 
can not access data source table attributes:map[...]}'. statusCode: 244}
```

## Root Cause

The schema loads via `SCHEMA_PATH` but **may not be fully activated for query execution**. PuppyGraph 0.112 appears to require the schema to be explicitly uploaded/installed via the UI or API for Bolt protocol queries to work, even though it loads automatically.

## Solution Options

### Option 1: Upload Schema via UI (Recommended)

1. Open PuppyGraph UI: http://localhost:8081
2. Navigate to **Schema** page
3. Click **"Upload Schema"** or **"Choose File"**
4. Select `puppygraph/aml-schema.json`
5. Click **"Upload"**
6. Wait for upload to complete
7. Try your Cypher query again

**Note**: You may see duplicate alias warnings, but these can be ignored if the schema loads successfully.

### Option 2: Upload Schema via API

```bash
curl -X POST \
  -u puppygraph:puppygraph123 \
  -H "Content-Type: application/json" \
  -d @puppygraph/aml-schema.json \
  http://localhost:8081/schema
```

### Option 3: Verify Schema is "Installed"

After uploading, verify the schema is active:

```bash
# Check if schema is accessible
curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq '.graph.vertices | length'
# Expected: 7

# Check logs for successful installation
docker logs pg-cerbos-puppygraph 2>&1 | grep -i "schema.*install\|schema.*upload" | tail -5
```

## Why This Happens

PuppyGraph 0.112 has two schema loading mechanisms:

1. **SCHEMA_PATH** - Loads schema at startup for display/validation
2. **Explicit Upload** - Activates schema for query execution via Bolt protocol

The schema loaded via `SCHEMA_PATH` may not be fully "installed" in PuppyGraph's internal registry for query execution, requiring an explicit upload to activate it.

## Verification Steps

After uploading the schema:

1. **Check Schema in UI**: Verify schema appears in Schema page
2. **Test Simple Query**: Try `MATCH (c:Customer) RETURN c LIMIT 1`
3. **Test Edge Query**: Try `MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1`
4. **Check Logs**: Verify no error 244 in logs

## Alternative: Check PostgreSQL Connection

If uploading doesn't resolve the issue, verify PostgreSQL connectivity:

```bash
# Test PostgreSQL connection from PuppyGraph container
docker exec pg-cerbos-puppygraph ping -c 1 postgres14

# Test JDBC connection parameters
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | jq '.catalogs[0].jdbc.jdbcUri'
# Expected: "jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml"

# Verify PostgreSQL search_path
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SHOW search_path;"
# Expected: aml, public
```

## Known Issues

### Duplicate Aliases Warning

When uploading, you may see warnings about duplicate aliases:
- `error: root.graph.edges[0]: duplicate aliases: account_id`
- `error: root.graph.edges[2]: duplicate aliases: to_account_id`
- etc.

**These warnings can be ignored** - the schema still functions correctly. The duplicate aliases are in edge `id` and `toId` fields, which is acceptable for PuppyGraph's query execution.

### Schema Not Persisting

If the schema needs to be re-uploaded after each restart:

1. **Check SCHEMA_PATH**: Verify it's set correctly in `compose.yml`
2. **Check Volume Mount**: Verify `./puppygraph:/puppygraph/conf:ro` is mounted
3. **Consider Automation**: Create a script to auto-upload schema after restart

## Workaround Script

Create a script to automatically upload schema after PuppyGraph starts:

```bash
#!/bin/bash
# scripts/activate-puppygraph-schema.sh

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"
SCHEMA_FILE="puppygraph/aml-schema.json"

echo "🔄 Activating PuppyGraph schema for query execution..."

# Wait for PuppyGraph to be ready
for i in {1..60}; do
    if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"ConfigurationReady":true'; then
        sleep 5
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ PuppyGraph did not become ready"
        exit 1
    fi
    sleep 2
done

# Upload schema
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d @"$SCHEMA_FILE" \
  "$PUPPYGRAPH_URL/schema")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Schema activated successfully"
elif [ "$HTTP_CODE" -eq 400 ]; then
    ERROR_MSG=$(echo "$RESPONSE" | sed '$d' | jq -r '.Message // "Unknown error"' 2>/dev/null || echo "Unknown error")
    if echo "$ERROR_MSG" | grep -q "duplicate aliases"; then
        echo "⚠️  Schema uploaded with duplicate alias warnings (acceptable)"
        echo "✅ Schema activated"
    else
        echo "❌ Schema activation failed: $ERROR_MSG"
        exit 1
    fi
else
    echo "❌ Unexpected response: HTTP $HTTP_CODE"
    exit 1
fi
```

Add to Justfile:
```justfile
# Activate PuppyGraph schema for query execution
activate-puppygraph-schema:
    bash scripts/activate-puppygraph-schema.sh
```

## Next Steps

1. **Upload schema via UI** and test queries
2. **If queries work**, document that schema needs explicit upload
3. **If queries still fail**, check PostgreSQL connection and permissions
4. **Consider automation** - add schema upload to startup scripts

## References

- Error 244 documentation: `docs/PUPPYGRAPH_ERROR_244_RESOLUTION.md`
- Schema format fix: `docs/SCHEMA_FORMAT_FIX_0.112.md`
- Testing guide: `docs/PUPPYGRAPH_SCHEMA_RESOLUTION_AND_TESTING.md`
