# Cerbos Migration Documentation Index

This document provides an index to all Cerbos migration-related documentation.

## Migration Documents

### 1. [Migration Plan](./cerbos-migration-plan.md)
**Comprehensive migration plan** covering all phases from planning to deployment.

**Contents:**
- Current architecture analysis
- Cerbos architecture overview
- Detailed migration strategy (6 phases)
- Implementation steps
- Risk mitigation
- Timeline estimates

**Use this for:** Understanding the complete migration process and planning your implementation.

### 2. [Migration Summary](./cerbos-migration-summary.md)
**High-level summary** of the migration with key points and quick reference.

**Contents:**
- What changes vs what stays the same
- Key differences: OPA vs Cerbos
- Migration approach overview
- Timeline and benefits

**Use this for:** Quick overview and executive summary.

### 3. [Example Policies](../cerbos-examples/)
**Working examples** of Cerbos policies, schemas, and tests.

**Contents:**
- Resource policies (postgres.yaml, iceberg.yaml)
- JSON schemas (principal.json, resource.json)
- Test suite (test_suite.yaml)
- Cerbos configuration (cerbos.yaml)

**Use this for:** Reference implementation and starting point for your policies.

## Quick Start

1. **Read the Summary** → [cerbos-migration-summary.md](./cerbos-migration-summary.md)
2. **Review the Plan** → [cerbos-migration-plan.md](./cerbos-migration-plan.md)
3. **Examine Examples** → [cerbos-examples/](../cerbos-examples/)
4. **Start Implementation** → Follow Phase 1 in the migration plan

## Key Components to Replace

| Component | Current | Replacement | Status |
|-----------|---------|------------|--------|
| Policy Engine | OPA (Rego) | Cerbos (YAML) | ⏳ Planned |
| Policy Storage | Postgres + Bundles | Git or Filesystem | ⏳ Planned |
| API Format | OPA REST API | Cerbos REST/gRPC | ⏳ Planned |
| Envoy Integration | Direct OPA call | Adapter Service | ⏳ Planned |

## Migration Phases

1. **Phase 1: Setup** - Add Cerbos service, create policy structure
2. **Phase 2: Policy Migration** - Convert Rego to Cerbos YAML
3. **Phase 3: Integration** - Update Envoy, backend, application code
4. **Phase 4: Testing** - Comprehensive test suite
5. **Phase 5: Deployment** - Parallel running, gradual rollout
6. **Phase 6: Cleanup** - Remove OPA, update documentation

## Timeline

- **Week 1:** Infrastructure setup and policy migration
- **Week 2:** Integration updates and adapter development
- **Week 3:** Testing and validation
- **Week 4:** Deployment and cleanup

**Total: 4 weeks**

## Questions?

Refer to:
- [Cerbos Documentation](https://docs.cerbos.dev/)
- [Migration Plan](./cerbos-migration-plan.md) for detailed implementation steps
- [Example Policies](../cerbos-examples/) for working code examples
