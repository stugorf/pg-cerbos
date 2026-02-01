# AML PoC Specification

**Anti-Money Laundering Proof of Concept**  
PostgreSQL + PuppyGraph + Cerbos Architecture

---

## Overview

This PoC demonstrates an AML (Anti-Money Laundering) system using:
- **PostgreSQL** as the system of record
- **PuppyGraph** to query Postgres "as a graph" via schema mapping
- **Cerbos** for RBAC-style authorization with derived roles

### Use Case Workflow

"Analyst investigates an alert, opens/works a case, expands the transaction network, adds notes, escalates for SAR decision, manager closes case."

---

## Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                    UI: Case Workbench                        │
│              (Graph exploration + timeline)                  │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AML API (Policy Enforcement)                   │
│              Port 8082 (FastAPI Backend)                     │
└───────────┬───────────────────────────────┬─────────────────┘
            │                               │
            │ Authorization                 │ Graph Query
            │ (gRPC)                        │ (HTTP)
            ▼                               ▼
┌──────────────────────┐      ┌──────────────────────────────┐
│   Cerbos PDP         │      │      PuppyGraph              │
│   Port 3593          │      │   (Graph Query Endpoint)     │
│                      │      │                              │
│ • Policy Evaluation  │      │ • Graph Traversals           │
│ • Decision Logging   │      │ • Postgres Translation       │
└──────────────────────┘      └──────────────┬───────────────┘
                                            │
                                            │ JDBC
                                            ▼
                              ┌──────────────────────────────┐
                              │      PostgreSQL             │
                              │   Port 5434                 │
                              │                             │
                              │ • AML Tables                │
                              │ • System of Record          │
                              └─────────────────────────────┘
```

---

## Database Schema

### Core Domain Objects

#### 1. Customer
- `customer_id` (PK)
- `name`
- `risk_rating` (low/med/high)
- `pep_flag` (boolean)
- `created_at`, `updated_at`

#### 2. Account
- `account_id` (PK)
- `customer_id` (FK → Customer)
- `type`, `status`
- `created_at`, `updated_at`

#### 3. Transaction
- `txn_id` (PK)
- `from_account_id` (FK → Account)
- `to_account_id` (FK → Account)
- `amount`, `timestamp`
- `channel`, `country`
- `created_at`

### Investigation Objects

#### 4. Alert
- `alert_id` (PK)
- `alert_type`
- `created_at`
- `severity` (low/medium/high/critical)
- `status` (new/triaged/escalated/closed)
- `primary_customer_id` (FK → Customer, nullable)
- `primary_account_id` (FK → Account, nullable)

#### 5. Case
- `case_id` (PK)
- `status` (open/closed)
- `priority` (low/medium/high/urgent)
- `created_at`, `updated_at`
- `owner_user_id` (assigned analyst)
- `team`
- `source_alert_id` (FK → Alert)

#### 6. CaseNote
- `note_id` (PK)
- `case_id` (FK → Case)
- `author_user_id`
- `created_at`
- `text`

#### 7. SAR (Suspicious Activity Report)
- `sar_id` (PK)
- `case_id` (FK → Case)
- `status` (draft/submitted)
- `created_at`, `submitted_at`

### Files
- **Schema DDL**: `postgres/init/60-aml-schema.sql`
- **Seed Data**: `postgres/init/61-aml-seed-data.sql`

---

## Graph Schema (PuppyGraph)

PuppyGraph maps PostgreSQL tables to a graph structure for traversal queries.

### Nodes
- `Customer`, `Account`, `Transaction`, `Alert`, `Case`, `CaseNote`, `SAR`

### Edges
- `(Customer)-[:OWNS]->(Account)`
- `(Account)-[:SENT_TXN]->(Transaction)`
- `(Transaction)-[:TO_ACCOUNT]->(Account)`
- `(Alert)-[:FLAGS_CUSTOMER]->(Customer)`
- `(Alert)-[:FLAGS_ACCOUNT]->(Account)`
- `(Case)-[:FROM_ALERT]->(Alert)`
- `(Case)-[:ABOUT_CUSTOMER]->(Customer)` (conditional)
- `(Case)-[:HAS_NOTE]->(CaseNote)`
- `(Case)-[:RESULTED_IN]->(SAR)`

### File
- **PuppyGraph Schema**: `puppygraph/aml-schema.json`

### Example Graph Query

```cypher
// Expand transaction network from a case
MATCH (c:Case {case_id: 1})-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
MATCH (cust)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
RETURN c, a, cust, acc, txn, acc2
```

---

## Authorization (Cerbos)

### Roles

#### 1. `aml_analyst`
- View alerts/cases/transactions/customers
- Create notes
- Escalate alert to case
- Edit/close cases **only if assigned** (via derived role)

#### 2. `aml_manager`
- All analyst permissions
- Assign/unassign cases
- Close any case
- Approve SAR submission

#### 3. `auditor`
- Read-only access to cases/alerts/SARs
- No edits, no assignment, no export

### Resource Types & Actions

| Resource | Actions |
|----------|---------|
| `alert` | `view`, `triage`, `escalate` |
| `case` | `view`, `edit`, `assign`, `close`, `add_note` |
| `transaction` | `view`, `graph_expand` |
| `customer` | `view` |
| `sar` | `view`, `draft`, `submit` |

### Derived Roles

**`case_assignee`**: Automatically granted when `principal.id == resource.owner_user_id`

This allows analysts to edit/close cases only if they are the assigned owner, while managers can always edit/close.

### Policy Files
- **Principal Policies**: `cerbos/policies/principal_policies/aml_roles.yaml`
- **Resource Policies**: `cerbos/policies/resource_policies/aml.yaml`
- **Derived Roles**: `cerbos/policies/derived_roles/aml_derived_roles.yaml`
- **Schemas**: 
  - `cerbos/policies/_schemas/aml_principal.json`
  - `cerbos/policies/_schemas/aml_resource.json`

---

## API Endpoints (AML API)

### Alert Management
- `GET /alerts` - List alerts (with Cerbos authorization)
- `GET /alerts/{id}` - Get alert details
- `POST /alerts/{id}/triage` - Triage an alert
- `POST /alerts/{id}/escalate` - Escalate alert → creates case

### Case Management
- `GET /cases` - List cases
- `GET /cases/{id}` - Get case details
- `POST /cases/{id}/notes` - Add note to case
- `POST /cases/{id}/assign` - Assign case to analyst (manager only)
- `POST /cases/{id}/close` - Close case
- `POST /cases/{id}/graph-expand?depth=2` - Expand transaction network

### SAR Management
- `GET /sars` - List SARs
- `GET /sars/{id}` - Get SAR details
- `POST /sars` - Create SAR draft (manager only)
- `POST /sars/{id}/submit` - Submit SAR (manager only)

### Request Flow Example: "Expand Transaction Network"

```
1. UI → AML API: POST /cases/{id}/graph-expand?depth=2
2. AML API → Cerbos:
   - Principal: {id: "analyst1", roles: ["aml_analyst"], attrs: {team: "Team A"}}
   - Resource: {kind: "case", id: "1", owner_user_id: "analyst1", team: "Team A", status: "open"}
   - Action: "graph_expand"
3. Cerbos → AML API: ALLOW
4. AML API → PuppyGraph: Graph traversal query
5. PuppyGraph → PostgreSQL: Translated SQL queries
6. PostgreSQL → PuppyGraph: Results
7. PuppyGraph → AML API: Graph subgraph
8. AML API → UI: JSON response with graph data
```

---

## Audit & Decision Logging

Cerbos decision logs capture:
- Principal ID + roles
- Resource type + ID
- Action
- Decision (ALLOW/DENY)
- Request context (endpoint, case_id, investigation reason)
- Timestamp

**Enabled in Cerbos config**: `cerbos/cerbos.yaml` (audit logging)

---

## Setup Instructions

### 1. Initialize Database Schema

The AML schema is automatically created when PostgreSQL initializes:
- Schema DDL runs via `postgres/init/60-aml-schema.sql`
- Seed data loads via `postgres/init/61-aml-seed-data.sql`

### 2. Configure PuppyGraph

PuppyGraph is now integrated in `compose.yml`:

1. **Start PuppyGraph**: Automatically starts with `just up`
   - Web UI: http://localhost:8081
   - Gremlin: Port 8182
   - openCypher/Bolt: Port 7687

2. **Load Schema**: 
   ```bash
   just init-puppygraph
   ```
   Or manually upload `puppygraph/aml-schema.json` via Web UI

3. **Verify Connection**: PuppyGraph connects to PostgreSQL via JDBC
   - Connection string in schema: `jdbc:postgresql://postgres:5432/demo_data`
   - Uses Docker service name `postgres` for internal networking

### 3. Load Cerbos Policies

Policies are automatically loaded from:
- `cerbos/policies/principal_policies/aml_roles.yaml`
- `cerbos/policies/resource_policies/aml.yaml`
- `cerbos/policies/derived_roles/aml_derived_roles.yaml`

Cerbos auto-reloads on file changes.

### 4. Test Authorization

```bash
# Test analyst can view case assigned to them
curl -X POST http://localhost:3593/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "id": "analyst1",
      "roles": ["aml_analyst"]
    },
    "resource": {
      "kind": "case",
      "id": "1",
      "attr": {
        "owner_user_id": "analyst1",
        "status": "open"
      }
    },
    "actions": ["view", "edit"]
  }'
```

---

## Demo Data

Seed data includes:
- **5 customers** (mix of risk ratings, some PEP)
- **8 accounts** (checking/savings)
- **8 transactions** (mix of high-value and normal)
- **5 alerts** (various types and statuses)
- **3 cases** (2 open, 1 closed)
- **5 case notes** (investigation timeline)
- **1 SAR** (draft status)

See `postgres/init/61-aml-seed-data.sql` for details.

---

## Next Steps

1. **Implement AML API endpoints** in `policy-registry/backend/app.py`
   - Alert management endpoints
   - Case management endpoints
   - Graph expansion endpoint (PuppyGraph integration)
   - SAR management endpoints

2. **Integrate PuppyGraph queries** in backend
   - Add PuppyGraph client library
   - Implement graph traversal queries
   - Add Cerbos authorization checks before queries

3. **Create UI components** for case workbench
   - Case list and detail views
   - Alert triage interface
   - Graph visualization for transaction networks

4. **Implement SAR submission workflow**
   - SAR draft creation
   - Manager approval flow
   - Submission tracking

5. **Add audit log viewer** for AML decisions
   - Display Cerbos decision logs
   - Filter by user, resource, action
   - Export for compliance

---

## Files Created

```
postgres/init/
  ├── 60-aml-schema.sql          # AML table DDL
  └── 61-aml-seed-data.sql       # Demo data

puppygraph/
  └── aml-schema.json            # PuppyGraph schema mapping

cerbos/policies/
  ├── _schemas/
  │   ├── aml_principal.json    # Principal schema
  │   └── aml_resource.json      # Resource schema
  ├── principal_policies/
  │   └── aml_roles.yaml         # Role definitions
  ├── resource_policies/
  │   └── aml.yaml               # Resource policies
  └── derived_roles/
      └── aml_derived_roles.yaml # case_assignee derived role

docs/
  └── AML_POC_SPEC.md            # This document
```

---

## References

- [Cerbos Documentation](https://docs.cerbos.dev)
- [PuppyGraph Documentation](https://puppygraph.com/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
