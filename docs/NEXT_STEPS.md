# Next Steps for Cerbos Refactoring

## Immediate Actions

### 1. Rebuild and Test

```bash
# Rebuild backend with Cerbos SDK
docker compose build --no-cache policy-registry-backend

# Start services (Envoy, OPA, cerbos-adapter will be skipped)
docker compose up -d

# Check Cerbos is running
curl http://localhost:3593/_cerbos/health

# Check backend is running
curl http://localhost:8082/health
```

### 2. Test Cerbos Integration

```bash
# Test authorization (should work with existing policies)
curl -X POST http://localhost:8082/query \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM postgres.public.person LIMIT 5"}'
```

### 3. Access New UIs

- **Cerbos Policy Editor**: http://localhost:8083/cerbos-policy-editor.html
- **Query Interface**: http://localhost:8083/query.html
- **Authentication**: http://localhost:8083/auth.html

## Potential Issues to Watch For

### Cerbos SDK API Compatibility

The Cerbos Python SDK API might differ from what we implemented. If you see import errors or method signature issues:

1. Check the actual SDK version: `pip show cerbos`
2. Review SDK documentation: https://github.com/cerbos/cerbos-sdk-python
3. Adjust `cerbos_client.py` to match the actual API

### Policy Directory Access

The backend needs read access to `./cerbos/policies`. If policies aren't loading:

1. Check volume mount in compose.yml
2. Verify directory permissions
3. Check Cerbos logs: `docker compose logs cerbos`

### Authentication Token

The query interface requires a JWT token. Users need to:
1. Log in via auth.html
2. Token is stored in localStorage
3. Token is sent with API requests

## Cleanup Tasks (Optional)

### Remove Legacy Code

1. **Remove OPA bundle endpoint** (if not needed):
   - File: `policy-registry/backend/app.py`
   - Function: `get_bundle()`

2. **Remove directories** (if not needed):
   - `envoy/` - Envoy configuration
   - `cerbos-adapter/` - Adapter service code
   - `opa/` - OPA policy files

3. **Update Justfile**:
   - Remove OPA-related commands
   - Remove Envoy-related commands
   - Update Cerbos commands

### Update Port References

Update any scripts or documentation that reference:
- Port 8081 (Envoy) - no longer used
- Port 3594 (cerbos-adapter) - no longer used
- Port 8181 (OPA) - no longer used

## Testing Checklist

- [ ] Backend starts without errors
- [ ] Cerbos service is accessible
- [ ] Can authenticate via auth.html
- [ ] Can view policies in Cerbos editor
- [ ] Can edit and save policies
- [ ] Can execute queries via query interface
- [ ] Authorization works for different user roles
- [ ] Query results display correctly

## Rollback Plan

If issues occur, you can temporarily:

1. **Restore OPA** (if needed):
   - Uncomment OPA service in compose.yml
   - Revert query endpoint to use OPA
   - Restart services

2. **Keep both systems** (for testing):
   - Keep Cerbos and OPA running in parallel
   - Use feature flag to switch between them

## Success Criteria

✅ All services start successfully  
✅ Cerbos policies are loaded and working  
✅ Query authorization works correctly  
✅ Policy editor allows CRUD operations  
✅ Query interface executes queries and shows results  
✅ Different user roles are properly authorized  
