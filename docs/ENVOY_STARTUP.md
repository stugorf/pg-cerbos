# Envoy Startup Guide

## Current Status

From your `docker compose ps` output:
- ✅ **Cerbos**: Running (shows unhealthy but service works)
- ✅ **Cerbos Adapter**: Healthy
- ✅ **All dependencies**: Running
- ❌ **Envoy**: **NOT RUNNING** (missing from container list)

## Port Review

All ports in `compose.yml` are correctly configured:
- ✅ Envoy: `8081:8081` (client entrypoint)
- ✅ Cerbos: `3593:3593`
- ✅ Cerbos Adapter: `3594:8080`
- ✅ Trino: `8080:8080`
- ✅ OPA: `8181:8181`

## Start Envoy

### Option 1: Quick Start
```bash
docker compose up -d envoy
```

### Option 2: Use Helper Script
```bash
just start-envoy
```

### Option 3: Start Everything
```bash
docker compose up -d
```

## Verify Envoy Started

```bash
# Check status
docker compose ps envoy

# Should show: STATUS = Up

# Test endpoint
curl http://localhost:8081/v1/info
```

## Test Authorization

Once Envoy is running, test with:

```bash
curl -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@pg-cerbos.com' \
  -H 'x-user-roles: full_access_user' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement
```

## Troubleshooting

If Envoy fails to start:

1. **Check logs:**
   ```bash
   docker compose logs envoy
   ```

2. **Check configuration:**
   ```bash
   docker compose config envoy
   ```

3. **Verify dependencies:**
   ```bash
   docker compose ps cerbos-adapter trino-coordinator
   ```

4. **Check Envoy config syntax:**
   ```bash
   docker run --rm -v $(pwd)/envoy/envoy.yaml:/envoy.yaml envoyproxy/envoy:v1.30-latest \
     envoy --config-path /envoy.yaml --mode validate
   ```

## Why Envoy Might Not Start

Common reasons:
1. **Configuration error** - Check `envoy/envoy.yaml` syntax
2. **Dependency not ready** - Adapter or Trino not healthy
3. **Port conflict** - Something else using port 8081
4. **Network issue** - Can't reach adapter service

## Next Steps

1. Start Envoy: `docker compose up -d envoy`
2. Verify: `docker compose ps envoy`
3. Test: Use the curl command above
4. Monitor: `docker compose logs -f envoy cerbos-adapter cerbos`
