# Temporarily Disabling Cerbos

## Current Status

Cerbos is temporarily disabled because it's failing to start. The system is now configured to use **OPA** (the original authorization system) so everything can run normally.

## What Was Changed

1. **Commented out Cerbos services** in `compose.yml`:
   - `cerbos` service
   - `cerbos-adapter` service

2. **Reverted Envoy** to use OPA instead of Cerbos adapter

3. **System now uses OPA** for authorization (original working setup)

## Current Architecture

```
Client Request
    ↓
Envoy (Port 8081)
    ↓
OPA (Port 8181) ← Currently Active
    ↓
Authorization Decision
    ↓
Trino (Port 8080)
```

## To Re-enable Cerbos Later

When Cerbos configuration issues are resolved:

1. **Uncomment Cerbos services** in `compose.yml`:
   ```yaml
   cerbos:
     # ... uncomment this section
   
   cerbos-adapter:
     # ... uncomment this section
   ```

2. **Update Envoy** to use Cerbos adapter:
   - Edit `envoy/envoy.yaml`
   - Change `opa_cluster` back to `cerbos_adapter_cluster`
   - Change OPA URL to Cerbos adapter URL

3. **Restart services**:
   ```bash
   docker compose up -d
   ```

## About OPA

**Do you still need OPA?**

- **For now: YES** - OPA is currently handling all authorization
- **After Cerbos works: NO** - You can remove OPA once Cerbos is fully functional

## Migration Path

1. ✅ **Current**: OPA handling authorization (working)
2. ⏳ **Next**: Fix Cerbos configuration issues
3. ⏳ **Then**: Enable Cerbos alongside OPA (parallel running)
4. ⏳ **Finally**: Switch Envoy to Cerbos, then remove OPA

## Troubleshooting Cerbos

To debug Cerbos issues:

1. **Check logs**:
   ```bash
   docker compose logs cerbos
   ```

2. **Try minimal config**:
   - Use `cerbos-minimal.yaml` instead of `cerbos.yaml`
   - Or disable audit/validation temporarily

3. **Test Cerbos standalone**:
   ```bash
   docker run --rm -v $(pwd)/cerbos/policies:/policies \
     -v $(pwd)/cerbos/cerbos-minimal.yaml:/config/cerbos.yaml \
     ghcr.io/cerbos/cerbos:latest server --config=/config/cerbos.yaml
   ```

## Files Status

- ✅ **OPA**: Active and working
- ⏸️ **Cerbos**: Disabled (commented out in compose.yml)
- ✅ **Envoy**: Using OPA
- ✅ **All other services**: Running normally

The system should now start successfully with OPA handling authorization!
