# Adapter Route Fix Plan

## Problem Analysis

### Current Situation
1. **Envoy Configuration**: Uses `path_prefix: /check`, which prepends `/check` to the original request path
2. **Request Flow**: Client → Envoy (`/v1/statement`) → Adapter (`/check/v1/statement`)
3. **Adapter Routes**: Defined as `/check` and `/check/{rest:path}`
4. **Issue**: Routes are not matching `/check/v1/statement`, returning 404

### Root Cause
The `path_prefix` in Envoy's `ext_authz` configuration prepends to the original request path, causing Envoy to call `/check/v1/statement` instead of `/check`. While the adapter has routes to handle this, they're not matching.

### Why Routes Aren't Matching
Possible reasons:
1. **Code not rebuilt**: Changes to `adapter.py` not included in container image
2. **FastAPI route order**: `/check` route might be interfering with `/check/{rest:path}`
3. **Route registration issue**: Routes not being registered correctly
4. **FastAPI version issue**: `{rest:path}` syntax might not work as expected

## Solution Options

### Option 1: Fix at Envoy Level (RECOMMENDED)
**Remove `path_prefix` and put `/check` in URI**

**Pros:**
- Simpler adapter code (only needs `/check` route)
- Envoy calls fixed endpoint regardless of original path
- More predictable behavior

**Cons:**
- Need to verify Envoy doesn't append path when URI includes path

**Implementation:**
```yaml
http_service:
  server_uri:
    uri: http://cerbos-adapter:8080/check
    cluster: cerbos_adapter_cluster
    timeout: 2s
  # Remove path_prefix
```

### Option 2: Fix at Adapter Level
**Ensure FastAPI routes handle `/check/*` correctly**

**Pros:**
- More flexible (can handle different paths if needed)
- Works with current Envoy config

**Cons:**
- More complex route matching
- Need to debug why routes aren't matching

**Implementation:**
- Verify route syntax is correct
- Test route matching directly
- Add comprehensive logging

### Option 3: Hybrid Approach
**Remove `path_prefix` AND ensure adapter handles both cases**

**Pros:**
- Most robust solution
- Works regardless of Envoy behavior

**Cons:**
- More code to maintain

## Recommended Solution: Option 1

### Steps

1. **Update Envoy Configuration**
   - Remove `path_prefix: /check`
   - Set `uri: http://cerbos-adapter:8080/check`

2. **Simplify Adapter Routes**
   - Keep only `/check` route (remove `/check/{rest:path}`)
   - Remove catch-all route

3. **Verify**
   - Restart Envoy
   - Test with Postman
   - Check logs to confirm `/check` is being called

### If Option 1 Doesn't Work

If Envoy still appends the path even when URI includes `/check`, then:

1. **Keep `path_prefix` removed**
2. **Fix adapter routes** to properly handle `/check/*`:
   - Use `@app.post("/check/{rest:path}")` with `rest: str` parameter
   - Ensure route is registered before exact `/check` route
   - Add comprehensive logging to verify route matching

3. **Debug Route Registration**
   - Check startup logs for registered routes
   - Test routes directly with curl
   - Verify FastAPI version supports `{path:path}` syntax

## Testing Plan

1. **Test Envoy → Adapter directly:**
   ```bash
   curl -X POST http://localhost:3594/check \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
   ```

2. **Test full flow:**
   ```bash
   curl -X POST http://localhost:8081/v1/statement \
     -H 'x-user-id: 2' \
     -H 'x-user-email: fullaccess@pg-cerbos.com' \
     -H 'x-user-roles: full_access_user' \
     --data-binary 'SELECT * FROM postgres.public.person LIMIT 5'
   ```

3. **Check logs:**
   - Envoy logs: Should show calling `/check` (not `/check/v1/statement`)
   - Adapter logs: Should show route matched and handler called

## Implementation Priority

1. **Immediate**: Try Option 1 (remove path_prefix, use URI path)
2. **If that fails**: Debug adapter routes with direct testing
3. **Fallback**: Use Option 3 (handle both cases)
