# AML PoC Quick Start Guide

Quick reference for setting up and testing the AML Proof of Concept.

## Prerequisites

- Docker and Docker Compose installed
- Ports 8080-8083, 5434, 3593 available
- `just` command runner (or use `make` equivalents)

## Setup

### 1. Start Services

```bash
just up
```

### 2. Initialize AML Schema and Data

The AML schema and seed data are automatically loaded when PostgreSQL initializes:
- Schema: `postgres/init/60-aml-schema.sql`
- Seed Data: `postgres/init/61-aml-seed-data.sql`

To verify:

```bash
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -c "\dt aml.*"
```

### 3. Verify Seed Data

```bash
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -c "SELECT COUNT(*) FROM aml.customer;"
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -c "SELECT COUNT(*) FROM aml.case;"
```

## Testing Cerbos Policies

### Validate Policies

```bash
just validate-aml-policies
```

### Test Authorization via Cerbos API

#### Test 1: Analyst can view case assigned to them

```bash
curl -X POST http://localhost:3593/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "id": "analyst1",
      "roles": ["aml_analyst"],
      "attr": {
        "team": "Team A"
      }
    },
    "resource": {
      "kind": "case",
      "id": "1",
      "attr": {
        "owner_user_id": "analyst1",
        "status": "open",
        "team": "Team A"
      }
    },
    "actions": ["view", "edit"]
  }' | jq
```

**Expected**: `{"result": {"1": "EFFECT_ALLOW", "2": "EFFECT_ALLOW"}}`

#### Test 2: Analyst cannot edit case NOT assigned to them

```bash
curl -X POST http://localhost:3593/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "id": "analyst1",
      "roles": ["aml_analyst"]
    },
    "resource": {
      "kind": "case",
      "id": "2",
      "attr": {
        "owner_user_id": "analyst2",
        "status": "open"
      }
    },
    "actions": ["edit"]
  }' | jq
```

**Expected**: `{"result": {"1": "EFFECT_DENY"}}`

#### Test 3: Manager can always edit any case

```bash
curl -X POST http://localhost:3593/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "id": "manager1",
      "roles": ["aml_manager"]
    },
    "resource": {
      "kind": "case",
      "id": "2",
      "attr": {
        "owner_user_id": "analyst2",
        "status": "open"
      }
    },
    "actions": ["edit", "assign", "close"]
  }' | jq
```

**Expected**: All actions allowed

#### Test 4: Auditor can only view

```bash
curl -X POST http://localhost:3593/api/check \
  -H "Content-Type: application/json" \
  -d '{
    "principal": {
      "id": "auditor1",
      "roles": ["auditor"]
    },
    "resource": {
      "kind": "case",
      "id": "1",
      "attr": {
        "status": "open"
      }
    },
    "actions": ["view", "edit", "close"]
  }' | jq
```

**Expected**: Only `view` allowed, `edit` and `close` denied

## Query Demo Data

### View All Cases

```bash
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -c "SELECT case_id, status, priority, owner_user_id, team FROM aml.case;"
```

### View Transaction Network for a Case

```bash
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -c "
SELECT 
    c.case_id,
    a.alert_id,
    cust.customer_id,
    cust.name,
    txn.txn_id,
    txn.amount,
    txn.timestamp
FROM aml.case c
JOIN aml.alert a ON c.source_alert_id = a.alert_id
JOIN aml.customer cust ON a.primary_customer_id = cust.customer_id
JOIN aml.account acc ON cust.customer_id = acc.customer_id
JOIN aml.transaction txn ON acc.account_id = txn.from_account_id
WHERE c.case_id = 1
ORDER BY txn.timestamp;
"
```

### View Case Notes Timeline

```bash
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -c "
SELECT 
    cn.note_id,
    cn.created_at,
    cn.author_user_id,
    cn.text
FROM aml.case_note cn
WHERE cn.case_id = 1
ORDER BY cn.created_at;
"
```

## PuppyGraph Setup

PuppyGraph is now integrated as a Docker service in `compose.yml`.

### 1. Start PuppyGraph

PuppyGraph starts automatically with `just up`. Verify it's running:

```bash
just check-puppygraph
```

Or check the service:

```bash
docker ps | grep puppygraph
```

### 2. Access PuppyGraph Web UI

Open the PuppyGraph Web UI: http://localhost:8081

- **Username**: `puppygraph` (default)
- **Password**: `puppygraph123` (or set via `PUPPYGRAPH_PASSWORD` env var)

### 3. Load AML Schema

#### Option A: Using the Script (Recommended)

```bash
just init-puppygraph
```

This will wait for PuppyGraph to be ready and provide instructions.

#### Option B: Manual Upload via Web UI

1. Open http://localhost:8081
2. Sign in with credentials above
3. Navigate to **Schema** page
4. Click **Upload Schema** or use the schema builder
5. Upload the file: `puppygraph/aml-schema.json`
6. Verify the schema loads correctly

#### Option C: Using Load Script

```bash
just load-puppygraph-schema
```

### 4. Verify Schema Loaded

Once the schema is loaded, you should see:
- 7 vertex types: Customer, Account, Transaction, Alert, Case, CaseNote, SAR
- 9 edge types: OWNS, SENT_TXN, TO_ACCOUNT, FLAGS_CUSTOMER, FLAGS_ACCOUNT, FROM_ALERT, ABOUT_CUSTOMER, HAS_NOTE, RESULTED_IN

### 5. Test Graph Queries

#### Using openCypher (Bolt Protocol - Port 7687)

```cypher
// Expand transaction network from a case
MATCH (c:Case {case_id: 1})-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
MATCH (cust)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
RETURN c, a, cust, acc, txn
```

#### Using Gremlin (Port 8182)

```groovy
g.V().hasLabel('Case').has('case_id', 1)
  .out('FROM_ALERT')
  .out('FLAGS_CUSTOMER')
  .out('OWNS')
  .out('SENT_TXN')
  .valueMap()
```

#### Using Web UI Query Interface

1. Navigate to **Query** page in PuppyGraph Web UI
2. Select query language (openCypher or Gremlin)
3. Enter and execute queries
4. View results in table or graph visualization

## Troubleshooting

### Policies not loading

```bash
# Check Cerbos logs
just cerbos-logs

# Verify policies exist
just list-cerbos-policies | grep aml
```

### Database schema missing

```bash
# Re-run initialization
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -f /docker-entrypoint-initdb.d/60-aml-schema.sql
docker exec pg-cerbos-postgres psql -U postgres -d demo_data -f /docker-entrypoint-initdb.d/61-aml-seed-data.sql
```

### Cerbos health check

```bash
just check-cerbos
```

### PuppyGraph not responding

```bash
# Check PuppyGraph health
just check-puppygraph

# Check PuppyGraph logs
docker logs pg-cerbos-puppygraph

# Verify PuppyGraph is running
docker ps | grep puppygraph
```

### PuppyGraph schema not loading

1. Verify PostgreSQL is accessible from PuppyGraph container:
   ```bash
   docker exec pg-cerbos-puppygraph ping -c 1 postgres
   ```

2. Check schema file exists:
   ```bash
   ls -la puppygraph/aml-schema.json
   ```

3. Verify JDBC connection string in schema matches your PostgreSQL setup:
   - Host: `postgres` (Docker service name)
   - Port: `5432` (internal port)
   - Database: `demo_data`
   - User/Password: Match your PostgreSQL credentials

## Next Steps

1. Implement AML API endpoints in `policy-registry/backend/app.py`
2. Add PuppyGraph service to `compose.yml`
3. Create UI for case workbench
4. Add graph visualization

See `docs/AML_POC_SPEC.md` for full specification.
