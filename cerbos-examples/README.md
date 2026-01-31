# Cerbos Migration Examples

This directory contains example Cerbos policies and configuration files for migrating from OPA to Cerbos.

## Directory Structure

```
cerbos-examples/
├── cerbos.yaml                    # Cerbos server configuration
├── policies/
│   ├── _schemas/                  # JSON schemas for validation
│   │   ├── principal.json        # User/principal schema
│   │   └── resource.json         # Resource schema
│   ├── resource_policies/         # Resource-based policies
│   │   ├── postgres.yaml         # PostgreSQL access policies
│   │   └── iceberg.yaml          # Iceberg access policies
│   └── tests/                     # Policy test suite
│       └── test_suite.yaml       # Comprehensive test cases
└── README.md                      # This file
```

## Policy Files

### Resource Policies

- **`postgres.yaml`** - Defines access control rules for PostgreSQL database queries
- **`iceberg.yaml`** - Defines access control rules for Iceberg table queries

### Schemas

- **`principal.json`** - Validates user/principal attributes (id, email, roles)
- **`resource.json`** - Validates resource attributes (kind, catalog, schema, table, query)

### Tests

- **`test_suite.yaml`** - Comprehensive test cases covering all user roles and scenarios

## Usage

### Testing Policies Locally

1. Install Cerbos CLI:
   ```bash
   brew install cerbos
   # or
   curl -L https://github.com/cerbos/cerbos/releases/latest/download/cerbos_0.0.0_darwin_amd64.tar.gz | tar xz
   ```

2. Validate policies:
   ```bash
   cerbos compile policies/
   ```

3. Run tests:
   ```bash
   cerbos test policies/tests/test_suite.yaml
   ```

### Running Cerbos Server

1. Start Cerbos with file-based storage:
   ```bash
   cerbos server --set=storage.driver=disk --set=storage.disk.directory=./policies
   ```

2. Or use Docker:
   ```bash
   docker run -it --rm \
     -v $(pwd)/policies:/policies \
     -v $(pwd)/cerbos.yaml:/config/cerbos.yaml \
     -p 3593:3593 \
     ghcr.io/cerbos/cerbos:latest \
     server --config=/config/cerbos.yaml
   ```

### Testing Authorization

```bash
# Test admin access
curl -X POST http://localhost:3593/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "id": "1",
      "roles": ["admin"],
      "attr": {"email": "admin@ues-mvp.com"}
    },
    "resource": {
      "kind": "postgres",
      "id": "query-001",
      "attr": {
        "method": "POST",
        "path": "/v1/statement",
        "body": "SELECT * FROM postgres.public.person"
      }
    },
    "actions": ["query"]
  }'
```

## Policy Mapping

### Current OPA Policies → Cerbos Equivalents

| OPA Policy | Cerbos Policy | File |
|------------|---------------|------|
| `authz-policy-fixed.rego` | `postgres.yaml` + `iceberg.yaml` | `policies/resource_policies/` |
| `field_security.rego` | Field-level rules in resource policies | `policies/resource_policies/*.yaml` |

## Next Steps

1. Review the policies in this directory
2. Customize them for your specific needs
3. Test them using the Cerbos CLI
4. Deploy Cerbos alongside OPA for parallel running
5. Gradually migrate traffic to Cerbos
6. Remove OPA once migration is complete

## References

- [Cerbos Documentation](https://docs.cerbos.dev/)
- [Cerbos Policy Authoring Guide](https://docs.cerbos.dev/cerbos/latest/policies/overview)
- [Cerbos Test Suite Format](https://docs.cerbos.dev/cerbos/latest/policies/testing)
