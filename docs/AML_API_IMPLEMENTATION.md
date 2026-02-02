# AML API Implementation

## ✅ Completed Implementation

### 1. PuppyGraph Client (`puppygraph_client.py`)

- **PuppyGraphClient class**: Client for querying PuppyGraph graph database
- **Methods**:
  - `execute_cypher(query)`: Execute openCypher queries
  - `execute_gremlin(query)`: Execute Gremlin queries
  - `health_check()`: Check PuppyGraph service health
- **Configuration**: Uses environment variables:
  - `PUPPYGRAPH_URL` (default: `http://puppygraph:8081`)
  - `PUPPYGRAPH_USER` (default: `puppygraph`)
  - `PUPPYGRAPH_PASSWORD` (default: `puppygraph123`)

### 2. AML Data Models (`aml_models.py`)

Pydantic models for type-safe API requests and responses:

**Request Models**:
- `GraphExpandRequest`: Graph traversal parameters
- `CaseNoteCreate`: Create case notes
- `CaseAssignRequest`: Assign cases to analysts
- `SARCreate`: Create SARs

**Response Models**:
- `CustomerResponse`, `AccountResponse`, `TransactionResponse`
- `AlertResponse`, `CaseResponse`, `CaseNoteResponse`, `SARResponse`
- `GraphResponse`, `GraphNode`, `GraphEdge`: Graph query results

### 3. AML API Endpoints (`app.py`)

All endpoints include Cerbos authorization checks:

#### Alert Endpoints
- `GET /aml/alerts` - List alerts (with optional status/severity filters)
- `GET /aml/alerts/{alert_id}` - Get specific alert
- `POST /aml/alerts/{alert_id}/escalate` - Escalate alert → creates case

#### Case Endpoints
- `GET /aml/cases` - List cases (with optional status/owner filters)
- `GET /aml/cases/{case_id}` - Get specific case
- `GET /aml/cases/{case_id}/notes` - List all notes for a case
- `POST /aml/cases/{case_id}/notes` - Add note to case
- `POST /aml/cases/{case_id}/graph-expand` - Expand transaction network via PuppyGraph
- `POST /aml/cases/{case_id}/assign` - Assign case (manager only)
- `POST /aml/cases/{case_id}/close` - Close case (analyst if assigned, manager always)

#### SAR Endpoints
- `GET /aml/sars` - List SARs (with optional status/case_id filters)
- `GET /aml/sars/{sar_id}` - Get specific SAR
- `POST /aml/sars` - Create SAR draft (manager only)
- `POST /aml/sars/{sar_id}/submit` - Submit SAR (manager only)

## Authorization Flow

Each endpoint follows this pattern:

1. **Extract user context**: Get user ID, email, and roles
2. **Cerbos authorization check**: Call `check_resource_access()` with:
   - Principal: user ID, email, roles
   - Resource: kind, ID, attributes (e.g., `owner_user_id`, `status`)
   - Action: `view`, `escalate`, `add_note`, `graph_expand`, `assign`, `close`
3. **If denied**: Return HTTP 403 with reason
4. **If allowed**: Execute operation (Trino query or PuppyGraph query)
5. **Return response**: Convert to Pydantic response models

## Example Usage

### List Alerts
```bash
curl -X GET "http://localhost:8082/aml/alerts?status=new&severity=high" \
  -H "Authorization: Bearer <token>"
```

### Escalate Alert to Case
```bash
curl -X POST "http://localhost:8082/aml/alerts/1/escalate" \
  -H "Authorization: Bearer <token>"
```

### Expand Transaction Network
```bash
curl -X POST "http://localhost:8082/aml/cases/1/graph-expand" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"depth": 2, "direction": "both"}'
```

### Add Case Note
```bash
curl -X POST "http://localhost:8082/aml/cases/1/notes" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "Found suspicious transaction pattern"}'
```

## Integration Points

### Cerbos Authorization
- Uses `cerbos_client.check_resource_access()` for all endpoints
- Supports derived roles (e.g., `case_assignee` for analysts)
- Resource attributes include ownership and status for context-aware decisions

### PuppyGraph Integration
- Graph expansion endpoint uses PuppyGraph for transaction network queries
- Executes openCypher queries via `puppygraph_client.execute_cypher()`
- Returns graph structure with nodes and edges

### Trino/PostgreSQL
- All data operations go through Trino
- Queries target `postgres.demo_data.aml.*` tables
- Uses Trino client manager for connection pooling

## Additional Endpoints Added

### Case Notes Listing
- `GET /aml/cases/{case_id}/notes` - Returns all notes for a case in chronological order

### SAR Management
- `GET /aml/sars` - List all SARs with optional filtering by status or case_id
- `GET /aml/sars/{sar_id}` - Get specific SAR details
- `POST /aml/sars` - Create a new SAR draft (manager only, requires case_id)
- `POST /aml/sars/{sar_id}/submit` - Submit a SAR (manager only, changes status from draft to submitted)

## Graph Response Parsing

The graph expansion endpoint now includes improved parsing logic:
- Extracts nodes from PuppyGraph response (handles multiple response formats)
- Tracks unique nodes to avoid duplicates
- Extracts node properties and labels
- Returns structured `GraphResponse` with nodes, edges, query, and execution time

## Next Steps

1. **Error Handling**: Add more robust error handling and validation
2. **Testing**: Add unit tests for AML endpoints
3. **UI Integration**: Create frontend components for AML workflows
4. **Graph Visualization**: Add frontend graph visualization for transaction networks
5. **PuppyGraph Response Format**: Refine parsing based on actual PuppyGraph API response structure

## Notes

- SQL queries use f-strings (Trino limitation) but IDs are validated by FastAPI
- PuppyGraph response format parsing needs refinement based on actual API response
- All endpoints require authentication via JWT token
- Authorization decisions are logged for audit purposes
