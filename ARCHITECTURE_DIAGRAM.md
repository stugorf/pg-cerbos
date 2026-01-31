# UES MVP Component Architecture Diagram

## System Overview
The UES MVP is a unified entitlements solution with comprehensive authentication and authorization, built using microservices architecture with Docker containers.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                    CLIENT LAYER                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────┐                    ┌─────────────────────────────┐                                                        │
│  │      Authentication UI      │                    │      Policy Editor UI       │                                                        │
│  │      (Port 8083/auth.html) │                    │      (Port 8083/index.html) │                                                        │
│  │                             │                    │                             │                                                        │
│  │ • User Login/Logout         │                    │ • Monaco-based Editor       │                                                        │
│  │ • User Management           │                    │ • Policy Management         │                                                        │
│  │ • Role Assignment           │                    │ • Bundle Management         │                                                        │
│  │ • Permission Management     │                    │ • Policy Validation         │                                                        │
│  └─────────────────────────────┘                    └─────────────────────────────┘                                                        │
│           │                                                    │                                                                              │
│           │ HTTP/HTTPS                                        │ HTTP/HTTPS                                                                   │
│           ▼                                                    ▼                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                 GATEWAY LAYER                                                                                │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                        ENVOY PROXY (Port 8081)                                                                        │   │
│  │                                                                                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              ext_authz Filter                                                                                  │ │   │
│  │  │                         (Authorization Check)                                                                                  │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • Intercepts all requests                                                                                                      │ │   │
│  │  │ • Forwards to OPA for policy evaluation                                                                                        │ │   │
│  │  │ • Applies authorization headers                                                                                                │ │   │
│  │  │ • Routes to appropriate backend services                                                                                       │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                                                                              │
│           │ HTTP/HTTPS                                                                                                                   │
│           ▼                                                                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                               AUTHORIZATION LAYER                                                                           │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                        OPA ENGINE (Port 8181)                                                                         │   │
│  │                                                                                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              Policy Evaluation Engine                                                                           │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • Rego Policy Language                                                                                                          │ │   │
│  │  │ • Role-based Access Control                                                                                                     │ │   │
│  │  │ • Resource-level Permissions                                                                                                    │ │   │
│  │  │ • Field-level Security                                                                                                          │ │   │
│  │  │ • Dynamic Policy Updates                                                                                                        │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                                                                              │
│           │ HTTP/HTTPS                                                                                                                   │
│           ▼                                                                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                               APPLICATION LAYER                                                                             │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                    POLICY REGISTRY BACKEND (Port 8082)                                                               │   │
│  │                                                                                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              FastAPI Application                                                                                │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • User Authentication & Management                                                                                              │ │   │
│  │  │ • Role & Permission Management                                                                                                  │ │   │
│  │  │ • Policy CRUD Operations                                                                                                        │ │   │
│  │  │ • Bundle Management                                                                                                             │ │   │
│  │  │ • Query Execution & Results                                                                                                     │ │   │
│  │  │ • JWT Token Management                                                                                                          │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                                                                              │
│           │ HTTP/HTTPS                                                                                                                   │
│           ▼                                                                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                               DATA PROCESSING LAYER                                                                        │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                        TRINO CLUSTER                                                                                  │   │
│  │                                                                                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              COORDINATOR (Port 8080)                                                                             │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • Query Planning & Coordination                                                                                                 │ │   │
│  │  │ • Access Control Enforcement                                                                                                     │ │   │
│  │  │ • Field Masking & Row Filtering                                                                                                 │ │   │
│  │  │ • Catalog Management                                                                                                            │ │   │
│  │  │ • Query Routing                                                                                                                 │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                    │                                                                                                │   │
│  │                                    │ Internal Communication                                                                          │   │
│  │                                    ▼                                                                                                │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              WORKER NODE                                                                                        │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • Query Execution                                                                                                               │ │   │
│  │  │ • Data Processing                                                                                                               │ │   │
│  │  │ • Row-level Security                                                                                                            │ │   │
│  │  │ • Performance Optimization                                                                                                      │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                                                                              │
│           │ SQL Queries                                                                                                                 │
│           ▼                                                                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                 STORAGE LAYER                                                                              │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                    POSTGRESQL DATABASES                                                                              │   │
│  │                                                                                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              MAIN DATABASE (Port 5434)                                                                           │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • policy_store: OPA policies, bundles, versions                                                                                 │ │   │
│  │  │ • demo_data: Sample person data (names, SSNs, job titles)                                                                       │ │   │
│  │  │ • users: User accounts and authentication                                                                                       │ │   │
│  │  │ • roles: Role definitions                                                                                                       │ │   │
│  │  │ • permissions: Resource and field-level permissions                                                                             │ │   │
│  │  │ • user_roles: User-role assignments                                                                                             │ │   │
│  │  │ • role_permissions: Role-permission assignments                                                                                 │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                    │                                                                                                │   │
│  │                                    │ Separate Database                                                                               │   │
│  │                                    ▼                                                                                                │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              QUERY RESULTS DB (Port 5433)                                                                        │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • queries: Query metadata and status                                                                                           │ │   │
│  │  │ • query_columns: Result column definitions                                                                                     │ │   │
│  │  │ • query_results: Actual query result data                                                                                      │ │   │
│  │  │ • query_stats: Query performance statistics                                                                                     │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│           │                                                                                                                              │
│           │ S3 API                                                                                                                      │
│           ▼                                                                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                                    OBJECT STORAGE                                                                                    │   │
│  │                                                                                                                                    │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              MINIO (Ports 9000, 9001)                                                                           │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • S3-compatible object storage                                                                                                  │ │   │
│  │  │ • Iceberg table data files                                                                                                      │ │   │
│  │  │ • Parquet/ORC file storage                                                                                                      │ │   │
│  │  │ • Web console for management                                                                                                    │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  │                                    │                                                                                                │   │
│  │                                    │ Catalog Service                                                                                 │   │
│  │                                    ▼                                                                                                │   │
│  │  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐ │   │
│  │  │                              NESSIE (Port 19120)                                                                                │ │   │
│  │  │                                                                                                                                │ │   │
│  │  │ • Iceberg catalog service                                                                                                       │ │   │
│  │  │ • Table metadata management                                                                                                     │ │   │
│  │  │ • Schema evolution tracking                                                                                                     │ │   │
│  │  │ • Version control for tables                                                                                                    │ │   │
│  │  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Service Hosting Relationships

### 1. **Authentication & Authorization Services**
- **Hosted by**: `policy-registry-backend` container
- **Data Storage**: PostgreSQL main database (`users`, `roles`, `permissions` tables)
- **Connections**: 
  - Frontend UIs (Port 8083)
  - OPA engine (Port 8181)
  - PostgreSQL (Port 5434)

### 2. **Policy Management Services**
- **Hosted by**: `policy-registry-backend` container
- **Data Storage**: PostgreSQL main database (`policies` table)
- **Connections**:
  - OPA engine (Port 8181) - pulls policies via bundles
  - Frontend policy editor (Port 8083)
  - PostgreSQL (Port 5434)

### 3. **Query Processing Services**
- **Hosted by**: `policy-registry-backend` container
- **Data Storage**: PostgreSQL query results database (Port 5433)
- **Connections**:
  - Trino coordinator (Port 8080)
  - Frontend query interface (Port 8083)
  - Query results database (Port 5433)

### 4. **Data Query Engine**
- **Hosted by**: `trino-coordinator` and `trino-worker` containers
- **Data Sources**:
  - PostgreSQL (Port 5434) - demo_data and policy_store
  - Iceberg via MinIO (Port 9000) and Nessie (Port 19120)
- **Connections**:
  - Envoy proxy (Port 8081)
  - Policy registry backend (Port 8082)

### 5. **Authorization Enforcement**
- **Hosted by**: `opa` container
- **Policy Source**: Policy registry backend (Port 8082)
- **Connections**:
  - Envoy proxy (Port 8081)
  - Policy registry backend (Port 8082)

### 6. **Request Routing & Authorization**
- **Hosted by**: `envoy` container
- **Authorization**: OPA engine (Port 8181)
- **Backend**: Trino coordinator (Port 8080)
- **Connections**:
  - Client applications
  - OPA engine (Port 8181)
  - Trino coordinator (Port 8080)

## Data Flow Architecture

### Authentication Flow
1. User authenticates via UI (Port 8083)
2. Policy registry backend validates credentials against PostgreSQL
3. JWT token issued and returned to client
4. Token used for subsequent API calls

### Authorization Flow
1. Client request to Envoy proxy (Port 8081)
2. Envoy forwards to OPA for policy evaluation
3. OPA evaluates policies from policy registry
4. If authorized, request forwarded to Trino
5. Trino applies field-level and row-level security
6. Query executed against appropriate data sources

### Policy Management Flow
1. Admin creates/updates policies via UI (Port 8083)
2. Policy registry backend stores in PostgreSQL
3. OPA periodically polls for policy updates
4. New policies automatically loaded and enforced

### Query Execution Flow
1. User submits SQL query via UI
2. Policy registry backend validates permissions
3. Query sent to Trino via Envoy
4. Trino executes with security policies applied
5. Results stored in query results database
6. Results returned to user interface

## Network Architecture

### Container Network: `trino-net`
All services communicate over a dedicated Docker network with internal DNS resolution:
- `postgres` → `mvp-postgres:5432`
- `query-results-db` → `mvp-query-results:5432`
- `trino-coordinator` → `mvp-trino-coordinator:8080`
- `policy-registry-backend` → `mvp-policy-registry:8080`
- `opa` → `mvp-opa:8181`
- `envoy` → `mvp-envoy:8081`

### External Port Mapping
- **8080**: Trino UI and API
- **8081**: Envoy proxy (client entry point)
- **8082**: Policy registry backend API
- **8083**: Frontend UIs (authentication + policy editor)
- **5434**: PostgreSQL main database
- **5433**: PostgreSQL query results database
- **8181**: OPA API
- **9000/9001**: MinIO S3 API and console
- **19120**: Nessie catalog service

## Security Architecture

### Authentication Layers
1. **JWT-based authentication** for API access
2. **Password hashing** for user credentials
3. **Session management** with token expiration

### Authorization Layers
1. **Role-based access control (RBAC)** at user level
2. **Resource-level permissions** for databases and tables
3. **Field-level security** for sensitive data columns
4. **Row-level filtering** based on user context

### Policy Enforcement Points
1. **API Gateway**: Envoy proxy with OPA integration
2. **Query Engine**: Trino with field masking and row filtering
3. **Application Layer**: Policy registry backend with permission checks
4. **Database Layer**: PostgreSQL with role-based access

This architecture provides a comprehensive, secure, and scalable unified entitlements solution with clear separation of concerns and robust security enforcement at multiple layers. 