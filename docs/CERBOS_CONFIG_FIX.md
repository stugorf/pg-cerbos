# Cerbos Configuration Fix

## Issue Fixed

The audit configuration had invalid fields. Fixed by:

1. **Removed invalid fields**: `bufferSize` and `flushInterval` were incorrectly placed directly under `local`
2. **Simplified configuration**: Removed `advanced` section (optional settings)
3. **Fixed storage path**: Changed from file path to directory path

## Current Configuration

The `cerbos.yaml` now has a simplified, valid configuration:

```yaml
audit:
  enabled: true
  backend: "local"
  local:
    storagePath: /tmp/cerbos-audit
    retentionPeriod: 168h  # 7 days
```

## If Cerbos Still Fails

### Option 1: Check Logs
```bash
docker compose logs cerbos
```

Look for specific error messages about:
- Configuration syntax errors
- Missing files or directories
- Permission issues

### Option 2: Use Minimal Config (Testing)

If the full config still has issues, temporarily use the minimal config:

1. Update `compose.yml` to use minimal config:
   ```yaml
   cerbos:
     volumes:
       - ./cerbos/policies:/policies:ro
       - ./cerbos/cerbos-minimal.yaml:/config/cerbos.yaml:ro
   ```

2. Restart Cerbos:
   ```bash
   docker compose restart cerbos
   ```

### Option 3: Disable Audit Entirely

If audit is causing issues, disable it:

```yaml
audit:
  enabled: false
```

### Option 4: Disable Request Validation

If schema validation is causing issues:

```yaml
requestValidation:
  enabled: false
```

## Verification

Run the configuration check:
```bash
just check-cerbos-config
```

Or manually:
```bash
bash scripts/check-cerbos-config.sh
```

## Common Issues

1. **Schema files not found**: Ensure `_schemas/principal.json` and `_schemas/resource.json` exist
2. **Policy syntax errors**: Validate policies with Cerbos CLI
3. **Directory permissions**: Ensure `/tmp/cerbos-audit` can be created (or disable audit)

## Next Steps

1. Restart Cerbos: `docker compose restart cerbos`
2. Check logs: `docker compose logs cerbos`
3. Verify health: `just check-cerbos`
