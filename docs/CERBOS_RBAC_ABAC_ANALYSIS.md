# Cerbos RBAC and ABAC Analysis for Cypher Queries

## Executive Summary

This document provides a comprehensive analysis of the current Cerbos integration for Policy-Based Access Control (PBAC), with a focus on Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC) coverage for user-submitted Cypher graph queries. It identifies gaps, provides recommendations, and proposes an implementation plan.

---

## 1. Current Implementation Overview

### 1.1 Policy-Based Access Control (PBAC) with Cerbos

The system currently implements **PBAC** using Cerbos as the Policy Decision Point (PDP). Cerbos evaluates YAML policies that define access rules based on:
- **Principal attributes**: User ID, roles, email
- **Resource attributes**: Resource kind, ID, query content, method, path
- **Actions**: query, view, graph_expand, read, write

### 1.2 Current Authorization Flow

#### SQL Queries (Postgres/Iceberg)
1. User submits SQL query via `/query` endpoint
2. Backend extracts user info from JWT (user_id, email, roles)
3. Backend calls Cerbos with:
   - Principal: `{id, roles, attr: {email}}`
   - Resource: `{kind: "postgres"|"iceberg", id: "query-{user_id}", attr: {method, path, body, catalog}}`
   - Action: `"query"`
4. Cerbos evaluates policies in `postgres.yaml` or `iceberg.yaml`
5. Decision (ALLOW/DENY) is logged and enforced

#### Graph Queries (Cypher/Gremlin)
1. User submits Cypher/Gremlin query via `/query/graph` endpoint
2. Backend extracts user info from JWT
3. Backend calls Cerbos with:
   - Principal: `{id, roles, attr: {email}}`
   - Resource: `{kind: "transaction", id: "graph-query", attr: {query_type}}`
   - Action: `"graph_expand"`
4. Cerbos evaluates policies in `transaction.yaml`
5. Decision is logged and query executed via PuppyGraph

---

## 2. Current RBAC Coverage

### 2.1 SQL Query RBAC

**Roles Defined:**
- `admin`: Full access to all resources and actions
- `full_access_user`: Can query all fields in Postgres and Iceberg
- `postgres_only_user`: Can query Postgres only (explicitly denied Iceberg)
- `restricted_user`: Can query both Postgres and Iceberg, but SSN fields are denied

**Policy Structure:**
```yaml
# postgres.yaml and iceberg.yaml
rules:
  - actions: ["query"]
    effect: EFFECT_ALLOW
    roles: ["full_access_user"]
    condition: # method and path checks
```

**RBAC Strengths:**
- ✅ Clear role-based rules
- ✅ Role-to-permission mapping is explicit
- ✅ Role hierarchy (admin > full_access > restricted)

**RBAC Gaps:**
- ⚠️ No role inheritance or derived roles for SQL queries
- ⚠️ Limited role granularity (only 4 roles)
- ⚠️ No role-based restrictions on query patterns or complexity

### 2.2 Graph Query RBAC

**Roles Defined:**
- `admin`: Full access to graph queries
- `aml_analyst`: Can view and expand transaction networks
- `aml_manager`: Can view and expand transaction networks

**Policy Structure:**
```yaml
# transaction.yaml
rules:
  - actions: ["view", "graph_expand"]
    effect: EFFECT_ALLOW
    roles: ["aml_analyst", "aml_manager"]
```

**RBAC Strengths:**
- ✅ Role-based access to graph operations
- ✅ Clear separation between analyst and manager roles

**RBAC Gaps for Cypher Queries:**
- ⚠️ **No Cypher query-specific role restrictions**
- ⚠️ **No role-based limits on graph traversal depth**
- ⚠️ **No role-based restrictions on node/edge types**
- ⚠️ **No role-based restrictions on query patterns** (e.g., path queries, aggregations)
- ⚠️ **Limited role granularity** (only 3 roles for graph queries)
- ⚠️ **No role-based query complexity limits** (e.g., max hops, max nodes returned)

---

## 3. Current ABAC Coverage

### 3.1 SQL Query ABAC

**Principal Attributes Used:**
- `id`: User identifier
- `email`: User email address
- `roles`: List of user roles

**Resource Attributes Used:**
- `method`: HTTP method (POST)
- `path`: Request path (/v1/statement)
- `body`: SQL query string
- `catalog`: Data source (postgres/iceberg)

**ABAC Strengths:**
- ✅ Field-level restrictions using query body analysis (SSN field blocking)
- ✅ Catalog-based access control (Postgres vs Iceberg)
- ✅ Query content inspection for field-level security

**ABAC Gaps:**
- ⚠️ **No user attribute-based restrictions** (e.g., department, region, clearance level)
- ⚠️ **No time-based access control** (e.g., business hours only)
- ⚠️ **No resource attribute-based restrictions** (e.g., table-level, schema-level)
- ⚠️ **Limited query metadata extraction** (only catalog detection)

### 3.2 Graph Query ABAC

**Principal Attributes Used:**
- `id`: User identifier
- `email`: User email address
- `roles`: List of user roles

**Resource Attributes Used:**
- `query_type`: "cypher" or "gremlin"
- `resource_kind`: "transaction" (hardcoded)

**ABAC Strengths:**
- ✅ Query type differentiation (Cypher vs Gremlin)

**ABAC Gaps for Cypher Queries:**
- ⚠️ **No Cypher query parsing or analysis**
- ⚠️ **No extraction of Cypher query elements**:
  - Node labels (Customer, Transaction, Account, etc.)
  - Relationship types (OWNS, SENT_TXN, TO_ACCOUNT, etc.)
  - Traversal depth (number of hops)
  - Query patterns (MATCH, WHERE, RETURN clauses)
  - Aggregation functions (COUNT, SUM, etc.)
- ⚠️ **No user attribute-based restrictions** (e.g., team, region, clearance)
- ⚠️ **No resource attribute-based restrictions** (e.g., customer risk rating, transaction amount thresholds)
- ⚠️ **No time-based or context-based access control**
- ⚠️ **No query complexity analysis** (e.g., max nodes, max edges, max path length)

---

## 4. Detailed Gap Analysis for Cypher Queries

### 4.1 RBAC Gaps

#### 4.1.1 Missing Role-Based Query Restrictions

**Current State:**
- All users with `aml_analyst` or `aml_manager` roles can execute any Cypher query
- No differentiation between query types or complexity

**Gap:**
- No role-based restrictions on:
  - **Query depth**: Junior analysts might only need 1-2 hop queries, while senior analysts need deeper traversals
  - **Node types**: Some roles might be restricted from accessing certain node types (e.g., SAR nodes)
  - **Relationship types**: Some roles might be restricted from certain relationship patterns
  - **Query operations**: Some roles might be restricted from aggregation or path-finding queries

**Example Scenarios:**
```cypher
# Junior analyst should only access 1-2 hops
MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
RETURN c, acc, txn

# Senior analyst can access deeper paths
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)<-[:OWNS]-(c2:Customer)
RETURN path
```

#### 4.1.2 Missing Role Hierarchy

**Current State:**
- Flat role structure (admin, aml_analyst, aml_manager)
- No role inheritance or derived roles for graph queries

**Gap:**
- No role hierarchy (e.g., `aml_manager` should inherit `aml_analyst` permissions)
- No derived roles based on context (e.g., `case_assignee` for case-specific queries)

**Example:**
The system has `aml_derived_roles.yaml` for case ownership, but it's not used for graph queries.

### 4.2 ABAC Gaps

#### 4.2.1 Missing Cypher Query Parsing

**Current State:**
- Cypher query is passed as a string in resource attributes
- No parsing or analysis of query structure

**Gap:**
- No extraction of:
  - **Node labels**: `(c:Customer)`, `(txn:Transaction)`
  - **Relationship types**: `[:OWNS]`, `[:SENT_TXN]`
  - **Traversal depth**: Number of hops in path queries
  - **Query patterns**: MATCH, WHERE, RETURN clauses
  - **Aggregations**: COUNT, SUM, AVG functions
  - **Path variables**: Named paths for analysis

**Impact:**
- Cannot enforce fine-grained access control based on what the query actually accesses
- Cannot restrict access to specific node types or relationship patterns
- Cannot limit query complexity

#### 4.2.2 Missing User Attribute-Based Restrictions

**Current State:**
- Only basic user attributes (id, email, roles) are used
- No additional user attributes (team, region, clearance level, department)

**Gap:**
- No team-based restrictions (e.g., Team A can only query Team A's cases)
- No region-based restrictions (e.g., EU analysts can only query EU customers)
- No clearance level restrictions (e.g., only high-clearance users can query PEP customers)

**Example Scenario:**
```cypher
# Should be restricted by user's team attribute
MATCH (c:Customer {team: "Team A"})-[:OWNS]->(acc:Account)
RETURN c, acc
```

#### 4.2.3 Missing Resource Attribute-Based Restrictions

**Current State:**
- Resource attributes are minimal (query_type, resource_kind)
- No extraction of resource attributes from the query itself

**Gap:**
- No restrictions based on:
  - **Customer attributes**: risk_rating, pep_flag, country
  - **Transaction attributes**: amount thresholds, currency, transaction type
  - **Case attributes**: status, priority, team assignment
  - **Account attributes**: account type, balance thresholds

**Example Scenario:**
```cypher
# Should be restricted by transaction amount
MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 100000
RETURN c, txn
```

#### 4.2.4 Missing Query Complexity Analysis

**Current State:**
- No analysis of query complexity
- No limits on query execution

**Gap:**
- No restrictions on:
  - **Max traversal depth**: Prevent deep graph traversals that could be expensive
  - **Max nodes returned**: Limit result set size
  - **Max path length**: Restrict path-finding queries
  - **Query execution time**: Time-based limits

---

## 5. Recommendations

### 5.1 RBAC Enhancements

#### 5.1.1 Implement Role-Based Query Restrictions

**Recommendation:**
Create a new Cerbos policy resource type `cypher_query` with role-based restrictions:

```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "cypher_query"
  rules:
    # Junior Analyst: Limited to 2-hop queries, no SAR nodes
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst_junior"]
      condition:
        match:
          expr: |
            R.attr.max_depth <= 2 &&
            !R.attr.node_labels.contains("SAR") &&
            !R.attr.node_labels.contains("CaseNote")
    
    # Senior Analyst: Up to 4-hop queries, all nodes except SAR
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst_senior"]
      condition:
        match:
          expr: |
            R.attr.max_depth <= 4 &&
            !R.attr.node_labels.contains("SAR")
    
    # Manager: Full access except SAR read-only
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_manager"]
      condition:
        match:
          expr: R.attr.max_depth <= 6
```

#### 5.1.2 Implement Role Hierarchy

**Recommendation:**
Use Cerbos derived roles to create role hierarchies:

```yaml
apiVersion: api.cerbos.dev/v1
derivedRoles:
  name: graph_query_roles
  definitions:
    - name: aml_analyst_senior
      parentRoles: ["aml_analyst_junior"]
      condition:
        match:
          expr: P.attr.clearance_level >= 2
    
    - name: aml_manager
      parentRoles: ["aml_analyst_senior"]
      condition:
        match:
          expr: P.attr.clearance_level >= 3
```

### 5.2 ABAC Enhancements

#### 5.2.1 Implement Cypher Query Parsing

**Recommendation:**
Add a Cypher query parser to extract query metadata:

```python
# New module: cypher_parser.py
from typing import Dict, List, Set
import re

def parse_cypher_query(query: str) -> Dict[str, any]:
    """Parse Cypher query and extract metadata for authorization."""
    return {
        "node_labels": extract_node_labels(query),
        "relationship_types": extract_relationship_types(query),
        "max_depth": calculate_traversal_depth(query),
        "has_aggregations": has_aggregation_functions(query),
        "query_pattern": detect_query_pattern(query),
        "path_variables": extract_path_variables(query)
    }
```

**Integration:**
```python
# In app.py /query/graph endpoint
cypher_metadata = parse_cypher_query(query)
allowed, reason, policy = cerbos_client.check_resource_access(
    user_id=str(current_user.id),
    user_email=current_user.email,
    user_roles=user_roles,
    resource_kind="cypher_query",
    resource_id="graph-query",
    action="execute",
    attributes={
        "query_type": query_type,
        "query": query,
        **cypher_metadata  # Include parsed metadata
    }
)
```

#### 5.2.2 Enhance User Attributes

**Recommendation:**
Add user attributes to the principal schema and database:

```sql
-- Add user attributes table
CREATE TABLE user_attributes (
    user_id INTEGER REFERENCES users(id),
    team VARCHAR(100),
    region VARCHAR(100),
    clearance_level INTEGER,
    department VARCHAR(100),
    PRIMARY KEY (user_id)
);
```

**Update Cerbos Principal:**
```python
# In cerbos_client.py
principal = engine_pb2.Principal(
    id=user_id,
    roles=set(user_roles),
    attr={
        "email": Value(string_value=user_email),
        "team": Value(string_value=user_team),
        "region": Value(string_value=user_region),
        "clearance_level": Value(number_value=user_clearance_level)
    }
)
```

#### 5.2.3 Implement Resource Attribute Extraction

**Recommendation:**
Extract resource attributes from Cypher query WHERE clauses:

```python
def extract_resource_attributes(query: str) -> Dict[str, any]:
    """Extract resource attributes from Cypher WHERE clauses."""
    attributes = {}
    
    # Extract customer risk_rating
    if re.search(r'risk_rating\s*[=<>]', query, re.IGNORECASE):
        # Extract threshold
        pass
    
    # Extract transaction amount
    if re.search(r'amount\s*[=<>]', query, re.IGNORECASE):
        # Extract threshold
        pass
    
    # Extract PEP flag
    if re.search(r'pep_flag\s*=\s*true', query, re.IGNORECASE):
        attributes["pep_flag"] = True
    
    return attributes
```

#### 5.2.4 Implement Query Complexity Limits

**Recommendation:**
Add query complexity analysis and limits:

```python
def analyze_query_complexity(query: str) -> Dict[str, int]:
    """Analyze Cypher query complexity."""
    return {
        "max_depth": calculate_traversal_depth(query),
        "estimated_nodes": estimate_node_count(query),
        "estimated_edges": estimate_edge_count(query),
        "path_count": count_path_variables(query)
    }
```

**Policy Enforcement:**
```yaml
# In cypher_query.yaml
rules:
  - actions: ["execute"]
    effect: EFFECT_ALLOW
    roles: ["aml_analyst"]
    condition:
      match:
        expr: |
          R.attr.max_depth <= 3 &&
          R.attr.estimated_nodes <= 1000 &&
          R.attr.estimated_edges <= 5000
```

---

## 6. Implementation Plan

### Phase 1: Cypher Query Parsing (Week 1-2)

**Objectives:**
- Implement Cypher query parser to extract metadata
- Integrate parser into authorization flow
- Update Cerbos resource attributes with parsed metadata

**Tasks:**
1. Create `cypher_parser.py` module
2. Implement node label extraction
3. Implement relationship type extraction
4. Implement traversal depth calculation
5. Integrate parser into `/query/graph` endpoint
6. Update Cerbos resource attributes
7. Add unit tests

**Deliverables:**
- Cypher query parser module
- Updated authorization flow
- Unit tests

### Phase 2: Enhanced RBAC (Week 2-3)

**Objectives:**
- Create role-based query restrictions
- Implement role hierarchy using derived roles
- Add role-based complexity limits

**Tasks:**
1. Create `cypher_query.yaml` Cerbos policy
2. Define role-based restrictions (depth, node types, etc.)
3. Implement derived roles for role hierarchy
4. Update user roles in database
5. Test role-based restrictions
6. Update documentation

**Deliverables:**
- New Cerbos policies
- Role hierarchy implementation
- Updated role definitions

### Phase 3: Enhanced ABAC (Week 3-4)

**Objectives:**
- Add user attributes (team, region, clearance)
- Extract resource attributes from queries
- Implement attribute-based restrictions

**Tasks:**
1. Add user_attributes table to database
2. Update user model and API
3. Extract resource attributes from Cypher queries
4. Update Cerbos principal schema
5. Create attribute-based policies
6. Test attribute-based restrictions
7. Update documentation

**Deliverables:**
- User attributes schema
- Resource attribute extraction
- Attribute-based policies

### Phase 4: Query Complexity Analysis (Week 4-5)

**Objectives:**
- Implement query complexity analysis
- Add complexity-based restrictions
- Add query execution limits

**Tasks:**
1. Implement complexity analysis functions
2. Add complexity limits to policies
3. Implement query execution time limits
4. Add result set size limits
5. Test complexity restrictions
6. Update documentation

**Deliverables:**
- Complexity analysis module
- Complexity-based policies
- Execution limits

### Phase 5: Testing and Documentation (Week 5-6)

**Objectives:**
- Comprehensive testing
- Documentation updates
- Performance optimization

**Tasks:**
1. Integration tests for all scenarios
2. Performance testing
3. Security testing
4. Update README and documentation
5. Create migration guide
6. Performance optimization

**Deliverables:**
- Test suite
- Updated documentation
- Performance benchmarks

---

## 7. Example Implementations

### 7.1 Enhanced Cypher Query Authorization

```python
# In app.py
@API.post("/query/graph")
def execute_graph_query(
    query_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a graph query with enhanced RBAC/ABAC."""
    query = query_data.get("query", "").strip()
    query_type = query_data.get("type", "cypher").lower()
    
    if query_type != "cypher":
        # Gremlin queries use existing authorization
        return execute_gremlin_query(query_data, current_user, db)
    
    # Parse Cypher query
    from cypher_parser import parse_cypher_query, extract_resource_attributes, analyze_query_complexity
    
    cypher_metadata = parse_cypher_query(query)
    resource_attrs = extract_resource_attributes(query)
    complexity = analyze_query_complexity(query)
    
    # Get user attributes
    user_attrs = get_user_attributes(db, current_user.id)
    user_roles = get_user_roles(db, current_user.id)
    
    # Check authorization with enhanced attributes
    cerbos_client = get_cerbos_client()
    allowed, reason, policy = cerbos_client.check_resource_access(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind="cypher_query",
        resource_id="graph-query",
        action="execute",
        attributes={
            "query_type": query_type,
            "query": query,
            **cypher_metadata,
            **resource_attrs,
            **complexity
        },
        principal_attributes=user_attrs  # New parameter
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    
    # Execute query...
```

### 7.2 Enhanced Cerbos Policy

```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "cypher_query"
  schemas:
    principalSchema:
      ref: cerbos:///aml_principal.json
    resourceSchema:
      ref: cerbos:///cypher_query_resource.json
  rules:
    # Junior Analyst: Limited access
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst_junior"]
      condition:
        match:
          expr: |
            R.attr.max_depth <= 2 &&
            !R.attr.node_labels.contains("SAR") &&
            !R.attr.node_labels.contains("CaseNote") &&
            R.attr.estimated_nodes <= 500
    
    # Senior Analyst: Moderate access
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst_senior"]
      condition:
        match:
          expr: |
            R.attr.max_depth <= 4 &&
            !R.attr.node_labels.contains("SAR") &&
            R.attr.estimated_nodes <= 2000
    
    # Manager: Full access
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_manager"]
      condition:
        match:
          expr: R.attr.max_depth <= 6
    
    # Team-based restrictions
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst", "aml_manager"]
      condition:
        match:
          expr: |
            R.attr.node_labels.contains("Customer") &&
            P.attr.team == R.attr.customer_team
    
    # Clearance-based restrictions for PEP customers
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst", "aml_manager"]
      condition:
        match:
          expr: |
            R.attr.pep_flag == true &&
            P.attr.clearance_level >= 3
    
    # Amount threshold restrictions
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst"]
      condition:
        match:
          expr: |
            R.attr.transaction_amount <= 100000 ||
            P.attr.clearance_level >= 2
```

---

## 8. Success Metrics

### 8.1 Security Metrics
- ✅ All Cypher queries are authorized before execution
- ✅ Role-based restrictions enforced on 100% of queries
- ✅ Attribute-based restrictions enforced where applicable
- ✅ Zero unauthorized access to restricted resources

### 8.2 Functionality Metrics
- ✅ Query parsing accuracy > 95%
- ✅ Authorization decision time < 50ms
- ✅ Support for all common Cypher patterns
- ✅ Comprehensive test coverage > 80%

### 8.3 Usability Metrics
- ✅ Clear error messages for denied queries
- ✅ Documentation for policy authors
- ✅ Easy role and attribute management

---

## 9. Conclusion

The current Cerbos integration provides a solid foundation for PBAC, with basic RBAC coverage for SQL and graph queries. However, there are significant gaps in RBAC and ABAC coverage specifically for Cypher queries:

1. **RBAC Gaps**: Limited role granularity, no role-based query restrictions, no role hierarchy
2. **ABAC Gaps**: No Cypher query parsing, limited user attributes, no resource attribute extraction, no complexity analysis

The proposed implementation plan addresses these gaps through:
- Cypher query parsing and metadata extraction
- Enhanced role-based restrictions
- User and resource attribute extraction
- Query complexity analysis and limits

This will provide enterprise-grade access control for Cypher queries while maintaining the flexibility and power of Cerbos's policy engine.
