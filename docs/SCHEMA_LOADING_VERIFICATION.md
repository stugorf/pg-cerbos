# Schema Loading Verification

## Configuration Summary

The AML schema is configured to load automatically at PuppyGraph startup via the `SCHEMA_PATH` environment variable.

### Compose Configuration

```yaml
puppygraph:
  environment:
    - SCHEMA_PATH=/puppygraph/conf/aml-schema.json
  volumes:
    - ./puppygraph:/puppygraph/conf:ro
```

### Verification Steps

#### 1. Environment Variable Check
```bash
docker exec pg-cerbos-puppygraph env | grep SCHEMA_PATH
```
**Expected**: `SCHEMA_PATH=/puppygraph/conf/aml-schema.json`

#### 2. Schema File Existence
```bash
docker exec pg-cerbos-puppygraph test -f /puppygraph/conf/aml-schema.json && echo "✅ Schema file exists"
```
**Expected**: `✅ Schema file exists`

#### 3. Schema File Readability
```bash
docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | jq -r '.graph.vertices | length'
```
**Expected**: `7` (number of vertex types)

#### 4. Startup Logs
```bash
docker logs pg-cerbos-puppygraph 2>&1 | grep -i "SCHEMA_PATH\|initial schema"
```
**Expected**: 
- `SCHEMA_PATH=/puppygraph/conf/aml-schema.json`
- `Starting gremlin server, with initial schema.`

#### 5. Configuration Ready Status
```bash
docker logs pg-cerbos-puppygraph 2>&1 | grep "ConfigurationReady"
```
**Expected**: `"ConfigurationReady":true`

#### 6. Schema API Endpoint
```bash
curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq -r '.graph.vertices[0].label'
```
**Expected**: `Customer` (or first vertex label from schema)

## How PuppyGraph Loads Schema

1. **Startup**: PuppyGraph reads `SCHEMA_PATH` environment variable
2. **Initialization**: During "Starting gremlin server, with initial schema" phase
3. **Loading**: Schema JSON is parsed and validated
4. **Ready**: `ConfigurationReady: true` indicates successful load
5. **Accessible**: Schema available via `/schemajson` API endpoint and UI

## Troubleshooting

### Schema Not Loading

If schema doesn't appear in UI or queries fail:

1. **Check file path**:
   ```bash
   docker exec pg-cerbos-puppygraph ls -la /puppygraph/conf/
   ```

2. **Check environment variable**:
   ```bash
   docker exec pg-cerbos-puppygraph env | grep SCHEMA_PATH
   ```

3. **Check logs for errors**:
   ```bash
   docker logs pg-cerbos-puppygraph 2>&1 | grep -i error
   ```

4. **Verify volume mount**:
   ```bash
   docker inspect pg-cerbos-puppygraph | jq '.[0].Mounts[] | select(.Destination == "/puppygraph/conf")'
   ```

5. **Restart service**:
   ```bash
   docker compose restart puppygraph
   ```

### Common Issues

- **File not found**: Check volume mount path in `compose.yml`
- **Permission denied**: Ensure file is readable (should be with `:ro` mount)
- **Invalid JSON**: Validate schema with `jq` before mounting
- **Path mismatch**: Ensure `SCHEMA_PATH` matches actual file location

## Current Status

✅ **Schema Loading Verified**:
- Environment variable set correctly
- Schema file exists and is readable
- Schema loads at startup (evidenced by logs)
- Configuration ready status: `true`
- Schema accessible via API

## Quick Verification Command

Run this single command to verify all aspects:

```bash
echo "=== Schema Loading Verification ===" && \
echo "1. Environment:" && docker exec pg-cerbos-puppygraph env | grep SCHEMA_PATH && \
echo "2. File exists:" && docker exec pg-cerbos-puppygraph test -f /puppygraph/conf/aml-schema.json && echo "✅" || echo "❌" && \
echo "3. Vertex count:" && docker exec pg-cerbos-puppygraph cat /puppygraph/conf/aml-schema.json | jq -r '.graph.vertices | length' && \
echo "4. Configuration ready:" && docker logs pg-cerbos-puppygraph 2>&1 | grep "ConfigurationReady" | tail -1
```
