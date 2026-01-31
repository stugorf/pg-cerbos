# Cerbos Policy Format Fixes

## Issues Fixed

### 1. Invalid `description` Field
**Error:** `unknown field "description"`

**Problem:** Cerbos resource policies don't support a `description` field at the top level.

**Fix:** Removed `description` fields from:
- `cerbos/policies/resource_policies/postgres.yaml`
- `cerbos/policies/resource_policies/iceberg.yaml`

### 2. Invalid Test Suite Format
**Error:** `unknown field "name"` in `tests/test_suite.yaml`

**Problem:** Test suite files use a different format and shouldn't be in the policies directory that Cerbos scans.

**Fix:** Renamed `test_suite.yaml` to `test_suite.yaml.bak` to exclude it from policy loading.

## Correct Policy Format

```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "postgres"
  # No description field here
  
  rules:
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["admin"]
```

## Test Suite Files

Test suite files should be:
- Kept outside the policies directory, OR
- Renamed with `.bak` extension, OR
- Used only with Cerbos CLI `cerbos test` command (not loaded by server)

## Verification

After fixes, Cerbos should start successfully. Check with:

```bash
docker compose restart cerbos
docker compose logs cerbos
```

You should see:
- ✅ "Initializing disk store from /policies"
- ✅ No "Index build failed" errors
- ✅ Server starting successfully
