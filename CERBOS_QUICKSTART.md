# Cerbos Quick Start Guide

## 🚀 Getting Started with Cerbos

The Cerbos migration has been implemented. Follow these steps to get started.

## Prerequisites

- Docker and Docker Compose installed
- Ports 3593, 3594 available (in addition to existing ports)

## Quick Start

### 1. Start All Services

```bash
just up
```

This will start:
- ✅ Cerbos PDP (port 3593)
- ✅ Cerbos Adapter (port 3594)
- ✅ Envoy (updated to use Cerbos)
- ✅ OPA (still running for comparison)
- ✅ All other existing services

### 2. Check Cerbos Health

```bash
# Check Cerbos service
just check-cerbos

# Check adapter
just check-cerbos-adapter
```

### 3. Validate Policies

```bash
# List policies
just list-cerbos-policies

# Validate syntax (requires Cerbos CLI)
just validate-cerbos-policies

# Run tests (requires Cerbos CLI)
just test-cerbos-policies
```

### 4. Test Authorization

```bash
# Test query through Envoy (now using Cerbos)
curl -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@ues-mvp.com' \
  -H 'x-user-roles: full_access_user' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement
```

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Envoy     │ Port 8081
│  (ext_authz)│
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Cerbos Adapter  │ Port 3594
│  (Translation)  │
└──────┬──────────┘
       │
       ▼
┌─────────────┐
│   Cerbos    │ Port 3593
│     PDP     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Trino     │ Port 8080
└─────────────┘
```

## Key Commands

### Health Checks
```bash
just check-cerbos           # Check Cerbos health
just check-cerbos-adapter   # Check adapter health
just ps                     # Show all containers
```

### Policy Management
```bash
just list-cerbos-policies        # List all policies
just validate-cerbos-policies     # Validate policy syntax
just test-cerbos-policies        # Run policy tests
```

### Logs
```bash
just cerbos-logs           # View Cerbos and adapter logs
just logs                  # View all service logs
```

### API Endpoints

**Policy Registry Backend** (port 8082):
- `GET /cerbos/policies` - List Cerbos policies
- `GET /cerbos/policies/{name}` - Get specific policy
- `POST /cerbos/policies/validate` - Validate policy
- `GET /cerbos/health` - Check Cerbos health

**Cerbos Direct** (port 3593):
- `POST /api/check` - Authorization check
- `GET /_cerbos/health` - Health check

**Cerbos Adapter** (port 3594):
- `POST /check` - Envoy-compatible authorization check
- `GET /health` - Health check

## Policy Files

Policies are located in `cerbos/policies/`:

```
cerbos/policies/
├── _schemas/
│   ├── principal.json    # User schema
│   └── resource.json     # Resource schema
├── resource_policies/
│   ├── postgres.yaml     # PostgreSQL policies
│   └── iceberg.yaml      # Iceberg policies
└── tests/
    └── test_suite.yaml    # Policy tests
```

## Switching Between OPA and Cerbos

### Current Setup (Cerbos)
Envoy is configured to use Cerbos adapter. This is the default.

### Switch to OPA (if needed)
Edit `envoy/envoy.yaml`:
- Change `cerbos_adapter_cluster` to `opa_cluster`
- Change adapter URL to OPA URL
- Restart Envoy: `docker compose restart envoy`

### Parallel Running
Both OPA and Cerbos are running simultaneously. You can:
- Compare authorization decisions
- Test both systems
- Gradually migrate traffic

## Troubleshooting

### Cerbos not starting
```bash
# Check logs
docker compose logs cerbos

# Verify policies exist
ls -la cerbos/policies/resource_policies/

# Check configuration
cat cerbos/cerbos.yaml
```

### Adapter errors
```bash
# Check adapter logs
docker compose logs cerbos-adapter

# Test adapter directly
curl http://localhost:3594/health

# Verify Cerbos is up
just check-cerbos
```

### Authorization failures
```bash
# Check Cerbos logs
just cerbos-logs

# Validate policies
just validate-cerbos-policies

# Check Envoy logs
docker compose logs envoy
```

## Next Steps

1. ✅ **Test the system** - Run queries and verify authorization
2. ✅ **Compare with OPA** - Both systems are running in parallel
3. ✅ **Monitor logs** - Watch for any issues
4. ✅ **Validate policies** - Ensure policies match requirements
5. ⏳ **Full migration** - Remove OPA when ready (optional)

## Documentation

- [Migration Plan](docs/cerbos-migration-plan.md) - Detailed migration plan
- [Implementation Status](docs/CERBOS_IMPLEMENTATION_STATUS.md) - Current status
- [Migration Summary](docs/cerbos-migration-summary.md) - High-level overview

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the migration plan documentation
3. Check Cerbos logs: `just cerbos-logs`
4. Verify policies: `just validate-cerbos-policies`
