# Cerbos RBAC/ABAC Analysis - Executive Summary

## Current State

### ✅ What's Working

**SQL Queries (Postgres/Iceberg):**
- ✅ Role-based access control (4 roles: admin, full_access_user, postgres_only_user, restricted_user)
- ✅ Field-level restrictions (SSN blocking for restricted users)
- ✅ Catalog-based access control (Postgres vs Iceberg)
- ✅ Query content inspection

**Graph Queries (Cypher/Gremlin):**
- ✅ Basic role-based access (admin, aml_analyst, aml_manager)
- ✅ Query type differentiation (Cypher vs Gremlin)
- ✅ Authorization before execution

### ⚠️ Gaps Identified

**RBAC Gaps for Cypher Queries:**
1. **No role-based query restrictions** - All analysts can execute any Cypher query
2. **No role hierarchy** - Flat role structure, no inheritance
3. **No role-based complexity limits** - No limits on traversal depth, node count, etc.
4. **Limited role granularity** - Only 3 roles for graph queries

**ABAC Gaps for Cypher Queries:**
1. **No Cypher query parsing** - Query structure not analyzed
2. **No node/relationship type restrictions** - Cannot restrict access to specific graph elements
3. **No user attribute-based restrictions** - No team, region, clearance level checks
4. **No resource attribute extraction** - Cannot restrict based on customer risk, transaction amount, etc.
5. **No query complexity analysis** - No limits on depth, nodes, edges, execution time

---

## Recommendations

### Priority 1: Cypher Query Parsing (Critical)

**Why:** Foundation for all other enhancements. Without parsing, we cannot extract query metadata for authorization.

**What:**
- Parse Cypher queries to extract:
  - Node labels (Customer, Transaction, Account, SAR, etc.)
  - Relationship types (OWNS, SENT_TXN, TO_ACCOUNT, etc.)
  - Traversal depth (number of hops)
  - Query patterns (MATCH, WHERE, RETURN)
  - Aggregation functions

**Impact:** Enables fine-grained access control based on what the query actually accesses.

### Priority 2: Enhanced RBAC (High)

**Why:** Provides role-based restrictions on query complexity and access patterns.

**What:**
- Create role hierarchy (junior_analyst → senior_analyst → manager)
- Add role-based restrictions:
  - Max traversal depth per role
  - Allowed node types per role
  - Allowed relationship types per role
  - Query complexity limits per role

**Impact:** Prevents unauthorized access to sensitive graph elements and limits query complexity.

### Priority 3: Enhanced ABAC (High)

**Why:** Enables attribute-based restrictions for fine-grained access control.

**What:**
- Add user attributes (team, region, clearance_level, department)
- Extract resource attributes from queries (customer risk, transaction amount, PEP flag)
- Implement attribute-based policies (team-based, clearance-based, amount-based)

**Impact:** Enables context-aware access control (e.g., team-based case access, clearance-based PEP access).

### Priority 4: Query Complexity Analysis (Medium)

**Why:** Prevents resource exhaustion and improves security.

**What:**
- Analyze query complexity (depth, node count, edge count)
- Implement complexity-based limits
- Add execution time limits
- Add result set size limits

**Impact:** Prevents expensive queries and protects system resources.

---

## Implementation Phases

### Phase 1: Cypher Query Parsing (2 weeks)
- Implement parser
- Integrate into authorization flow
- Add unit tests

### Phase 2: Enhanced RBAC (1-2 weeks)
- Create role-based policies
- Implement role hierarchy
- Test role restrictions

### Phase 3: Enhanced ABAC (1-2 weeks)
- Add user attributes
- Extract resource attributes
- Create attribute-based policies

### Phase 4: Complexity Analysis (1 week)
- Implement complexity analysis
- Add complexity limits
- Test limits

### Phase 5: Testing & Documentation (1-2 weeks)
- Integration tests
- Documentation updates
- Performance optimization

**Total Timeline: 6-9 weeks**

---

## Example Policy Structure

```yaml
# New: cypher_query.yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "cypher_query"
  rules:
    # Junior Analyst: Limited to 2 hops, no SAR nodes
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst_junior"]
      condition:
        match:
          expr: |
            R.attr.max_depth <= 2 &&
            !R.attr.node_labels.contains("SAR")
    
    # Senior Analyst: Up to 4 hops, all except SAR
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst_senior"]
      condition:
        match:
          expr: |
            R.attr.max_depth <= 4 &&
            !R.attr.node_labels.contains("SAR")
    
    # Team-based restrictions
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst"]
      condition:
        match:
          expr: |
            R.attr.node_labels.contains("Customer") &&
            P.attr.team == R.attr.customer_team
    
    # Clearance-based PEP access
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst"]
      condition:
        match:
          expr: |
            R.attr.pep_flag == true &&
            P.attr.clearance_level >= 3
```

---

## Key Files to Modify

1. **`policy-registry/backend/cypher_parser.py`** (NEW)
   - Cypher query parsing logic

2. **`policy-registry/backend/app.py`**
   - Update `/query/graph` endpoint to use parser

3. **`policy-registry/backend/cerbos_client.py`**
   - Add principal attributes support

4. **`cerbos/policies/resource_policies/cypher_query.yaml`** (NEW)
   - Cypher query-specific policies

5. **`cerbos/policies/derived_roles/graph_query_roles.yaml`** (NEW)
   - Role hierarchy definitions

6. **`cerbos/policies/_schemas/cypher_query_resource.json`** (NEW)
   - Resource schema for Cypher queries

7. **`postgres/init/30-auth-schema.sql`**
   - Add user_attributes table

---

## Next Steps

1. **Review this analysis** with stakeholders
2. **Prioritize phases** based on business needs
3. **Start Phase 1** (Cypher query parsing)
4. **Iterate** based on feedback and testing

For detailed analysis, see [CERBOS_RBAC_ABAC_ANALYSIS.md](./CERBOS_RBAC_ABAC_ANALYSIS.md).
