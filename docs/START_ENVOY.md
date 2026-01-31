# Starting Envoy

## Issue

Envoy is not running, which is why port 8081 is not accessible.

## Solution

Start Envoy with:

```bash
docker compose up -d envoy
```

Or use the helper script:

```bash
just start-envoy
```

## Why Envoy Isn't Running

Envoy depends on:
- `cerbos-adapter` ✅ (running and healthy)
- `trino-coordinator` ✅ (running and healthy)
- `opa` ✅ (running)

All dependencies are met, so Envoy should start successfully.

## After Starting Envoy

### 1. Verify Envoy is Running

```bash
docker compose ps envoy
```

Should show: `STATUS = Up`

### 2. Test the Endpoint

```bash
curl -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@ues-mvp.com' \
  -H 'x-user-roles: full_access_user' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement
```

### 3. Check Logs if Issues

```bash
docker compose logs envoy
```

Look for:
- ✅ "all dependencies initialized"
- ✅ "starting workers"
- ❌ Configuration errors
- ❌ Connection errors to adapter

## Port Summary

- **8081**: Envoy (client entrypoint) ← **Needs to be started**
- **3593**: Cerbos (working)
- **3594**: Cerbos Adapter (healthy)
- **8080**: Trino (healthy)

## Quick Start

```bash
# Start Envoy
docker compose up -d envoy

# Check status
docker compose ps envoy

# Test
curl http://localhost:8081/v1/info
```
