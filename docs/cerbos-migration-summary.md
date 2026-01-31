# Cerbos Migration Summary

## Quick Overview

This document provides a high-level summary of migrating from OPA to Cerbos in the UES MVP.

## What Changes

### Components Being Replaced

| Current Component | Replacement | Reason |
|------------------|-------------|---------|
| **OPA Service** | **Cerbos Service** | More developer-friendly, GitOps-native |
| **Rego Policies** | **Cerbos YAML Policies** | Easier to read and maintain |
| **OPA Bundle API** | **Cerbos Git Storage** | Native GitOps support |
| **Policy Registry Bundle Endpoint** | **Cerbos Policy Management** | Simplified policy management |

### What Stays the Same

- ✅ **Envoy** - Still used as authorization proxy (with adapter)
- ✅ **PostgreSQL** - Still stores user/role/permission data
- ✅ **Policy Registry Backend** - Still manages policies (updated for Cerbos)
- ✅ **Authentication System** - JWT-based auth remains unchanged
- ✅ **Authorization Model** - Same roles, resources, and actions

## Key Differences: OPA vs Cerbos

### Policy Language

**OPA (Rego):**
```rego
allow = {
  "allowed": true,
  "headers": {"x-authz": "admin-access"}
} if {
  "admin" in user_roles
}
```

**Cerbos (YAML):**
```yaml
rules:
  - actions: ["query"]
    effect: EFFECT_ALLOW
    roles: ["admin"]
```

### API Format

**OPA:**
```
POST /v1/data/envoy/authz/allow
{
  "input": {
    "attributes": {
      "request": { "http": {...} }
    }
  }
}
```

**Cerbos:**
```
POST /api/check
{
  "principal": { "id": "1", "roles": ["admin"] },
  "resource": { "kind": "postgres" },
  "actions": ["query"]
}
```

## Migration Approach

### Phase 1: Parallel Running
- Deploy Cerbos alongside OPA
- Route test traffic to Cerbos
- Compare authorization decisions
- Validate policy correctness

### Phase 2: Full Migration
- Switch Envoy to use Cerbos
- Remove OPA components
- Update documentation

## Estimated Timeline

- **Week 1:** Setup and policy migration
- **Week 2:** Integration and adapter development  
- **Week 3:** Testing and validation
- **Week 4:** Deployment and cleanup

**Total: 4 weeks**

## Benefits

1. **Better Developer Experience** - YAML is more readable than Rego
2. **GitOps Native** - Built-in Git integration for policy management
3. **Better Performance** - gRPC support, optimized for high throughput
4. **Easier Maintenance** - Policies are easier to understand and modify

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Policy logic differences | Comprehensive test suite, parallel running |
| Performance impact | Performance testing, sidecar deployment |
| Integration complexity | Adapter service pattern |

## Next Steps

1. Review the detailed migration plan (`cerbos-migration-plan.md`)
2. Set up Cerbos development environment
3. Create initial Cerbos policies
4. Build Envoy-Cerbos adapter
5. Begin parallel running phase
