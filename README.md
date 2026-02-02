# PG CERBOS  
**Cerbos + Trino + Postgres + Iceberg + Authentication**

This repository provides a **production-ready unified entitlements solution** with **comprehensive authentication and authorization**.  
It demonstrates request-level access control using **Cerbos** as the core policy decision point, with policies stored as YAML files, enforced directly in the backend service. The system queries **Postgres** and **Iceberg** (MinIO + Nessie) through **Trino**.

---

## 🚀 Quick Start for New Developers

### Prerequisites
- Docker and Docker Compose installed
- Ports 8080-8083, 5434, 3593, 9000-9001, 19120 available

### 1. Start the Services
```bash
docker compose up -d
```

### 2. Initialize the Complete System
```bash
just init
```

This single command ensures everything is properly set up:
- ✅ **PostgreSQL**: Demo data, policy store, and authentication tables
- ✅ **Iceberg**: Demo schema and sample tables  
- ✅ **Authentication**: Users, roles, and permissions configured
- ✅ **Policies**: Cerbos policies loaded and validated
- ✅ **Trino**: Health check and cleanup of hanging queries

### 3. Access the System
- **Main Dashboard**: http://localhost:8083/auth.html
  - **SQL Query Tab**: Execute SQL queries with Cerbos authorization
  - **Policy Management Tab**: Create, edit, and manage Cerbos YAML policies
  - **Cerbos Logs Tab**: View real-time authorization decisions and audit logs
  - **User/Role/Permission Management Tabs**: Admin functions for access control
- **Trino UI**: http://localhost:8080 (direct Trino access)
- **MinIO Console**: http://localhost:9001 (S3 storage for Iceberg)
- **Test Users**: See [Authentication Section](#-authentication--authorization-system) below

### 4. Test Queries
```sql
-- PostgreSQL demo data (10 records with names, SSNs, job titles)
SELECT * FROM postgres.public.person LIMIT 3;

-- Iceberg demo data (1 test record)
SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC;
```

**Note**: All demo queries work immediately without semicolons (Trino requirement).

---

## ✨ Architecture

- **Trino** – federated SQL engine querying Postgres and Iceberg (coordinator + worker nodes)
- **Postgres** – stores demo data (`demo_data`), policies (`policy_store`), and authentication data (`users`, `roles`, `permissions`)
- **Query Results DB** – separate Postgres instance for storing query execution logs and results
- **MinIO** – S3-compatible object store for Iceberg tables  
- **Nessie** – catalog service for Iceberg  
- **Cerbos** – core policy decision point (PDP) for authorization as a service, using YAML policies (Policy as Code)
- **Policy Registry Backend** – FastAPI service with authentication, user management, Cerbos policy editor, query interface, and authorization logging
- **Policy Registry Frontend** – Web UI with authentication, SQL query interface, Cerbos policy management, and authorization logs viewer
- **Authentication System** – JWT-based auth with role-based access control (RBAC)
- **SQL Query Interface** – Web-based SQL editor with real-time results and Cerbos authorization

### Component Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          User Interface Layer                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │   Auth UI        │  │  Policy Editor   │  │  SQL Query UI    │      │
│  │  (Login/Admin)   │  │  (Cerbos YAML)   │  │  (Query Builder) │      │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘      │
│           │                      │                     │                  │
│           └──────────────────────┼─────────────────────┘                  │
│                                  │                                         │
│                          ┌───────▼────────┐                                │
│                          │  Cerbos Logs   │                                │
│                          │  Viewer Tab    │                                │
│                          └────────────────┘                                │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Policy Registry Frontend (Nginx)                         │
│                         Port 8083                                           │
│              Serves static HTML/CSS/JS files                                │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │ HTTP Requests
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              Policy Registry Backend (FastAPI)                              │
│                         Port 8082                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  • Authentication (JWT)                                              │  │
│  │  • User/Role/Permission Management                                   │  │
│  │  • Cerbos Policy Management (CRUD)                                    │  │
│  │  • SQL Query Execution (Trino Client)                                 │  │
│  │  • Authorization Decision Logging                                     │  │
│  │  • Cerbos Logs API                                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────┬───────────────────────────────────────┬───────────────────────────┘
          │                                       │
          │ Authorization Check                    │ Query Execution
          │ (gRPC)                                │ (HTTP)
          ▼                                       ▼
┌──────────────────────────┐        ┌───────────────────────────────────────┐
│   Cerbos PDP (gRPC)      │        │        Trino Cluster                  │
│   Port 3593              │        │  ┌─────────────────┐                  │
│                          │        │  │  Coordinator   │                  │
│  ┌────────────────────┐  │        │  │  Port 8080     │◄──►              │
│  │  Policy Evaluation │  │        │  │                 │                  │
│  │  (YAML Policies)  │  │        │  │ • Query Planning│                  │
│  │                    │  │        │  │ • Coordination  │                  │
│  │  • Resource Policy │  │        │  └─────────────────┘                  │
│  │  • Principal Policy│  │        │  ┌─────────────────┐                  │
│  │  • Audit Logging   │  │        │  │    Worker       │                  │
│  └────────────────────┘  │        │  │  (internal)     │                  │
│                          │        │  │                 │                  │
│  Policy Storage:         │        │  │ • Query Exec    │                  │
│  /policies/*.yaml        │        │  │ • Data Processing│                │
└──────────────────────────┘        │  └─────────────────┘                  │
                                    └───────────┬───────────────────────────┘
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Data Storage Layer                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │   Postgres       │  │ Query Results DB │  │     MinIO         │      │
│  │   Port 5434      │  │   Port 5433      │  │   Port 9000/9001  │      │
│  │                  │  │                  │  │                   │      │
│  │ • demo_data      │  │ • query_results  │  │ • S3 Storage     │      │
│  │ • policy_store   │  │ • query_logs     │  │ • Iceberg Data    │      │
│  │ • nessie         │  │ • query_stats    │  │ • Parquet Files  │      │
│  │ • users/roles    │  │                  │  │                   │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                             │
│  ┌──────────────────┐                                                      │
│  │     Nessie       │                                                      │
│  │   Port 19120     │                                                      │
│  │                  │                                                      │
│  │ • Catalog        │                                                      │
│  │ • Version Control│                                                      │
│  │ • Schema Mgmt    │                                                      │
│  └──────────────────┘                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Cerbos Authorization Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SQL Query Authorization Flow                              │
└─────────────────────────────────────────────────────────────────────────────┘

    User submits SQL query via Web UI
              │
              ▼
    ┌─────────────────────┐
    │  Frontend (auth.html)│
    │  • Validates JWT     │
    │  • Sends query +     │
    │    auth headers      │
    └──────────┬───────────┘
               │
               │ POST /query
               │ Headers: Authorization: Bearer <token>
               ▼
    ┌─────────────────────────────────────┐
    │  Policy Registry Backend            │
    │  (FastAPI - Port 8082)              │
    │                                     │
    │  1. Extract user info from JWT      │
    │     • user_id                       │
    │     • user_email                    │
    │     • user_roles                    │
    │                                     │
    │  2. Parse SQL query                 │
    │     • Determine resource_kind       │
    │       (postgres/iceberg)            │
    │     • Extract query metadata        │
    └──────────┬──────────────────────────┘
               │
               │ Authorization Check Required
               ▼
    ┌─────────────────────────────────────┐
    │  Cerbos Authorization Check         │
    │  (gRPC - Port 3593)                 │
    │                                     │
    │  Request:                           │
    │  • Principal:                       │
    │     - id: user_id                   │
    │     - roles: [user_roles]           │
    │     - attr: {email: user_email}     │
    │  • Resource:                        │
    │     - kind: postgres/iceberg        │
    │     - id: query-{user_id}           │
    │     - attr: {query, method, path}   │
    │  • Action: "query"                  │
    │                                     │
    │  Cerbos evaluates policies:        │
    │  • Loads YAML policies from        │
    │    /policies/*.yaml                 │
    │  • Matches resource policies       │
    │  • Evaluates rules based on        │
    │    principal roles/attributes      │
    │  • Returns: ALLOW or DENY           │
    └──────────┬──────────────────────────┘
               │
               │ Decision: ALLOW / DENY
               ▼
    ┌─────────────────────────────────────┐
    │  Policy Registry Backend             │
    │                                     │
    │  IF DENY:                           │
    │    • Log decision                   │
    │    • Return HTTP 403                │
    │    • Error: "Query not authorized"  │
    │                                     │
    │  IF ALLOW:                          │
    │    • Log decision                   │
    │    • Forward query to Trino         │
    └──────────┬──────────────────────────┘
               │
               │ POST /v1/statement
               │ Body: SQL query
               ▼
    ┌─────────────────────────────────────┐
    │  Trino Coordinator                   │
    │  (Port 8080)                         │
    │                                     │
    │  • Plans query                      │
    │  • Distributes to workers           │
    │  • Executes query                   │
    └──────────┬──────────────────────────┘
               │
               │ Query Execution
               ▼
    ┌─────────────────────────────────────┐
    │  Data Sources                       │
    │  • Postgres (Port 5434)             │
    │  • Iceberg (MinIO + Nessie)         │
    └──────────┬──────────────────────────┘
               │
               │ Results
               ▼
    ┌─────────────────────────────────────┐
    │  Policy Registry Backend            │
    │                                     │
    │  • Store results in query_results DB│
    │  • Return JSON response             │
    └──────────┬──────────────────────────┘
               │
               │ HTTP 200 + Results
               ▼
    ┌─────────────────────────────────────┐
    │  Frontend                            │
    │                                     │
    │  • Display results in table         │
    │  • Update query history              │
    │  • Show in Cerbos Logs tab          │
    └─────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    Key Concepts                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  🔐 Authorization as a Service (AaaS)                                       │
│     • Cerbos runs as an independent service                                │
│     • Makes authorization decisions independently                          │
│     • Can be scaled and updated separately                                 │
│                                                                             │
│  📝 Policy as Code                                                          │
│     • Policies stored as YAML files                                        │
│     • Version-controlled in Git                                             │
│     • Automatically reloaded on changes                                     │
│     • No code changes needed for policy updates                            │
│                                                                             │
│  ⚡ Real-time Authorization                                                 │
│     • Every query triggers authorization check                              │
│     • Decisions logged for audit                                           │
│     • Policies evaluated dynamically                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Authentication & Authorization System

### User Roles & Permissions

The system implements a **Role-Based Access Control (RBAC)** model with four predefined roles:

#### 1. **Admin** (`admin`)
- **Full access** to all system features
- Can manage users, roles, and permissions
- Can access all data sources and fields
- Can create and publish policies

#### 2. **Full Access User** (`full_access_user`)
- Can query **all fields** in both **Postgres** and **Iceberg**
- Cannot access administrative functions
- Can view and edit policies (read-only for system policies)

#### 3. **Postgres Only User** (`postgres_only_user`)
- Can query **all fields** in **Postgres only**
- Cannot access Iceberg data
- Cannot access administrative functions

#### 4. **Restricted User** (`restricted_user`)
- Can query both **Postgres** and **Iceberg**
- **Cannot access SSN fields** (automatically masked/blocked)
- Cannot access administrative functions

### Field-Level Access Control

The system provides **three approaches** for handling unauthorized field access:

#### Option 1: **Authorization Error**
- Return "You are not authorized to access this field" messages
- Block the query entirely if it contains restricted fields

#### Option 2: **Field Obfuscation**
- Mask sensitive fields with asterisks: `****-**-****`
- Replace with null values
- Hash the field values

#### Option 3: **Query Rewriting**
- Automatically modify SQL queries to exclude unauthorized columns
- Transparent to the user while maintaining security

### Demo Users

| Email | Password | Role | Access Level |
|-------|----------|------|--------------|
| `admin@pg-cerbos.com` | `admin123` | Admin | Full system access |
| `fullaccess@pg-cerbos.com` | `user123` | Full Access | All data, all fields |
| `postgresonly@pg-cerbos.com` | `user123` | Postgres Only | Postgres only, all fields |
| `restricted@pg-cerbos.com` | `user123` | Restricted | All data, no SSN fields |

---

## 🚀 Quickstart

### For New Developers
See [DEVELOPER_SETUP.md](DEVELOPER_SETUP.md) for a comprehensive setup guide.

### Quick Setup
```bash
# 1. Clone & setup
git clone https://github.com/stugorf/pg-cerbos.git
cd pg-cerbos
cp env.example .env

# 2. Complete initialization (recommended)
just init

# Or step by step:
just up
# Wait for services to be healthy, then access the UI
```

---

## 🔎 Services

### Frontend Services
- **Policy Registry Frontend** → [http://localhost:8083](http://localhost:8083)
  - Main dashboard with SQL query interface, policy management, and Cerbos logs viewer
  - Authentication UI for user/role/permission management
  - Cerbos policy editor with Monaco editor (YAML)

### Backend Services
- **Policy Registry Backend** → [http://localhost:8082](http://localhost:8082)
  - FastAPI REST API
  - Authentication (JWT)
  - User/Role/Permission management
  - Cerbos policy CRUD operations
  - SQL query execution via Trino
  - Authorization decision logging
  - Cerbos logs API

### Authorization Service
- **Cerbos PDP** → [http://localhost:3593](http://localhost:3593) (gRPC)
  - Policy Decision Point for authorization
  - Evaluates YAML policies
  - Provides authorization as a service
  - Audit logging enabled

### Data Query Services
- **Trino Coordinator** → [http://localhost:8080](http://localhost:8080)
  - SQL query planning and coordination
  - Web UI for query monitoring
- **Trino Worker** → Internal (no external port)
  - Query execution and data processing

### Data Storage Services
- **Postgres (Main)** → Port 5434
  - `demo_data` database: Demo data tables
  - `policy_store` database: Authentication and user management
  - `nessie` database: Nessie catalog metadata
- **Query Results DB** → Port 5433
  - `query_results` database: Query execution logs and results
- **MinIO** → [http://localhost:9000](http://localhost:9000) (API), [http://localhost:9001](http://localhost:9001) (Console)
  - S3-compatible object storage for Iceberg tables
- **Nessie** → Port 19120
  - Catalog service for Iceberg version control

---

## 🗄️ Trino Cluster

The Trino cluster runs with **production-ready configuration** and **field-level security**:

- **Coordinator**: Query planning, coordination, and field masking
- **Worker**: Query execution with optimized memory settings
- **Memory**: 2GB per query, 4GB total cluster memory
- **JVM**: 4GB heap for both coordinator and worker
- **Security**: Row filters, column masks, and access control
- **Logging**: Production-level (INFO) with audit trails

### Field-Level Security Features

- **Automatic SSN masking** for restricted users
- **Configurable field patterns** for different data types
- **Real-time policy evaluation** through Cerbos
- **Audit logging** of all access attempts

---

## 🧪 Demo Queries

### Available Demo Data

After running `just init`, you'll have access to:

- **PostgreSQL**: `postgres.public.person` (10 records with names, SSNs, job titles, gender, age)
- **Iceberg**: `iceberg.demo.employee_performance` (10 records with performance metrics: employee_id, performance_score, projects_completed, last_review_date, department, salary_band)
- **AML PoC Data**: `aml.*` schema with customers, accounts, transactions, alerts, cases, notes, and SARs (see [AML PoC Documentation](docs/AML_POC_SPEC.md))

### PuppyGraph Graph Queries

PuppyGraph provides graph query capabilities for the AML PoC. Access the PuppyGraph Web UI at http://localhost:8081 (username: `puppygraph`, password: `puppygraph123`).

#### Example openCypher Queries

**Find high-value transactions:**
```cypher
MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 50000
RETURN c.name, c.risk_rating, txn.amount, txn.timestamp
ORDER BY txn.amount DESC
```

**Expand transaction network from a case:**
```cypher
MATCH (c:Case {case_id: 1})-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
MATCH (cust)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
RETURN c.case_id, a.alert_id, cust.name, txn.txn_id, txn.amount, txn.timestamp
ORDER BY txn.amount DESC
```

**Find all customers connected to high-value transactions:**
```cypher
MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 50000
RETURN cust.name, cust.risk_rating, txn.amount, txn.timestamp
ORDER BY txn.amount DESC
```

**Trace alert to case to SAR:**
```cypher
MATCH (alert:Alert)-[:FROM_ALERT]-(c:Case)-[:RESULTED_IN]->(sar:SAR)
WHERE alert.severity = 'high'
RETURN alert.alert_id, alert.alert_type, c.case_id, c.status, sar.sar_id, sar.status
```

**Find transaction paths between customers:**
```cypher
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)<-[:OWNS]-(c2:Customer)
WHERE c1.customer_id <> c2.customer_id
RETURN c1.name as from_customer, c2.name as to_customer, txn.amount, txn.timestamp
ORDER BY txn.amount DESC
LIMIT 10
```

**Get case investigation timeline:**
```cypher
MATCH (c:Case {case_id: 1})-[:HAS_NOTE]->(note:CaseNote)
RETURN note.created_at, note.author_user_id, note.text
ORDER BY note.created_at
```

**Find transaction chains (multi-hop analysis):**
```cypher
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn1:Transaction)-[:TO_ACCOUNT]->(acc2:Account)-[:SENT_TXN]->(txn2:Transaction)
WHERE txn1.amount > 30000 AND txn2.amount > 30000
RETURN c1.name as start_customer, txn1.amount as first_txn, txn2.amount as second_txn
LIMIT 10
```

**Find all PEP customers with high-value transactions:**
```cypher
MATCH (cust:Customer {pep_flag: true})-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 50000
RETURN cust.name, cust.risk_rating, txn.amount, txn.timestamp
ORDER BY txn.amount DESC
```

#### Example Gremlin Queries

**Find all transactions for a customer:**
```groovy
g.V().hasLabel('Customer').has('customer_id', 1)
  .out('OWNS')
  .out('SENT_TXN')
  .valueMap()
```

**Get case with all related entities:**
```groovy
g.V().hasLabel('Case').has('case_id', 1)
  .as('case')
  .out('FROM_ALERT').as('alert')
  .out('FLAGS_CUSTOMER').as('customer')
  .out('OWNS').as('account')
  .out('SENT_TXN').as('transaction')
  .select('case', 'alert', 'customer', 'account', 'transaction')
  .by(valueMap())
```

**Find high-risk customers with PEP flags:**
```groovy
g.V().hasLabel('Customer')
  .has('pep_flag', true)
  .has('risk_rating', 'high')
  .valueMap()
```

**Traverse from alert to transactions:**
```groovy
g.V().hasLabel('Alert').has('alert_id', 1)
  .out('FLAGS_CUSTOMER')
  .out('OWNS')
  .out('SENT_TXN')
  .order().by('amount', desc)
  .limit(10)
  .valueMap()
```

#### Using PuppyGraph Web UI

1. **Access Web UI**: http://localhost:8081
2. **Sign In**: Use `puppygraph` / `puppygraph123`
3. **Navigate to Query Tab**: Select openCypher or Gremlin
4. **Execute Queries**: Paste and run the examples above
5. **View Results**: See results in table or graph visualization

#### Using Graph Query Tab in Main UI

1. **Access Main UI**: http://localhost:8083/auth.html
2. **Login**: Use your credentials
3. **Navigate to Graph Query Tab**: Click "Graph Query" in navigation
4. **Select Query Language**: Choose openCypher or Gremlin
5. **Enter Query**: Paste a Cypher or Gremlin query
6. **Execute**: Click "Execute Graph Query"
7. **View Results**: Results displayed with execution time
8. **Authorization**: All queries are authorized via Cerbos before execution

**Note**: The Graph Query tab in the main UI routes queries through the backend API (`/query/graph`), which enforces Cerbos authorization before sending to PuppyGraph. This ensures all graph queries are properly authorized.

For more examples, see [AML Cypher Examples](docs/AML_CYPHER_EXAMPLES.md).  
For setup details, see [AML PoC Quick Start Guide](docs/AML_POC_QUICKSTART.md).

## 🔧 Troubleshooting

### Common Issues

#### "generator didn't stop after throw()" Error

If you encounter this error when executing queries, it's typically caused by a database schema mismatch. The `just init` command automatically fixes this by:

1. **Adding missing columns** to database tables
2. **Ensuring schema compatibility** between the application and database
3. **Setting up proper table structures** for query logging

**Solution**: Run `just init` again to ensure all database schemas are properly configured.

#### Database Connection Issues

The system uses multiple databases:
- **`policy_store`**: User authentication, roles, and policies
- **`query_results`**: Query execution logs and results
- **`demo_data`**: Sample data for testing

**Solution**: Ensure all services are running with `docker ps` and restart if needed with `just up`.

### SQL Query Interface

The system includes a **web-based SQL query interface** that allows authenticated users to:

- **Execute SQL queries** directly in the browser
- **View real-time results** in formatted tables
- **Save and load queries** for future use
- **Track query history** with execution times and status
- **Enforce role-based access** control automatically

### Sample Working Queries

```sql
-- Basic PostgreSQL queries
SELECT * FROM postgres.public.person LIMIT 5;
SELECT COUNT(*) FROM postgres.public.person;
SELECT job_title, COUNT(*) FROM postgres.public.person GROUP BY job_title;

-- Basic Iceberg queries  
SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC;
SELECT department, AVG(performance_score) as avg_score FROM iceberg.demo.employee_performance GROUP BY department;

-- Cross-data source analysis
SELECT 
    'PostgreSQL' as source,
    COUNT(*) as record_count
FROM postgres.public.person
UNION ALL
SELECT 
    'Iceberg' as source,
    COUNT(*) as record_count
FROM iceberg.demo.employee_performance;

-- Combined analysis (JOIN between PostgreSQL and Iceberg)
SELECT 
    p.first_name, 
    p.last_name, 
    p.job_title, 
    ep.performance_score, 
    ep.department,
    ep.salary_band
FROM postgres.public.person p 
JOIN iceberg.demo.employee_performance ep ON p.id = ep.employee_id 
ORDER BY ep.performance_score DESC 
LIMIT 5;
```

### Authenticated Queries via API

All queries must go through the Policy Registry Backend API which enforces Cerbos authorization. Below are comprehensive examples showing both **successful** and **failed** queries for each user role.

#### Admin User (`admin@pg-cerbos.com`)

**✅ Successful Queries** (Admin has full access to everything):

```bash
# Login as admin
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@pg-cerbos.com", "password": "admin123"}' \
  | jq -r '.access_token')

# Query Postgres with all fields including SSN (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq

# Query Iceberg (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC"}' \
  http://localhost:8082/query | jq

# Cross-source JOIN query (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT p.first_name, p.last_name, p.ssn, ep.performance_score FROM postgres.public.person p JOIN iceberg.demo.employee_performance ep ON p.id = ep.employee_id LIMIT 5"}' \
  http://localhost:8082/query | jq
```

**Expected Success Response:**
```json
{
  "success": true,
  "data": [...],
  "columns": [...],
  "execution_time_ms": 123.45
}
```

#### Full Access User (`fullaccess@pg-cerbos.com`)

**✅ Successful Queries** (Can access all fields in both Postgres and Iceberg):

```bash
# Login as full access user
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "fullaccess@pg-cerbos.com", "password": "user123"}' \
  | jq -r '.access_token')

# Query Postgres with all fields including SSN (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq

# Query Iceberg (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC"}' \
  http://localhost:8082/query | jq

# Query with SSN field explicitly (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT first_name, last_name, ssn FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq
```

**Expected Success Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "first_name": "John",
      "last_name": "Doe",
      "ssn": "123-45-6789",
      ...
    }
  ],
  "columns": ["id", "first_name", "last_name", "ssn", ...],
  "execution_time_ms": 98.76
}
```

**❌ Failed Queries** (Full Access User has no restrictions, so all queries should succeed):

*Note: Full Access User has no query restrictions, so there are no examples of failed queries for this role.*

#### Postgres Only User (`postgresonly@pg-cerbos.com`)

**✅ Successful Queries** (Can access all Postgres fields):

```bash
# Login as postgres only user
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "postgresonly@pg-cerbos.com", "password": "user123"}' \
  | jq -r '.access_token')

# Query Postgres with all fields including SSN (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq

# Query Postgres with specific fields (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT first_name, last_name, ssn, job_title FROM postgres.public.person WHERE age > 30"}' \
  http://localhost:8082/query | jq
```

**Expected Success Response:**
```json
{
  "success": true,
  "data": [...],
  "columns": [...],
  "execution_time_ms": 87.65
}
```

**❌ Failed Queries** (Cannot access Iceberg):

```bash
# Query Iceberg (denied by Cerbos)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC"}' \
  http://localhost:8082/query | jq
```

**Expected Failure Response:**
```json
{
  "success": false,
  "error": "Query not authorized",
  "message": "Cerbos authorization check failed: action 'query' on resource 'iceberg' denied",
  "status_code": 403
}
```

#### Restricted User (`restricted@pg-cerbos.com`)

**✅ Successful Queries** (Can access Postgres and Iceberg, but NOT SSN fields):

```bash
# Login as restricted user
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "restricted@pg-cerbos.com", "password": "user123"}' \
  | jq -r '.access_token')

# Query Postgres without SSN (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT first_name, last_name, job_title, age FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq

# Query Iceberg (allowed)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC"}' \
  http://localhost:8082/query | jq

# Query with SELECT * but excluding SSN in WHERE clause (allowed - SSN not in SELECT)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT first_name, last_name, job_title FROM postgres.public.person WHERE age > 25 LIMIT 5"}' \
  http://localhost:8082/query | jq
```

**Expected Success Response:**
```json
{
  "success": true,
  "data": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "job_title": "Engineer",
      "age": 35
    }
  ],
  "columns": ["first_name", "last_name", "job_title", "age"],
  "execution_time_ms": 76.54
}
```

**❌ Failed Queries** (Cannot access SSN fields):

```bash
# Query with SSN field explicitly (denied by Cerbos)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT ssn FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq
```

**Expected Failure Response:**
```json
{
  "success": false,
  "error": "Query not authorized",
  "message": "Cerbos authorization check failed: action 'query' on resource 'postgres' denied - restricted users cannot access SSN fields",
  "status_code": 403
}
```

```bash
# Query with SELECT * including SSN (denied by Cerbos)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT * FROM postgres.public.person LIMIT 5"}' \
  http://localhost:8082/query | jq
```

**Expected Failure Response:**
```json
{
  "success": false,
  "error": "Query not authorized",
  "message": "Cerbos authorization check failed: action 'query' on resource 'postgres' denied - query contains restricted field 'ssn'",
  "status_code": 403
}
```

```bash
# Query with SSN in JOIN (denied by Cerbos)
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT p.first_name, p.ssn, ep.performance_score FROM postgres.public.person p JOIN iceberg.demo.employee_performance ep ON p.id = ep.employee_id LIMIT 5"}' \
  http://localhost:8082/query | jq
```

**Expected Failure Response:**
```json
{
  "success": false,
  "error": "Query not authorized",
  "message": "Cerbos authorization check failed: action 'query' on resource 'postgres' denied - query contains restricted field 'ssn'",
  "status_code": 403
}
```

---

## 📝 Managing Users & Policies

### 1. Access Authentication UI
Open **Authentication UI** → [http://localhost:8083/auth.html](http://localhost:8083/auth.html)

### 2. Login as Admin
Use `admin@pg-cerbos.com` / `admin123` to access administrative features

### 3. Manage Users
- **Users Tab**: Create, edit, and manage user accounts
- **Roles Tab**: Define and assign user roles
- **Permissions Tab**: Configure fine-grained access controls

### 4. Manage Cerbos Policies
- **Policy Management Tab**: Create, edit, and delete Cerbos YAML policies
- **Monaco Editor**: Full-featured YAML editor with syntax highlighting
- **Policy Validation**: Real-time YAML validation before saving
- **Policy Storage**: Policies stored as YAML files in `/cerbos/policies/`
- **Auto-reload**: Cerbos automatically reloads policies on file changes

### 5. View Authorization Logs
- **Cerbos Logs Tab**: View real-time authorization decisions
- **Authorization as a Service**: See how Cerbos makes independent authorization decisions
- **Policy as Code**: Observe how YAML policies are evaluated
- **Auto-refresh**: Logs update automatically every 5 seconds
- **Decision Details**: View user, roles, resource, action, and decision (ALLOW/DENY)

### 6. Execute SQL Queries
- **SQL Query Tab**: Submit SQL queries and view results
- **Cerbos Authorization**: Every query is checked against Cerbos policies
- **Real-time Results**: See query results in formatted tables
- **Query History**: Track all executed queries with timestamps
- **Authorization Logging**: All authorization decisions are logged and visible in the Cerbos Logs tab

---

## ⚙️ Just Commands

```bash
just up              # build & start all services
just down            # stop & remove containers + volumes
just down -v         # stop & remove containers + volumes (clean slate)
just ps              # show container status
just logs            # tail logs
just init            # complete system initialization (recommended)
just check-cerbos    # check Cerbos service health
just validate-cerbos-policies  # validate Cerbos policy syntax
just test-cerbos-policies      # run Cerbos policy tests
```

---

## 🗺️ Roadmap

- **Enhanced Field Masking**: Support for more data types and masking patterns
- **Dynamic Policy Updates**: Real-time policy changes without service restart
- **Advanced Analytics**: Query performance and access pattern analysis
- **Integration APIs**: REST endpoints for external system integration
- **Multi-factor Authentication**: Support for 2FA and SSO
- **Compliance Reporting**: GDPR, HIPAA, and SOX compliance features

---

## 🛑 Cleanup

```bash
just down -v
```

This removes all containers and volumes for a completely clean slate.

---

## 🔧 Development Notes

### Authentication & Authorization Flow

1. **User Login**: Email/password authentication via JWT
2. **Token Validation**: Backend validates JWT token on each request
3. **Authorization Check**: For SQL queries, backend calls Cerbos PDP via gRPC
4. **Policy Evaluation**: Cerbos evaluates YAML policies based on:
   - Principal (user ID, roles, attributes)
   - Resource (postgres/iceberg, query metadata)
   - Action (query)
5. **Decision**: Cerbos returns ALLOW or DENY
6. **Query Execution**: If allowed, query is forwarded to Trino
7. **Audit Logging**: All authorization decisions are logged for compliance and visible in the Cerbos Logs tab

### Security Features

- **JWT Tokens**: Secure, stateless authentication
- **Password Hashing**: bcrypt with salt for secure storage
- **Role-based Access**: Granular permission system via Cerbos policies
- **Authorization as a Service**: Cerbos PDP provides independent authorization decisions
- **Policy as Code**: YAML policies version-controlled and automatically reloaded
- **Audit Trails**: Complete logging of all authorization decisions and access attempts
- **Real-time Monitoring**: Authorization logs visible in the UI for transparency

### SQL Query Interface Features

- **Real-time Execution**: Submit queries and see results immediately
- **Role-based Enforcement**: Automatic access control based on user permissions
- **Query History**: Track all queries with execution times and status
- **Saved Queries**: Store and reuse frequently executed queries
- **Formatted Results**: Clean table display with proper column headers
- **Error Handling**: Clear error messages for failed queries
- **Multi-source Support**: Query both PostgreSQL and Iceberg data

### API Endpoints

#### Authentication
- `POST /auth/login` - User authentication
- `GET /auth/me` - Current user information

#### User Management (Admin Only)
- `GET /users` - List all users
- `POST /users` - Create new user
- `PUT /users/{id}` - Update user

#### Role Management (Admin Only)
- `GET /roles` - List all roles
- `POST /roles` - Create new role

#### Permission Management (Admin Only)
- `GET /permissions` - List all permissions
- `POST /permissions` - Create new permission

#### Cerbos Policy Management (Admin Only)
- `GET /cerbos/policies` - List all Cerbos YAML policies
- `GET /cerbos/policies/{path}` - Get specific policy by path
- `POST /cerbos/policies` - Create new Cerbos policy
- `PUT /cerbos/policies/{path}` - Update existing policy
- `DELETE /cerbos/policies/{path}` - Delete policy
- `POST /cerbos/policies/validate` - Validate policy YAML syntax
- `GET /cerbos/logs` - Get Cerbos authorization logs (for UI display)

#### Query Execution
- `POST /query` - Execute SQL query (requires Cerbos authorization)
- `GET /queries` - List query history (authenticated)
- `GET /queries/{id}` - Get query details and results (authenticated)

---

## 🚨 Troubleshooting

### Common Issues

1. **"Schema Not Found" errors**
   - Run `just init` to ensure all schemas are created
   - Check that Iceberg catalog is accessible: `docker exec pg-cerbos-trino-coordinator trino --execute "SHOW CATALOGS"`

2. **"generator didn't stop after throw()" errors**
   - This usually indicates hanging queries in Trino
   - Run `just init` to clean up hanging queries
   - Or manually check: `docker exec pg-cerbos-trino-coordinator trino --execute "SELECT * FROM system.runtime.queries WHERE state = 'RUNNING'"`

3. **Authentication failures**
   - Ensure database is seeded: `docker exec pg-cerbos-postgres psql -U postgres -d policy_store -c "SELECT COUNT(*) FROM users;"`
   - Run `just init` to re-seed if needed

4. **Cerbos policy issues**
   - Check Cerbos health: `just check-cerbos`
   - Validate policies: `just validate-cerbos-policies`
   - Check Cerbos logs: `just cerbos-logs`

### Health Checks

```bash
# Check all services
just ps

# Check Cerbos health
just check-cerbos

# Check Trino status
docker exec pg-cerbos-trino-coordinator trino --execute "SELECT 1"

# Check database connectivity
docker exec pg-cerbos-postgres psql -U postgres -c "SELECT version()"
```

---

👉 This repo provides a **production-ready unified entitlements solution** with comprehensive authentication, role-based access control, field-level security, and a **web-based SQL query interface**. It demonstrates how to implement enterprise-grade data governance using modern open-source technologies.

**For new developers**: Simply run `just init` after starting services to get a fully working system! 🎉
