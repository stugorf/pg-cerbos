# PuppyGraph Integration for AML PoC

## ✅ Integration Complete

PuppyGraph has been successfully integrated into the AML PoC architecture as a Docker service.

## What Was Added

### 1. Docker Compose Service

**File**: `compose.yml`

Added PuppyGraph service with:
- **Image**: `puppygraph/puppygraph:stable`
- **Ports**:
  - `8081` - Web UI
  - `8182` - Gremlin server
  - `7687` - openCypher/Bolt protocol
- **Environment Variables**:
  - `PUPPYGRAPH_PASSWORD` (default: `puppygraph123`)
  - `QUERY_TIMEOUT=5m`
  - `STORAGE_PATH_ROOT=/data/storage`
- **Volumes**:
  - `puppygraph_data` - Persistent storage for schemas
  - `./puppygraph:/schemas:ro` - Schema directory mount
- **Dependencies**: Waits for PostgreSQL to be healthy
- **Health Check**: Monitors service availability

### 2. Initialization Scripts

**Files**:
- `scripts/init-puppygraph.sh` - Waits for PuppyGraph and provides upload instructions
- `scripts/load-puppygraph-schema.sh` - Attempts API-based schema upload

Both scripts:
- Wait for PuppyGraph to be ready
- Provide manual upload instructions
- Handle errors gracefully

### 3. Justfile Commands

Added three new commands:

```bash
just init-puppygraph          # Initialize PuppyGraph and show upload instructions
just load-puppygraph-schema   # Attempt to load schema via API
just check-puppygraph         # Check PuppyGraph service health
```

### 4. Schema Configuration

**File**: `puppygraph/aml-schema.json`

The schema is configured to connect to PostgreSQL:
- **JDBC URL**: `jdbc:postgresql://postgres:5432/demo_data`
- **User**: `postgres` (from environment)
- **Password**: `postgres` (from environment)
- **Driver**: `org.postgresql.Driver`

**Note**: The connection uses Docker service name `postgres` for internal networking.

## Quick Start

### 1. Start Services

```bash
just up
```

PuppyGraph will start automatically and wait for PostgreSQL to be ready.

### 2. Verify PuppyGraph is Running

```bash
just check-puppygraph
```

Or check manually:

```bash
curl http://localhost:8081/api/health
```

### 3. Load Schema

#### Option A: Using Script (Recommended)

```bash
just init-puppygraph
```

This provides step-by-step instructions.

#### Option B: Manual Upload

1. Open http://localhost:8081
2. Sign in:
   - Username: `puppygraph`
   - Password: `puppygraph123` (or your `PUPPYGRAPH_PASSWORD`)
3. Navigate to **Schema** page
4. Click **Upload Schema**
5. Select `puppygraph/aml-schema.json`
6. Verify schema loads

### 4. Test Graph Queries

Once schema is loaded, test queries in the Web UI:

**openCypher Example**:
```cypher
MATCH (c:Case {case_id: 1})-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
MATCH (cust)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
RETURN c, a, cust, acc, txn
```

**Gremlin Example**:
```groovy
g.V().hasLabel('Case').has('case_id', 1)
  .out('FROM_ALERT')
  .out('FLAGS_CUSTOMER')
  .out('OWNS')
  .out('SENT_TXN')
  .valueMap()
```

## Architecture Integration

```
┌─────────────────────────────────────────────────────────┐
│              AML API (Policy Enforcement)                │
│                   Port 8082                             │
└───────────┬───────────────────────────────┬─────────────┘
            │                               │
            │ Authorization                 │ Graph Query
            │ (gRPC)                        │ (HTTP)
            ▼                               ▼
┌──────────────────────┐      ┌──────────────────────────┐
│   Cerbos PDP         │      │      PuppyGraph           │
│   Port 3593          │      │   Port 8081/8182/7687     │
│                      │      │                           │
│ • Policy Evaluation  │      │ • Graph Traversals        │
│ • Decision Logging    │      │ • Postgres Translation    │
└──────────────────────┘      └──────────────┬────────────┘
                                            │
                                            │ JDBC
                                            ▼
                              ┌──────────────────────────┐
                              │      PostgreSQL          │
                              │   Port 5434              │
                              │                         │
                              │ • AML Tables            │
                              │ • System of Record      │
                              └─────────────────────────┘
```

## Configuration Details

### Environment Variables

Set in `.env` or `compose.yml`:

```bash
PUPPYGRAPH_PASSWORD=puppygraph123  # Change in production!
```

### Network Configuration

PuppyGraph connects to PostgreSQL via Docker network `trino-net`:
- Service name: `postgres`
- Internal port: `5432`
- Database: `demo_data`

### Storage

PuppyGraph uses a Docker volume for persistence:
- Volume name: `puppygraph_data`
- Mount point: `/data/storage`
- Persists schemas and configurations between container restarts

## Troubleshooting

### PuppyGraph Not Starting

```bash
# Check logs
docker logs pg-cerbos-puppygraph

# Check if PostgreSQL is ready
docker exec pg-cerbos-puppygraph ping -c 1 postgres

# Verify network connectivity
docker network inspect pg-cerbos_trino-net
```

### Schema Not Loading

1. **Verify schema file exists**:
   ```bash
   ls -la puppygraph/aml-schema.json
   ```

2. **Check JSON syntax**:
   ```bash
   python3 -m json.tool puppygraph/aml-schema.json > /dev/null
   ```

3. **Verify PostgreSQL connection**:
   - Check JDBC URL in schema matches your setup
   - Verify credentials are correct
   - Ensure database `demo_data` exists

4. **Check PuppyGraph logs**:
   ```bash
   docker logs pg-cerbos-puppygraph | grep -i error
   ```

### Connection Issues

If PuppyGraph can't connect to PostgreSQL:

1. **Verify service names**: PuppyGraph uses `postgres` (Docker service name)
2. **Check network**: Both services must be on `trino-net`
3. **Test connectivity**:
   ```bash
   docker exec pg-cerbos-puppygraph ping postgres
   ```

## Next Steps

1. **Backend Integration**: Add PuppyGraph client to `policy-registry/backend/app.py`
2. **API Endpoints**: Implement graph expansion endpoints
3. **Authorization**: Add Cerbos checks before PuppyGraph queries
4. **UI Integration**: Add graph visualization components

## References

- [PuppyGraph Docker Documentation](https://docs.puppygraph.com/getting-started/launching-puppygraph-in-docker/)
- [PuppyGraph PostgreSQL Connection](https://docs.puppygraph.com/getting-started/querying-postgresql-data-as-a-graph/)
- [PuppyGraph Schema Documentation](https://docs.puppygraph.com/reference/schema/)

---

**Status**: ✅ PuppyGraph Integration Complete  
**Ready for**: Backend API Implementation
