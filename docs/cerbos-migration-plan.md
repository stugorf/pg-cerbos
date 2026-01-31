# Cerbos Migration Plan

## Executive Summary

This document outlines a comprehensive plan for migrating the UES MVP from **Open Policy Agent (OPA)** to **Cerbos** as the Policy Decision Point (PDP). Cerbos provides a more developer-friendly YAML-based policy language, native GitOps support, and better integration patterns for microservices architectures.

## Current Architecture Analysis

### Current Components to Replace

1. **OPA Service** (`mvp-opa`)
   - Evaluates Rego policies
   - Pulls bundles from policy-registry-backend
   - Exposes REST API at `http://opa:8181/v1/data/envoy/authz/allow`

2. **Rego Policies** (`opa/*.rego`)
   - `authz-policy-fixed.rego` - Main authorization logic
   - `field_security.rego` - Field-level access control
   - `bootstrap.rego` - Initialization
   - `test_policies.rego` - Test cases

3. **Policy Registry Backend** (`policy-registry/backend`)
   - Serves OPA bundles (`/bundles/main.tar.gz`)
   - Stores policies in Postgres (`policies` table)
   - Policy CRUD operations

4. **Envoy Integration** (`envoy/envoy.yaml`)
   - `ext_authz` filter calls OPA
   - Path: `/v1/data/envoy/authz/allow`
   - Passes request context (headers, body, method, path)

### Current Authorization Model

**Roles:**
- `admin` - Full system access
- `full_access_user` - All data, all fields
- `postgres_only_user` - Postgres only, all fields
- `restricted_user` - All data, no SSN fields

**Resources:**
- `postgres` - PostgreSQL database access
- `iceberg` - Iceberg table access
- `field` - Field-level permissions (e.g., SSN)

**Actions:**
- `query` - Execute SQL queries
- `read` - Read data (future)
- `write` - Write/modify data (future)

## Cerbos Architecture Overview

### Key Cerbos Concepts

1. **Resource Policies** - Define access rules for resources (e.g., `postgres`, `iceberg`)
2. **Principal Policies** - Define user-specific permissions
3. **Derived Roles** - Compute roles from principal attributes
4. **Schemas** - Validate resource and principal attributes
5. **Conditions** - Express complex authorization logic

### Cerbos Deployment Options

- **Standalone Service** - HTTP/gRPC service (similar to current OPA)
- **Sidecar** - Deployed alongside each service instance
- **DaemonSet** - One instance per Kubernetes node

## Migration Strategy

### Phase 1: Setup and Infrastructure (Week 1)

#### 1.1 Add Cerbos Service

**Tasks:**
- Add Cerbos container to `compose.yml`
- Configure Cerbos to use GitOps (pull policies from Git) or file-based storage
- Expose Cerbos API (HTTP: 3593, gRPC: 3593)
- Set up health checks

**Files to Modify:**
- `compose.yml` - Add Cerbos service
- `Justfile` - Add Cerbos management commands

**Cerbos Configuration:**
```yaml
# cerbos/cerbos.yaml
server:
  httpListenAddr: ":3593"
  grpcListenAddr: ":3593"
storage:
  driver: "git"
  git:
    protocol: "https"
    repo: "https://github.com/stugorf/pg-cerbos.git"
    branch: "main"
    auth:
      ssh:
        privateKeyFile: "/etc/cerbos/ssh_key"
```

#### 1.2 Create Cerbos Policy Directory Structure

**Directory Structure:**
```
cerbos/
├── cerbos.yaml              # Cerbos configuration
├── policies/
│   ├── _schemas/
│   │   ├── principal.json   # Principal (user) schema
│   │   └── resource.json    # Resource schema
│   ├── derived_roles.yaml   # Role derivation rules
│   ├── resource_policies/
│   │   ├── postgres.yaml    # PostgreSQL access policies
│   │   └── iceberg.yaml     # Iceberg access policies
│   └── principal_policies/
│       └── admin.yaml       # Admin-specific policies
└── tests/
    └── test_suite.yaml      # Policy tests
```

### Phase 2: Policy Migration (Week 1-2)

#### 2.1 Convert Rego Policies to Cerbos YAML

**Current Rego Logic → Cerbos Equivalent:**

**Admin Access (Rego):**
```rego
allow = {
  "allowed": true,
  "headers": {"x-authz": "admin-access", ...}
} if {
  "admin" in user_roles
}
```

**Cerbos Equivalent:**
```yaml
# cerbos/policies/resource_policies/postgres.yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "postgres"
  rules:
    - actions: ["query", "read", "write"]
      effect: EFFECT_ALLOW
      roles: ["admin"]
```

**Full Access User (Rego):**
```rego
allow = {
  "allowed": true,
  "headers": {"x-authz": "full-access", ...}
} if {
  "full_access_user" in user_roles
  input.attributes.request.http.method == "POST"
  startswith(input.attributes.request.http.path, "/v1/statement")
}
```

**Cerbos Equivalent:**
```yaml
# cerbos/policies/resource_policies/postgres.yaml
rules:
  - actions: ["query"]
    effect: EFFECT_ALLOW
    roles: ["full_access_user"]
    condition:
      match:
        expr: request.method == "POST" && request.path.startsWith("/v1/statement")
```

**Postgres-Only User (Rego):**
```rego
allow = {
  "allowed": true,
  ...
} if {
  "postgres_only_user" in user_roles
  input.attributes.request.http.method == "POST"
  startswith(input.attributes.request.http.path, "/v1/statement")
  not contains_iceberg_query(parsed_body)
}
```

**Cerbos Equivalent:**
```yaml
# cerbos/policies/resource_policies/postgres.yaml
rules:
  - actions: ["query"]
    effect: EFFECT_ALLOW
    roles: ["postgres_only_user"]
    condition:
      match:
        expr: request.method == "POST" && 
              request.path.startsWith("/v1/statement") &&
              !request.body.contains("iceberg.")
```

**Restricted User (SSN Field Restriction):**
```rego
allow = {
  "allowed": false,
  "body": "Access denied: You are not authorized to access SSN fields..."
} if {
  "restricted_user" in user_roles
  contains_ssn_query(parsed_body)
}
```

**Cerbos Equivalent:**
```yaml
# cerbos/policies/resource_policies/postgres.yaml
rules:
  - actions: ["query"]
    effect: EFFECT_DENY
    roles: ["restricted_user"]
    condition:
      match:
        expr: request.body.matches("(?i).*\\b(ssn|SSN|social_security|social_security_number|ssn_number)\\b.*")
```

#### 2.2 Define Schemas

**Principal Schema:**
```json
// cerbos/policies/_schemas/principal.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "email": {
      "type": "string",
      "format": "email"
    },
    "roles": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["admin", "full_access_user", "postgres_only_user", "restricted_user"]
      }
    }
  },
  "required": ["id", "email", "roles"]
}
```

**Resource Schema:**
```json
// cerbos/policies/_schemas/resource.json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "kind": {
      "type": "string",
      "enum": ["postgres", "iceberg", "field"]
    },
    "catalog": {
      "type": "string"
    },
    "schema": {
      "type": "string"
    },
    "table": {
      "type": "string"
    },
    "field": {
      "type": "string"
    },
    "query": {
      "type": "string"
    }
  },
  "required": ["kind"]
}
```

### Phase 3: Integration Updates (Week 2)

#### 3.1 Update Envoy Configuration

**Current (OPA):**
```yaml
http_service:
  server_uri:
    uri: http://opa:8181
    path_prefix: /v1/data/envoy/authz/allow
```

**New (Cerbos):**
```yaml
http_service:
  server_uri:
    uri: http://cerbos:3593
    path_prefix: /api/check
  # Or use gRPC for better performance:
grpc_service:
  google_grpc:
    target_uri: cerbos:3593
    stat_prefix: cerbos
```

**Cerbos Request Format:**
```json
{
  "principal": {
    "id": "user-123",
    "roles": ["full_access_user"],
    "attr": {
      "email": "fullaccess@ues-mvp.com"
    }
  },
  "resource": {
    "kind": "postgres",
    "id": "query-001",
    "attr": {
      "catalog": "postgres",
      "query": "SELECT * FROM postgres.public.person"
    }
  },
  "actions": ["query"]
}
```

#### 3.2 Update Policy Registry Backend

**Changes Required:**
- Replace OPA bundle generation with Cerbos policy management
- Update API endpoints to work with Cerbos policies
- Modify policy editor to support YAML instead of Rego
- Update policy storage schema (if needed)

**New API Endpoints:**
- `POST /cerbos/policies` - Create/update Cerbos policy
- `GET /cerbos/policies` - List policies
- `POST /cerbos/policies/validate` - Validate policy syntax
- `POST /cerbos/policies/test` - Run policy tests

#### 3.3 Update Application Code

**Current (OPA):**
```python
opa_url = "http://opa:8181/v1/data/envoy/authz/allow"
opa_input = {
    "input": {
        "attributes": {
            "request": {
                "http": {
                    "method": "POST",
                    "path": "/v1/statement",
                    "headers": {...},
                    "body": sql_query
                }
            }
        }
    }
}
```

**New (Cerbos):**
```python
cerbos_url = "http://cerbos:3593/api/check"
cerbos_request = {
    "principal": {
        "id": str(current_user.id),
        "roles": get_user_roles(db, current_user.id),
        "attr": {
            "email": current_user.email
        }
    },
    "resource": {
        "kind": "postgres" if "postgres" in sql_query.lower() else "iceberg",
        "id": f"query-{query_id}",
        "attr": {
            "catalog": catalog,
            "schema": schema,
            "query": sql_query
        }
    },
    "actions": ["query"]
}
```

### Phase 4: Testing and Validation (Week 2-3)

#### 4.1 Policy Testing

**Cerbos Test Suite:**
```yaml
# cerbos/tests/test_suite.yaml
name: "UES MVP Authorization Tests"
description: "Test suite for postgres and iceberg access control"

principals:
  admin:
    id: "1"
    roles: ["admin"]
    attr:
      email: "admin@ues-mvp.com"
  
  full_access:
    id: "2"
    roles: ["full_access_user"]
    attr:
      email: "fullaccess@ues-mvp.com"
  
  postgres_only:
    id: "3"
    roles: ["postgres_only_user"]
    attr:
      email: "postgresonly@ues-mvp.com"
  
  restricted:
    id: "4"
    roles: ["restricted_user"]
    attr:
      email: "restricted@ues-mvp.com"

resources:
  postgres_query:
    kind: "postgres"
    id: "query-001"
    attr:
      catalog: "postgres"
      query: "SELECT * FROM postgres.public.person"
  
  iceberg_query:
    kind: "iceberg"
    id: "query-002"
    attr:
      catalog: "iceberg"
      query: "SELECT * FROM iceberg.demo.employee_performance"
  
  ssn_query:
    kind: "postgres"
    id: "query-003"
    attr:
      catalog: "postgres"
      query: "SELECT ssn FROM postgres.public.person"

tests:
  - name: "Admin can query postgres"
    principals: ["admin"]
    resources: ["postgres_query"]
    actions: ["query"]
    expected: EFFECT_ALLOW
  
  - name: "Full access user can query both"
    principals: ["full_access"]
    resources: ["postgres_query", "iceberg_query"]
    actions: ["query"]
    expected: EFFECT_ALLOW
  
  - name: "Postgres-only user cannot query iceberg"
    principals: ["postgres_only"]
    resources: ["iceberg_query"]
    actions: ["query"]
    expected: EFFECT_DENY
  
  - name: "Restricted user cannot query SSN"
    principals: ["restricted"]
    resources: ["ssn_query"]
    actions: ["query"]
    expected: EFFECT_DENY
```

#### 4.2 Integration Testing

**Test Scenarios:**
1. Envoy → Cerbos authorization flow
2. Policy Registry → Cerbos policy updates
3. Application → Cerbos permission checks
4. Field-level restrictions (SSN masking)
5. Catalog-level restrictions (postgres vs iceberg)

### Phase 5: Deployment and Rollout (Week 3-4)

#### 5.1 Parallel Running (Dual Mode)

**Strategy:**
- Run both OPA and Cerbos simultaneously
- Route a percentage of traffic to Cerbos
- Compare authorization decisions
- Gradually increase Cerbos traffic

**Implementation:**
- Add feature flag for Cerbos
- Log authorization decisions from both systems
- Alert on discrepancies

#### 5.2 Full Migration

**Steps:**
1. Switch Envoy to use Cerbos
2. Remove OPA service
3. Remove Rego policy files
4. Update documentation
5. Update Justfile commands

### Phase 6: Cleanup and Documentation (Week 4)

#### 6.1 Remove OPA Components

**Files to Remove:**
- `opa/` directory
- OPA-related code in `policy-registry/backend`
- OPA bundle generation logic

#### 6.2 Update Documentation

**Files to Update:**
- `README.md` - Update architecture diagrams and instructions
- `ARCHITECTURE_DIAGRAM.md` - Replace OPA with Cerbos
- `DEVELOPER_SETUP.md` - Update setup instructions
- `Justfile` - Update commands

## Detailed Implementation Plan

### Step 1: Add Cerbos Service

**File: `compose.yml`**
```yaml
cerbos:
  image: ghcr.io/cerbos/cerbos:latest
  container_name: mvp-cerbos
  command:
    - server
    - --set=server.httpListenAddr=:3593
    - --set=server.grpcListenAddr=:3593
  volumes:
    - ./cerbos/policies:/policies:ro
    - ./cerbos/cerbos.yaml:/config/cerbos.yaml:ro
  ports:
    - "3593:3593"
  networks: [trino-net]
  healthcheck:
    test: ["CMD", "cerbos", "healthcheck", "--http", "http://localhost:3593"]
    interval: 10s
    timeout: 5s
    retries: 3
```

### Step 2: Create Initial Cerbos Policies

**File: `cerbos/policies/resource_policies/postgres.yaml`**
```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "postgres"
  importDerivedRoles:
    - common_roles
  rules:
    - actions: ["query", "read", "write"]
      effect: EFFECT_ALLOW
      roles: ["admin"]
    
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["full_access_user"]
      condition:
        match:
          expr: request.method == "POST" && request.path.startsWith("/v1/statement")
    
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["postgres_only_user"]
      condition:
        match:
          expr: request.method == "POST" && 
                request.path.startsWith("/v1/statement") &&
                !request.body.contains("iceberg.")
    
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["restricted_user"]
      condition:
        match:
          expr: request.method == "POST" && 
                request.path.startsWith("/v1/statement") &&
                !request.body.matches("(?i).*\\b(ssn|SSN|social_security)\\b.*")
    
    - actions: ["query"]
      effect: EFFECT_DENY
      roles: ["restricted_user"]
      condition:
        match:
          expr: request.body.matches("(?i).*\\b(ssn|SSN|social_security)\\b.*")
```

**File: `cerbos/policies/resource_policies/iceberg.yaml`**
```yaml
apiVersion: api.cerbos.dev/v1
resourcePolicy:
  version: "default"
  resource: "iceberg"
  importDerivedRoles:
    - common_roles
  rules:
    - actions: ["query", "read", "write"]
      effect: EFFECT_ALLOW
      roles: ["admin"]
    
    - actions: ["query"]
      effect: EFFECT_ALLOW
      roles: ["full_access_user", "restricted_user"]
      condition:
        match:
          expr: request.method == "POST" && request.path.startsWith("/v1/statement")
    
    - actions: ["query"]
      effect: EFFECT_DENY
      roles: ["postgres_only_user"]
```

### Step 3: Update Envoy Configuration

**File: `envoy/envoy.yaml` (modify ext_authz filter)**
```yaml
http_filters:
  - name: envoy.filters.http.ext_authz
    typed_config:
      "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
      transport_api_version: V3
      with_request_body:
        allow_partial_message: true
        max_request_bytes: 8192
        pack_as_bytes: false
      failure_mode_allow: false
      http_service:
        server_uri:
          uri: http://cerbos:3593
          cluster: cerbos_cluster
          timeout: 1s
        path_prefix: /api/check
        authorization_request:
          headers_to_add:
            - header:
                key: "Content-Type"
                value: "application/json"
        authorization_response:
          allowed_upstream_headers:
            patterns:
              - exact: x-user-id
              - exact: x-user-email
              - exact: x-user-roles
              - exact: x-authz
  # ... rest of filters

clusters:
  # ... existing clusters
  
  - name: cerbos_cluster
    connect_timeout: 1s
    type: LOGICAL_DNS
    lb_policy: ROUND_ROBIN
    load_assignment:
      cluster_name: cerbos_cluster
      endpoints:
        - lb_endpoints:
            - endpoint:
                address: { socket_address: { address: cerbos, port_value: 3593 } }
```

**Note:** Envoy's `ext_authz` filter expects a specific request/response format. We'll need to create an adapter service or use Envoy's Lua filter to transform requests to Cerbos format.

### Step 4: Create Envoy-Cerbos Adapter (Alternative Approach)

Since Envoy's `ext_authz` has a specific format, we have two options:

**Option A: Use Envoy Lua Filter**
- Transform Envoy request to Cerbos format
- Call Cerbos API
- Transform Cerbos response to Envoy format

**Option B: Create Adapter Service**
- Lightweight service that translates between Envoy and Cerbos formats
- Deploy as sidecar or separate service

**Recommended: Option B (Adapter Service)**

**File: `adapter/Dockerfile`**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY adapter.py .
CMD ["python", "adapter.py"]
```

**File: `adapter/adapter.py`**
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
import json

app = FastAPI()

CERBOS_URL = "http://cerbos:3593/api/check"

@app.post("/check")
async def check(request: Request):
    """Adapter endpoint that translates Envoy ext_authz requests to Cerbos format."""
    body = await request.body()
    envoy_request = json.loads(body) if body else {}
    
    # Extract principal info from Envoy request
    headers = envoy_request.get("attributes", {}).get("request", {}).get("http", {}).get("headers", {})
    user_id = headers.get("x-user-id", "")
    user_email = headers.get("x-user-email", "")
    user_roles = headers.get("x-user-roles", "").split(",") if headers.get("x-user-roles") else []
    
    # Extract resource info
    http_req = envoy_request.get("attributes", {}).get("request", {}).get("http", {})
    method = http_req.get("method", "")
    path = http_req.get("path", "")
    query_body = http_req.get("body", "")
    
    # Determine resource kind
    resource_kind = "iceberg" if "iceberg" in query_body.lower() else "postgres"
    
    # Build Cerbos request
    cerbos_request = {
        "principal": {
            "id": user_id,
            "roles": user_roles,
            "attr": {
                "email": user_email
            }
        },
        "resource": {
            "kind": resource_kind,
            "id": f"query-{user_id}",
            "attr": {
                "method": method,
                "path": path,
                "body": query_body
            }
        },
        "actions": ["query"]
    }
    
    # Call Cerbos
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                CERBOS_URL,
                json=cerbos_request,
                timeout=1.0
            )
            cerbos_response = response.json()
            
            # Transform Cerbos response to Envoy format
            allowed = cerbos_response.get("results", [{}])[0].get("actions", {}).get("query") == "EFFECT_ALLOW"
            
            return JSONResponse({
                "allowed": allowed,
                "headers": {
                    "x-authz": "cerbos",
                    "x-user-id": user_id,
                    "x-user-email": user_email,
                    "x-user-roles": ",".join(user_roles)
                },
                "body": "" if allowed else "Access denied by Cerbos policy"
            })
        except Exception as e:
            # Fail open or closed based on security requirements
            return JSONResponse({
                "allowed": False,
                "headers": {},
                "body": f"Authorization error: {str(e)}"
            }, status_code=500)
```

### Step 5: Update Policy Registry Backend

**New Endpoints:**
```python
@API.post("/cerbos/policies")
def create_cerbos_policy(policy_data: dict, current_user: User = Depends(get_current_user)):
    """Create or update a Cerbos policy."""
    # Validate YAML syntax
    # Store in Git or file system
    # Trigger Cerbos reload
    pass

@API.post("/cerbos/policies/validate")
def validate_cerbos_policy(policy_data: dict):
    """Validate Cerbos policy syntax."""
    # Use Cerbos CLI or API to validate
    pass

@API.post("/cerbos/policies/test")
def test_cerbos_policy(test_data: dict):
    """Run policy tests."""
    # Use Cerbos test API
    pass
```

## Migration Checklist

### Pre-Migration
- [ ] Review Cerbos documentation and examples
- [ ] Set up Cerbos development environment
- [ ] Create test Cerbos policies
- [ ] Validate policy syntax and logic

### Phase 1: Infrastructure
- [ ] Add Cerbos service to `compose.yml`
- [ ] Create Cerbos policy directory structure
- [ ] Configure Cerbos storage (Git or filesystem)
- [ ] Add Cerbos health checks
- [ ] Update `Justfile` with Cerbos commands

### Phase 2: Policy Migration
- [ ] Convert `authz-policy-fixed.rego` to Cerbos YAML
- [ ] Convert `field_security.rego` to Cerbos YAML
- [ ] Create principal and resource schemas
- [ ] Create derived roles (if needed)
- [ ] Write Cerbos test suite
- [ ] Validate all policies

### Phase 3: Integration
- [ ] Create Envoy-Cerbos adapter service
- [ ] Update Envoy configuration
- [ ] Update policy-registry-backend for Cerbos
- [ ] Update application code to use Cerbos
- [ ] Update frontend policy editor for YAML

### Phase 4: Testing
- [ ] Unit tests for Cerbos policies
- [ ] Integration tests for Envoy → Cerbos flow
- [ ] End-to-end tests for all user roles
- [ ] Performance testing
- [ ] Security testing

### Phase 5: Deployment
- [ ] Deploy Cerbos alongside OPA (parallel running)
- [ ] Route test traffic to Cerbos
- [ ] Compare authorization decisions
- [ ] Gradually increase Cerbos traffic
- [ ] Full cutover to Cerbos

### Phase 6: Cleanup
- [ ] Remove OPA service
- [ ] Remove Rego policy files
- [ ] Remove OPA-related code
- [ ] Update all documentation
- [ ] Update `Justfile` commands

## Risk Mitigation

### Risks and Mitigation Strategies

1. **Policy Logic Differences**
   - **Risk:** Cerbos policies may not exactly match Rego logic
   - **Mitigation:** Comprehensive test suite, parallel running, gradual rollout

2. **Performance Impact**
   - **Risk:** Cerbos may have different latency characteristics
   - **Mitigation:** Performance testing, sidecar deployment option

3. **Integration Complexity**
   - **Risk:** Envoy integration may require adapter
   - **Mitigation:** Use adapter service pattern, well-tested

4. **Policy Management**
   - **Risk:** Different policy storage and management
   - **Mitigation:** Update policy registry, maintain GitOps workflow

## Benefits of Migration

1. **Developer Experience**
   - YAML policies are more readable than Rego
   - Better IDE support and tooling
   - Easier for non-developers to understand

2. **GitOps Native**
   - Built-in Git integration
   - Policy versioning and rollback
   - CI/CD integration

3. **Performance**
   - gRPC support for lower latency
   - Optimized for high-throughput scenarios
   - Sidecar deployment option

4. **Ecosystem**
   - Growing community and support
   - Better documentation and examples
   - Active development

## Timeline Estimate

- **Week 1:** Infrastructure setup and initial policy migration
- **Week 2:** Integration updates and adapter development
- **Week 3:** Testing and validation
- **Week 4:** Deployment and cleanup

**Total:** 4 weeks for complete migration

## Next Steps

1. Review and approve this migration plan
2. Set up Cerbos development environment
3. Create initial Cerbos policies for one resource (postgres)
4. Test Cerbos policies against existing test cases
5. Build Envoy-Cerbos adapter
6. Begin parallel running phase

## References

- [Cerbos Documentation](https://docs.cerbos.dev/)
- [Cerbos Quickstart](https://docs.cerbos.dev/cerbos/latest/quickstart)
- [Cerbos Policy Authoring](https://docs.cerbos.dev/cerbos/latest/policies/overview)
- [Cerbos Envoy Integration](https://docs.cerbos.dev/cerbos/latest/deployment/kubernetes-sidecar)
