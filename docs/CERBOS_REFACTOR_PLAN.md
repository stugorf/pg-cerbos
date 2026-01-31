# Cerbos Refactoring Plan

## Executive Summary

This plan refactors the MVP to use **Cerbos** as the core policy and authorization service, removing Envoy, OPA, and the cerbos-adapter. The new architecture integrates Cerbos directly into the policy-registry backend, simplifying the system while maintaining all functionality.

## Current Architecture Issues

1. **Complex Authorization Chain**: Client → Envoy → cerbos-adapter → Cerbos → Trino
2. **Multiple Policy Systems**: Both OPA (Rego) and Cerbos (YAML) exist in parallel
3. **Unnecessary Proxy Layer**: Envoy adds complexity without clear benefit for this use case
4. **Adapter Overhead**: cerbos-adapter adds translation layer that's not needed
5. **Policy Editor Mismatch**: UI edits Rego policies but system uses Cerbos

## Target Architecture

```
┌─────────────────┐    ┌─────────────────┐
│   Auth UI       │    │  Policy Editor   │
│   (Login/Admin) │    │  (Cerbos YAML)   │
└─────────┬───────┘    └─────────┬───────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────────────┐
│         Policy Registry Backend                │
│         (FastAPI + Cerbos Integration)         │
│  ┌──────────────────────────────────────────┐ │
│  │  • Authentication (JWT)                  │ │
│  │  • Cerbos Policy Management              │ │
│  │  • Query Authorization (Cerbos Check)   │ │
│  │  • Query Execution (Trino Client)        │ │
│  └──────────────────────────────────────────┘ │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│              Cerbos PDP                         │
│         (Port 3593)                             │
│  ┌──────────────────────────────────────────┐ │
│  │  • Policy Evaluation                      │ │
│  │  • Resource Policies (postgres/iceberg)  │ │
│  │  • Principal Policies (if needed)        │ │
│  └──────────────────────────────────────────┘ │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│              Trino Cluster                      │
│  ┌─────────────────┐    ┌─────────────────┐   │
│  │   Coordinator   │    │     Worker      │   │
│  │   (Port 8080)   │◄──►│   (Port 8081)   │   │
│  └─────────────────┘    └─────────────────┘   │
└─────────┬───────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────┐
│         Data Sources                            │
│  • PostgreSQL (Port 5434)                      │
│  • Iceberg via MinIO (Port 9000) + Nessie      │
└─────────────────────────────────────────────────┘
```

## Key Changes

### 1. Remove Services
- ❌ **Envoy** - No longer needed, backend handles authorization directly
- ❌ **cerbos-adapter** - No longer needed, direct Cerbos integration
- ❌ **OPA** - Replaced by Cerbos

### 2. Modify Services
- ✅ **policy-registry-backend** - Add direct Cerbos integration
- ✅ **policy-registry-frontend** - Update to edit Cerbos YAML policies
- ✅ **Cerbos** - Keep as core PDP

### 3. Keep Services
- ✅ **Trino** - Core query engine
- ✅ **PostgreSQL** - Data storage + demo data
- ✅ **MinIO + Nessie** - Iceberg storage
- ✅ **query-results-db** - Query result storage

## Implementation Plan

### Phase 1: Backend Integration

#### 1.1 Add Cerbos Client to Backend
- Install `cerbos` Python SDK
- Create Cerbos client wrapper
- Integrate authorization checks into query endpoints

#### 1.2 Update Query Execution Flow
```python
# New flow:
1. User submits query via UI
2. Backend extracts user info (from JWT)
3. Backend calls Cerbos CheckResources API
4. If allowed, execute query on Trino
5. Return results to UI
```

#### 1.3 Remove OPA Integration
- Remove OPA client code
- Remove OPA policy endpoints
- Remove OPA bundle generation

### Phase 2: Policy Management

#### 2.1 Cerbos Policy Storage
- Store Cerbos policies in PostgreSQL (as YAML text)
- Add endpoints for CRUD operations on Cerbos policies
- Add policy validation using Cerbos SDK

#### 2.2 Policy Sync to Cerbos
- Watch policy changes in database
- Sync policies to Cerbos via Admin API or file system
- Support hot-reloading of policies

### Phase 3: Frontend Updates

#### 3.1 Policy Editor
- Replace Monaco Rego editor with YAML editor
- Add Cerbos policy templates
- Add syntax validation for Cerbos policies
- Add policy testing interface

#### 3.2 Query Interface
- Enhance existing query UI
- Add real-time query execution
- Display authorization results
- Show query results in table format

### Phase 4: Cleanup

#### 4.1 Remove Unused Services
- Remove Envoy service from compose.yml
- Remove cerbos-adapter service
- Remove OPA service
- Remove envoy/ directory

#### 4.2 Update Documentation
- Update README.md
- Update architecture diagrams
- Create Cerbos-specific documentation

## Detailed Implementation Steps

### Step 1: Update Backend Dependencies

**File: `policy-registry/backend/requirements.txt`**
```python
# Add Cerbos SDK
cerbos>=0.50.0
```

### Step 2: Create Cerbos Client Module

**File: `policy-registry/backend/cerbos_client.py`**
```python
from cerbos.sdk.client import CerbosClient
from cerbos.sdk.model import Principal, Resource, CheckResourcesRequest
import os

CERBOS_URL = os.getenv("CERBOS_URL", "http://cerbos:3593")

class CerbosAuthz:
    def __init__(self):
        self.client = CerbosClient(CERBOS_URL)
    
    def check_query_permission(self, user_id: str, user_email: str, 
                               user_roles: list, method: str, path: str, 
                               query_body: str) -> bool:
        """Check if user can execute query."""
        # Determine resource kind from query
        resource_kind = "iceberg" if "iceberg." in query_body.lower() else "postgres"
        
        principal = Principal(
            id=user_id,
            roles=user_roles,
            attr={"email": user_email}
        )
        
        resource = Resource(
            kind=resource_kind,
            id=f"query-{user_id}",
            attr={
                "method": method,
                "path": path,
                "body": query_body,
                "catalog": resource_kind
            }
        )
        
        request = CheckResourcesRequest()
        request.principal = principal
        request.resources = [resource]
        request.actions = ["query"]
        
        response = self.client.check_resources(request)
        return response.results[0].actions["query"] == "EFFECT_ALLOW"
```

### Step 3: Update Query Endpoint

**File: `policy-registry/backend/app.py`**
```python
from cerbos_client import CerbosAuthz

cerbos_authz = CerbosAuthz()

@API.post("/query")
async def execute_query(query_data: dict, current_user: User = Depends(get_current_user)):
    """Execute SQL query with Cerbos authorization."""
    sql_query = query_data.get("query", "")
    
    # Check authorization with Cerbos
    user_roles = get_user_roles(db, current_user.id)
    allowed = cerbos_authz.check_query_permission(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        method="POST",
        path="/v1/statement",
        query_body=sql_query
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail="Query not authorized by Cerbos policy")
    
    # Execute query on Trino
    # ... existing Trino execution code ...
```

### Step 4: Add Cerbos Policy Management

**File: `policy-registry/backend/app.py`**
```python
@API.get("/cerbos/policies")
def list_cerbos_policies(current_user: User = Depends(get_current_admin_user)):
    """List all Cerbos policies."""
    # Read policies from cerbos/policies directory or database
    pass

@API.post("/cerbos/policies")
def create_cerbos_policy(policy_data: dict, current_user: User = Depends(get_current_admin_user)):
    """Create a new Cerbos policy."""
    # Validate YAML
    # Store in database
    # Sync to Cerbos
    pass

@API.put("/cerbos/policies/{policy_id}")
def update_cerbos_policy(policy_id: str, policy_data: dict, current_user: User = Depends(get_current_admin_user)):
    """Update a Cerbos policy."""
    pass

@API.delete("/cerbos/policies/{policy_id}")
def delete_cerbos_policy(policy_id: str, current_user: User = Depends(get_current_admin_user)):
    """Delete a Cerbos policy."""
    pass
```

### Step 5: Update Frontend Policy Editor

**File: `policy-registry/frontend/static/policy-editor.html`**
```html
<!doctype html>
<html>
<head>
    <title>Cerbos Policy Editor</title>
    <script>window.API_BASE = "http://localhost:8082";</script>
    <script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js"></script>
</head>
<body>
    <header>
        <h1>Cerbos Policy Editor</h1>
    </header>
    <main>
        <section>
            <button id="refresh">Refresh Policies</button>
            <button id="save">Save Policy</button>
            <select id="policy-type">
                <option value="resource">Resource Policy</option>
                <option value="principal">Principal Policy</option>
            </select>
            <select id="resource-kind">
                <option value="postgres">PostgreSQL</option>
                <option value="iceberg">Iceberg</option>
            </select>
        </section>
        <div id="editor"></div>
        <pre id="output"></pre>
    </main>
    <script src="cerbos-policy-editor.js"></script>
</body>
</html>
```

### Step 6: Update compose.yml

**Remove:**
- `envoy` service
- `cerbos-adapter` service  
- `opa` service

**Update:**
- `policy-registry-backend`: Add `CERBOS_URL` environment variable
- `cerbos`: Ensure policies directory is mounted correctly

### Step 7: Update Query UI

**File: `policy-registry/frontend/static/query.html`**
```html
<!doctype html>
<html>
<head>
    <title>SQL Query Interface</title>
    <link rel="stylesheet" href="styles.css" />
</head>
<body>
    <header>
        <h1>SQL Query Interface</h1>
        <div id="user-info"></div>
    </header>
    <main>
        <section id="query-section">
            <textarea id="query-input" placeholder="Enter SQL query..."></textarea>
            <button id="execute-query">Execute Query</button>
            <button id="clear-query">Clear</button>
        </section>
        <section id="results-section">
            <div id="query-status"></div>
            <table id="results-table"></table>
        </section>
    </main>
    <script src="query.js"></script>
</body>
</html>
```

## Migration Checklist

### Backend
- [ ] Add Cerbos SDK to requirements.txt
- [ ] Create cerbos_client.py module
- [ ] Update query endpoint to use Cerbos
- [ ] Add Cerbos policy management endpoints
- [ ] Remove OPA integration code
- [ ] Update authentication to work with Cerbos

### Frontend
- [ ] Create Cerbos policy editor (YAML)
- [ ] Update query interface UI
- [ ] Add query execution functionality
- [ ] Add results display
- [ ] Remove OPA policy editor

### Infrastructure
- [ ] Remove Envoy from compose.yml
- [ ] Remove cerbos-adapter from compose.yml
- [ ] Remove OPA from compose.yml
- [ ] Update Cerbos service configuration
- [ ] Update port mappings
- [ ] Update health checks

### Documentation
- [ ] Update README.md
- [ ] Update architecture diagrams
- [ ] Create Cerbos policy guide
- [ ] Update API documentation
- [ ] Create migration guide

### Testing
- [ ] Test Cerbos authorization
- [ ] Test policy CRUD operations
- [ ] Test query execution flow
- [ ] Test UI functionality
- [ ] Test with different user roles

## Benefits of New Architecture

1. **Simplified**: Removed 3 services (Envoy, adapter, OPA)
2. **Direct Integration**: Cerbos called directly from backend
3. **Unified Policies**: Single policy system (Cerbos YAML)
4. **Better UX**: Native Cerbos policy editor
5. **Easier Maintenance**: Fewer moving parts
6. **Better Performance**: Fewer network hops
7. **Easier Debugging**: Direct Cerbos integration

## Risks and Mitigation

### Risk 1: Policy Migration
- **Risk**: Existing OPA policies need to be converted to Cerbos
- **Mitigation**: Create conversion script, manual review process

### Risk 2: Feature Parity
- **Risk**: Some OPA features may not have Cerbos equivalents
- **Mitigation**: Review Cerbos capabilities, adjust policies as needed

### Risk 3: Testing Coverage
- **Risk**: New integration may have bugs
- **Mitigation**: Comprehensive testing, gradual rollout

## Timeline Estimate

- **Phase 1 (Backend)**: 2-3 days
- **Phase 2 (Policy Management)**: 1-2 days
- **Phase 3 (Frontend)**: 2-3 days
- **Phase 4 (Cleanup)**: 1 day
- **Testing & Documentation**: 1-2 days

**Total**: ~7-11 days

## Next Steps

1. Review and approve this plan
2. Set up development branch
3. Begin Phase 1 implementation
4. Test incrementally
5. Deploy when ready
