# Cerbos Adapter Troubleshooting

## Issue: Adapter Not Responding

If `just check-cerbos-adapter` hangs or shows no response, the adapter container likely isn't running.

## Quick Fix

### Step 1: Check if Adapter Container Exists

```bash
docker compose ps cerbos-adapter
```

If it shows nothing or "Exited", the container isn't running.

### Step 2: Build and Start the Adapter

```bash
# Build the adapter image (first time only)
docker compose build cerbos-adapter

# Start the adapter
docker compose up -d cerbos-adapter

# Check status
docker compose ps cerbos-adapter
```

### Step 3: Check Logs

```bash
docker compose logs cerbos-adapter
```

Look for:
- ✅ "Application startup complete" - Adapter is running
- ❌ Import errors - Missing dependencies
- ❌ Connection errors - Can't reach Cerbos
- ❌ Port binding errors - Port 3594 already in use

## Common Issues

### 1. Adapter Image Not Built

**Symptom:** Container shows "Image not found" or similar

**Fix:**
```bash
docker compose build cerbos-adapter
```

### 2. Adapter Can't Connect to Cerbos

**Symptom:** Logs show "Connection refused" or "Name resolution failed"

**Check:**
```bash
# Verify Cerbos is running
docker compose ps cerbos

# Test Cerbos health
curl http://localhost:3593/_cerbos/health

# Check network connectivity
docker compose exec cerbos-adapter ping -c 1 cerbos
```

**Fix:** Ensure Cerbos is healthy before starting adapter

### 3. Port Already in Use

**Symptom:** "Bind for 0.0.0.0:3594 failed: port is already allocated"

**Fix:**
```bash
# Find what's using the port
lsof -i :3594

# Stop the conflicting service or change port in compose.yml
```

### 4. Adapter Crashes on Startup

**Symptom:** Container exits immediately

**Check logs:**
```bash
docker compose logs cerbos-adapter
```

**Common causes:**
- Missing Python dependencies
- Syntax errors in adapter.py
- Environment variable issues

**Fix:**
```bash
# Rebuild with no cache
docker compose build --no-cache cerbos-adapter

# Check adapter code
python3 -m py_compile cerbos-adapter/adapter.py
```

## Verification

Once adapter is running:

```bash
# Check container status
docker compose ps cerbos-adapter

# Should show: STATUS = "Up" or "healthy"

# Test health endpoint
curl http://localhost:3594/health

# Should return: {"status":"healthy","service":"cerbos-adapter"}
```

## Manual Testing

Test the adapter directly:

```bash
curl -X POST http://localhost:3594/check \
  -H "Content-Type: application/json" \
  -d '{
    "attributes": {
      "request": {
        "http": {
          "method": "POST",
          "path": "/v1/statement",
          "headers": {
            "x-user-id": "1",
            "x-user-email": "admin@pg-cerbos.com",
            "x-user-roles": "admin"
          },
          "body": "SELECT 1"
        }
      }
    }
  }'
```

Should return authorization decision in Envoy format.

## Next Steps

Once adapter is running:
1. Restart Envoy: `docker compose restart envoy`
2. Test authorization flow through Envoy
3. Monitor logs: `docker compose logs -f cerbos-adapter`
