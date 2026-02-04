# Phase 3: Enhanced ABAC Implementation Plan

## Overview

Phase 3 implements Attribute-Based Access Control (ABAC) for **Cypher queries only** by adding user attributes (team, region, clearance_level, department) and creating attribute-based policies that restrict access based on these attributes combined with resource attributes extracted from queries.

**⚠️ IMPORTANT: This phase REQUIRES enhancing the Cypher parser** to extract `customer_team` and `customer_region` from queries. The current parser does not extract these attributes, which are essential for team-based and region-based ABAC rules (Rules 7 and 10). See Task 8 for details.

**Scope:** This phase focuses exclusively on Cypher graph queries. SQL query ABAC (Postgres/Iceberg) will be implemented in a future phase, but will leverage the same user attributes infrastructure built here.

## Current State

### ✅ Completed (Phase 1 & 2)
- Cypher query parsing extracts node labels, relationships, depth, patterns
- Resource attribute extraction (risk_rating, transaction_amount, pep_flag, severity, status)
- Role-based access control with hierarchy (junior → senior → manager)
- Role-based depth, node, and relationship restrictions
- Complexity analysis (estimated nodes/edges)

### ⚠️ Pending (Phase 3)
- User attributes storage and retrieval
- Principal schema with user attributes
- **Cypher parser enhancements** (REQUIRED: extract customer_team and customer_region)
- Attribute-based policy rules
- Integration of user attributes into authorization flow

## Objectives

1. **Add User Attributes Support**
   - Create database schema for user attributes
   - Update backend models to support user attributes
   - Create API endpoints for managing user attributes

2. **Update Principal Schema**
   - Extend `aml_principal.json` to include team, region, clearance_level, department
   - Ensure schema validation works with new attributes

3. **Implement Attribute-Based Policies for Cypher Queries**
   - Team-based restrictions (users can only query their team's cases/customers)
   - Region-based restrictions (users can only query their region's data)
   - Clearance-based restrictions (PEP access requires high clearance)
   - Amount-based restrictions (high-value transactions require clearance)

4. **Integrate User Attributes into Authorization Flow**
   - Fetch user attributes from database
   - Pass user attributes to Cerbos as principal attributes (Cypher queries only)
   - Test attribute-based restrictions

**Note:** SQL query ABAC will be implemented in a future phase. The user attributes infrastructure built in this phase will be reused for SQL queries.

## Implementation Tasks

### Task 1: Database Schema for User Attributes

**File:** `postgres/init/31-user-attributes-schema.sql` (NEW)

**Changes:**
- Create `user_attributes` table with columns:
  - `user_id` (FK to users.id, PRIMARY KEY)
  - `team` (VARCHAR(100), nullable)
  - `region` (VARCHAR(100), nullable)
  - `clearance_level` (INTEGER, nullable, default 1)
  - `department` (VARCHAR(100), nullable)
  - `created_at` (TIMESTAMP)
  - `updated_at` (TIMESTAMP)
- Add indexes for performance
- Add trigger for `updated_at` timestamp

**SQL:**
```sql
CREATE TABLE IF NOT EXISTS user_attributes (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    team VARCHAR(100),
    region VARCHAR(100),
    clearance_level INTEGER DEFAULT 1,
    department VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_attributes_team ON user_attributes(team);
CREATE INDEX IF NOT EXISTS idx_user_attributes_region ON user_attributes(region);
CREATE INDEX IF NOT EXISTS idx_user_attributes_clearance ON user_attributes(clearance_level);

CREATE TRIGGER update_user_attributes_updated_at 
    BEFORE UPDATE ON user_attributes 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
```

### Task 2: Seed Data for User Attributes

**File:** `postgres/init/41-user-attributes-seed-data.sql` (NEW)

**Changes:**
- Insert user attributes for existing users
- Create demo users with different attribute combinations for testing

**Example Seed Data:**
```sql
-- Admin user: full clearance, no team restrictions
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'admin@pg-cerbos.com'), 
     NULL, NULL, 5, 'IT')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Demo users for AML testing
-- Team A analyst (junior, low clearance)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'analyst_team_a@pg-cerbos.com'), 
     'Team A', 'US', 1, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Team B analyst (senior, medium clearance)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'analyst_team_b@pg-cerbos.com'), 
     'Team B', 'EU', 2, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Manager (high clearance, no team restrictions)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'manager@pg-cerbos.com'), 
     NULL, NULL, 4, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;
```

### Task 3: Update Backend Models

**File:** `policy-registry/backend/auth_models.py`

**Changes:**
- Add `UserAttributes` SQLAlchemy model
- Add relationship from `User` to `UserAttributes`
- Add Pydantic models for user attributes (create, update, response)

**Code:**
```python
class UserAttributes(Base):
    __tablename__ = "user_attributes"
    
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    team = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    clearance_level = Column(Integer, default=1, nullable=True)
    department = Column(String(100), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=text('now()'))
    
    # Relationship
    user = relationship("User", backref="attributes")
    
    def __repr__(self):
        return f"<UserAttributes(user_id={self.user_id}, team='{self.team}', clearance={self.clearance_level})>"

# Add to User model (if not already present)
# User.attributes = relationship("UserAttributes", uselist=False, back_populates="user")

# Pydantic models
class UserAttributesCreate(BaseModel):
    team: Optional[str] = None
    region: Optional[str] = None
    clearance_level: Optional[int] = 1
    department: Optional[str] = None

class UserAttributesUpdate(BaseModel):
    team: Optional[str] = None
    region: Optional[str] = None
    clearance_level: Optional[int] = None
    department: Optional[str] = None

class UserAttributesResponse(BaseModel):
    user_id: int
    team: Optional[str]
    region: Optional[str]
    clearance_level: Optional[int]
    department: Optional[str]
    created_at: datetime
    updated_at: datetime
```

### Task 4: Add Helper Function to Fetch User Attributes

**File:** `policy-registry/backend/auth_utils.py`

**Changes:**
- Add function `get_user_attributes(db, user_id)` to fetch user attributes as dict

**Code:**
```python
def get_user_attributes(db: Session, user_id: int) -> dict:
    """
    Get user attributes for Cerbos principal.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Dictionary of user attributes (team, region, clearance_level, department)
        Returns empty dict with defaults if user has no attributes record
    """
    from auth_models import UserAttributes
    
    user_attrs = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    
    if user_attrs:
        return {
            "team": user_attrs.team,
            "region": user_attrs.region,
            "clearance_level": user_attrs.clearance_level or 1,
            "department": user_attrs.department,
            "is_active": True  # Can be derived from User model if needed
        }
    else:
        # Return defaults if no attributes record exists
        return {
            "team": None,
            "region": None,
            "clearance_level": 1,
            "department": None,
            "is_active": True
        }
```

### Task 5: Update Principal Schema

**File:** `cerbos/policies/_schemas/aml_principal.json`

**Changes:**
- Add `region`, `clearance_level`, `department` to schema
- Keep `team` and `is_active` (already present)

**Updated Schema:**
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "title": "AML Principal Attributes Schema",
  "description": "Schema for AML user principal attributes (attr object only). Note: 'id' and 'roles' are top-level principal fields, not attributes.",
  "properties": {
    "email": {
      "type": "string",
      "format": "email",
      "description": "User email address"
    },
    "team": {
      "type": "string",
      "description": "User's team assignment (e.g., 'Team A', 'Team B')"
    },
    "region": {
      "type": "string",
      "description": "User's region assignment (e.g., 'US', 'EU', 'APAC')"
    },
    "clearance_level": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5,
      "description": "User's security clearance level (1=lowest, 5=highest)"
    },
    "department": {
      "type": "string",
      "description": "User's department (e.g., 'AML', 'IT', 'Compliance')"
    },
    "is_active": {
      "type": "boolean",
      "description": "Whether the user account is active"
    }
  },
  "additionalProperties": true
}
```

### Task 6: Update Graph Query Endpoint

**File:** `policy-registry/backend/app.py`

**Changes:**
- In `/query/graph` endpoint, fetch user attributes using `get_user_attributes()`
- Pass user attributes to `cerbos_client.check_resource_access()` as `principal_attributes`

**Code Changes:**
```python
# Around line 689, after getting user_roles:
user_roles = get_user_roles(db, current_user.id)

# Add this:
from auth_utils import get_user_attributes
user_attributes = get_user_attributes(db, current_user.id)

# Update the check_resource_access call (around line 704):
allowed, reason, policy = cerbos_client.check_resource_access(
    user_id=str(current_user.id),
    user_email=current_user.email,
    user_roles=user_roles,
    resource_kind=resource_kind,
    resource_id="graph-query",
    action=action,
    attributes=cerbos_attributes,
    principal_attributes=user_attributes  # Add this parameter
)
```


### Task 7: Add Attribute-Based Policy Rules

**File:** `cerbos/policies/resource_policies/cypher_query.yaml`

**Changes:**
- Add attribute-based rules after existing RBAC rules
- Rules should check both principal attributes (P.attr) and resource attributes (R.attr)

**New Rules to Add:**
```yaml
    # ============================================================================
    # ATTRIBUTE-BASED ACCESS CONTROL (ABAC) RULES
    # ============================================================================
    
    # ============================================================================
    # RULE 7: Team-based customer access
    # Reasoning: Users can only query customers from their own team
    #   - Checks if query accesses Customer nodes
    #   - Requires user's team to match customer's team (extracted from query)
    #   - Allows managers (no team restriction) to access all customers
    # Test: "Team A analyst can query Team A customers" - PENDING
    # Test: "Team A analyst cannot query Team B customers" - PENDING
    # ============================================================================
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst", "aml_analyst_junior", "aml_analyst_senior"]
      condition:
        match:
          expr: |
            R.attr.node_labels.contains("Customer") &&
            (P.attr.team == R.attr.customer_team || P.attr.team == null)
    
    # ============================================================================
    # RULE 8: Clearance-based PEP access
    # Reasoning: PEP (Politically Exposed Person) customers require high clearance
    #   - Checks if query accesses customers with pep_flag = true
    #   - Requires clearance_level >= 3
    # Test: "Low clearance analyst cannot query PEP customers" - PENDING
    # Test: "High clearance analyst can query PEP customers" - PENDING
    # ============================================================================
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst", "aml_analyst_junior", "aml_analyst_senior", "aml_manager"]
      condition:
        match:
          expr: |
            R.attr.pep_flag == true &&
            P.attr.clearance_level >= 3
    
    # ============================================================================
    # RULE 9: Clearance-based high-value transaction access
    # Reasoning: High-value transactions require elevated clearance
    #   - Checks if query accesses transactions with amount > threshold
    #   - Requires clearance_level >= 2 for transactions > $100k
    #   - Requires clearance_level >= 3 for transactions > $500k
    # Test: "Low clearance analyst cannot query high-value transactions" - PENDING
    # Test: "Medium clearance analyst can query $100k transactions" - PENDING
    # ============================================================================
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst", "aml_analyst_junior", "aml_analyst_senior", "aml_manager"]
      condition:
        match:
          expr: |
            R.attr.transaction_amount_min != null &&
            (
              (R.attr.transaction_amount_min <= 100000) ||
              (R.attr.transaction_amount_min > 100000 && R.attr.transaction_amount_min <= 500000 && P.attr.clearance_level >= 2) ||
              (R.attr.transaction_amount_min > 500000 && P.attr.clearance_level >= 3)
            )
    
    # ============================================================================
    # RULE 10: Region-based access (optional, if region data is available)
    # Reasoning: Users can only query data from their assigned region
    #   - Checks if query accesses region-specific data
    #   - Requires user's region to match resource region
    # Test: "US analyst can query US customers" - PENDING
    # Test: "US analyst cannot query EU customers" - PENDING
    # ============================================================================
    - actions: ["execute"]
      effect: EFFECT_ALLOW
      roles: ["aml_analyst", "aml_analyst_junior", "aml_analyst_senior"]
      condition:
        match:
          expr: |
            R.attr.customer_region != null &&
            (P.attr.region == R.attr.customer_region || P.attr.region == null)
```

**Note:** Rules 7 and 10 **REQUIRE** extracting `customer_team` and `customer_region` from queries. The current parser does NOT extract these attributes, so this is a **REQUIRED** enhancement for ABAC to work.

### Task 8: Enhance Resource Attribute Extraction (REQUIRED)

**File:** `policy-registry/backend/cypher_parser.py`

**Status:** ⚠️ **REQUIRED** - Current parser does not extract `customer_team` or `customer_region`, which are needed for team-based and region-based ABAC rules.

**Changes:**
- **MUST** add extraction logic for `customer_team` and `customer_region`
- Extract from WHERE clauses like `c.team = 'Team A'` or `WHERE customer.team = 'Team B'`
- Extract from node property patterns like `{team: 'Team A'}` or `Customer {team: 'Team A'}`
- Handle various variable names (c, customer, cust, etc.)
- Support both equality and inequality operators (=, !=, IN, etc.)

**Code Addition (REQUIRED):**
```python
def extract_resource_attributes(query: str) -> Dict[str, Any]:
    # ... existing code (keep all existing extraction logic) ...
    
    for where_match in where_matches:
        where_clause = where_match.group(1)
        
        # ... existing extraction code for risk_rating, amount, pep_flag, etc. ...
        
        # Extract customer_team from WHERE clauses
        # Handles: c.team = 'Team A', customer.team = 'Team B', team = 'Team C'
        team_match = re.search(r'(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?team\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if team_match:
            attributes["customer_team"] = team_match.group(1).strip("'\"")
        
        # Extract customer_region from WHERE clauses
        # Handles: c.region = 'US', customer.region = 'EU', region = 'APAC'
        region_match = re.search(r'(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?region\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if region_match:
            attributes["customer_region"] = region_match.group(1).strip("'\"")
    
    # Also check node property patterns: {property: value}
    node_prop_pattern = r'\{([^}]+)\}'
    prop_matches = re.finditer(node_prop_pattern, query_normalized)
    for prop_match in prop_matches:
        props = prop_match.group(1)
        
        # ... existing extraction code for pep_flag, risk_rating from node properties ...
        
        # Extract customer_team from node properties
        # Handles: {team: 'Team A'}, Customer {team: 'Team B'}
        team_prop_match = re.search(r'team\s*:\s*[\'"]?([^\'"\s,}]+)[\'"]?', props, re.IGNORECASE)
        if team_prop_match:
            attributes["customer_team"] = team_prop_match.group(1).strip("'\"")
        
        # Extract customer_region from node properties
        # Handles: {region: 'US'}, Customer {region: 'EU'}
        region_prop_match = re.search(r'region\s*:\s*[\'"]?([^\'"\s,}]+)[\'"]?', props, re.IGNORECASE)
        if region_prop_match:
            attributes["customer_region"] = region_prop_match.group(1).strip("'\"")
    
    return attributes
```

**Testing Requirements:**
- Test extraction from WHERE clauses: `WHERE c.team = 'Team A'`
- Test extraction from node properties: `MATCH (c:Customer {team: 'Team A'})`
- Test extraction with different variable names: `customer.team`, `cust.team`
- Test extraction with different operators: `=`, `!=`, `IN`
- Test that existing extractions (pep_flag, amount, etc.) still work

### Task 9: Update Resource Schema (REQUIRED)

**File:** `cerbos/policies/_schemas/cypher_query_resource.json`

**Status:** ⚠️ **REQUIRED** - Schema must include these attributes for ABAC policies to work.

**Changes:**
- **MUST** add `customer_team` and `customer_region` to schema (not currently present)

**Schema Addition:**
```json
    "customer_team": {
      "type": "string",
      "description": "Customer team extracted from query filters"
    },
    "customer_region": {
      "type": "string",
      "description": "Customer region extracted from query filters"
    }
```

### Task 10: Create Test Suite for ABAC Rules

**File:** `cerbos/policies/tests/cypher_query_abac_test_suite.yaml` (NEW)

**Changes:**
- Create comprehensive test suite for attribute-based rules
- Test team-based, clearance-based, and region-based restrictions

**Test Structure:**
```yaml
apiVersion: api.cerbos.dev/v1
testSuite:
  name: "Cypher Query ABAC Test Suite"
  description: "Tests for attribute-based access control rules"
  
  tests:
    # Team-based access tests
    - name: "Team A analyst can query Team A customers"
      input:
        principals:
          - id: "analyst_team_a"
            roles: ["aml_analyst_junior"]
            attr:
              team: "Team A"
              clearance_level: 1
        resources:
          - kind: "cypher_query"
            id: "test-query-1"
            attr:
              query_type: "cypher"
              query: "MATCH (c:Customer {team: 'Team A'}) RETURN c"
              node_labels: ["Customer"]
              max_depth: 1
              customer_team: "Team A"
        actions: ["execute"]
      expected:
        - principal: "analyst_team_a"
          resource: "test-query-1"
          actions:
            execute: EFFECT_ALLOW
    
    - name: "Team A analyst cannot query Team B customers"
      input:
        principals:
          - id: "analyst_team_a"
            roles: ["aml_analyst_junior"]
            attr:
              team: "Team A"
              clearance_level: 1
        resources:
          - kind: "cypher_query"
            id: "test-query-2"
            attr:
              query_type: "cypher"
              query: "MATCH (c:Customer {team: 'Team B'}) RETURN c"
              node_labels: ["Customer"]
              max_depth: 1
              customer_team: "Team B"
        actions: ["execute"]
      expected:
        - principal: "analyst_team_a"
          resource: "test-query-2"
          actions:
            execute: EFFECT_DENY
    
    # Clearance-based PEP access tests
    - name: "Low clearance analyst cannot query PEP customers"
      input:
        principals:
          - id: "analyst_low_clearance"
            roles: ["aml_analyst_junior"]
            attr:
              team: "Team A"
              clearance_level: 1
        resources:
          - kind: "cypher_query"
            id: "test-query-3"
            attr:
              query_type: "cypher"
              query: "MATCH (c:Customer {pep_flag: true}) RETURN c"
              node_labels: ["Customer"]
              max_depth: 1
              pep_flag: true
        actions: ["execute"]
      expected:
        - principal: "analyst_low_clearance"
          resource: "test-query-3"
          actions:
            execute: EFFECT_DENY
    
    - name: "High clearance analyst can query PEP customers"
      input:
        principals:
          - id: "analyst_high_clearance"
            roles: ["aml_analyst_senior"]
            attr:
              team: "Team A"
              clearance_level: 3
        resources:
          - kind: "cypher_query"
            id: "test-query-4"
            attr:
              query_type: "cypher"
              query: "MATCH (c:Customer {pep_flag: true}) RETURN c"
              node_labels: ["Customer"]
              max_depth: 1
              pep_flag: true
        actions: ["execute"]
      expected:
        - principal: "analyst_high_clearance"
          resource: "test-query-4"
          actions:
            execute: EFFECT_ALLOW
    
    # Clearance-based transaction amount tests
    - name: "Low clearance analyst cannot query high-value transactions"
      input:
        principals:
          - id: "analyst_low_clearance"
            roles: ["aml_analyst_junior"]
            attr:
              team: "Team A"
              clearance_level: 1
        resources:
          - kind: "cypher_query"
            id: "test-query-5"
            attr:
              query_type: "cypher"
              query: "MATCH (t:Transaction) WHERE t.amount > 200000 RETURN t"
              node_labels: ["Transaction"]
              max_depth: 1
              transaction_amount_min: 200000
        actions: ["execute"]
      expected:
        - principal: "analyst_low_clearance"
          resource: "test-query-5"
          actions:
            execute: EFFECT_DENY
    
    - name: "Medium clearance analyst can query $100k transactions"
      input:
        principals:
          - id: "analyst_medium_clearance"
            roles: ["aml_analyst_senior"]
            attr:
              team: "Team A"
              clearance_level: 2
        resources:
          - kind: "cypher_query"
            id: "test-query-6"
            attr:
              query_type: "cypher"
              query: "MATCH (t:Transaction) WHERE t.amount > 150000 RETURN t"
              node_labels: ["Transaction"]
              max_depth: 1
              transaction_amount_min: 150000
        actions: ["execute"]
      expected:
        - principal: "analyst_medium_clearance"
          resource: "test-query-6"
          actions:
            execute: EFFECT_ALLOW
```

### Task 11: Add API Endpoints for User Attributes Management

**File:** `policy-registry/backend/app.py`

**Changes:**
- Add endpoints for CRUD operations on user attributes
- GET `/users/{user_id}/attributes` - Get user attributes
- PUT `/users/{user_id}/attributes` - Update user attributes
- POST `/users/{user_id}/attributes` - Create user attributes

**Code:**
```python
@API.get("/users/{user_id}/attributes", response_model=UserAttributesResponse)
def get_user_attributes_endpoint(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user attributes."""
    # Only allow users to view their own attributes, or admins to view any
    if current_user.id != user_id and not is_admin(db, current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this user's attributes")
    
    from auth_models import UserAttributes
    user_attrs = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    
    if not user_attrs:
        raise HTTPException(status_code=404, detail="User attributes not found")
    
    return user_attrs

@API.put("/users/{user_id}/attributes", response_model=UserAttributesResponse)
def update_user_attributes_endpoint(
    user_id: int,
    attributes_update: UserAttributesUpdate,
    current_user: User = Depends(get_current_admin_user),  # Only admins can update
    db: Session = Depends(get_db)
):
    """Update user attributes (admin only)."""
    from auth_models import UserAttributes
    
    user_attrs = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    
    if not user_attrs:
        # Create if doesn't exist
        user_attrs = UserAttributes(user_id=user_id)
        db.add(user_attrs)
    
    # Update fields
    update_data = attributes_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user_attrs, key, value)
    
    db.commit()
    db.refresh(user_attrs)
    
    return user_attrs
```

### Task 12: Update Documentation

**File:** `docs/CERBOS_RBAC_ABAC_SUMMARY.md`

**Changes:**
- Update Phase 3 status to COMPLETE
- Document new attribute-based rules
- Update implementation status section


## Testing Strategy

### Unit Tests
- Test `get_user_attributes()` function
- Test user attributes model CRUD operations
- Test resource attribute extraction enhancements

### Integration Tests
- Test attribute-based policies with Cerbos test suite
- Test graph query endpoint with user attributes
- Test API endpoints for user attributes management

### Manual Testing
- Create test users with different attribute combinations
- Execute queries that should be allowed/denied based on attributes
- Verify authorization decisions in logs

## Success Criteria

1. ✅ User attributes table created and seeded
2. ✅ Backend models support user attributes
3. ✅ Principal schema includes all user attributes
4. ✅ Graph query endpoint passes user attributes to Cerbos
5. ✅ Attribute-based policy rules implemented and tested
6. ✅ Test suite passes for all ABAC scenarios
7. ✅ Documentation updated

## Timeline

- **Week 1:** Tasks 1-5 (Database schema, models, principal schema)
- **Week 2:** Tasks 6-9 (Integration, policies, resource extraction)
- **Week 3:** Tasks 10-12 (Testing, API endpoints, documentation)

**Total: 3 weeks**

## Dependencies

- Phase 1 (Cypher Query Parsing) - ✅ Complete
- Phase 2 (Enhanced RBAC) - ✅ Complete
- Cerbos schema validation - ✅ Working
- PuppyGraph integration - ✅ Working

## Risks and Mitigations

1. **Risk:** Resource attribute extraction may not capture all team/region filters
   - **Mitigation:** Enhance parser with comprehensive regex patterns, add unit tests

2. **Risk:** Performance impact of fetching user attributes on every query
   - **Mitigation:** Cache user attributes in session or use database indexes

3. **Risk:** Complex CEL expressions may be hard to debug
   - **Mitigation:** Add comprehensive test cases, document expression logic clearly

## Next Steps After Phase 3

- Phase 4: Query Complexity Analysis (execution time limits, result set size limits)
- Phase 5: Testing & Documentation (integration tests, performance optimization)
- **Future Phase: SQL Query ABAC** - Extend user attributes infrastructure to SQL queries (Postgres/Iceberg) with team-based, region-based, and clearance-based policies