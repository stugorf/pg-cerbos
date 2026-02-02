# AML UI Implementation

## ✅ UI Updates Complete

### 1. Graph Query Tab

**Location**: New tab in main navigation

**Features**:
- **Query Language Selection**: Dropdown to choose between openCypher and Gremlin
- **Query Input**: Large textarea for entering graph queries
- **Execution**: Executes queries via backend API endpoint `/query/graph`
- **Authorization**: All queries are authorized via Cerbos before being sent to PuppyGraph
- **Results Display**: Shows query results in table or JSON format
- **Execution Time**: Displays query execution time

**Backend Endpoint**: `POST /query/graph`
- Accepts: `{ query: string, type: "cypher" | "gremlin" }`
- Authorizes via Cerbos before execution
- Routes to PuppyGraph for execution
- Returns: Query results with execution time

**Example Queries**:

**Cypher**:
```cypher
MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 50000
RETURN c.name, txn.amount, txn.timestamp
```

**Gremlin**:
```groovy
g.V().hasLabel('Customer').out('OWNS').out('SENT_TXN').has('amount', gt(50000)).valueMap()
```

### 2. AML Management Tab

**Location**: New tab in main navigation

**Features**:
- **Three Sub-tabs**: Alerts, Cases, SARs
- **Alerts Section**:
  - List all AML alerts
  - Filter by status and severity
  - View alert details
  - Escalate alert to case
- **Cases Section**:
  - List all AML cases
  - View case details
  - Expand transaction network (graph query)
  - Close cases
- **SARs Section**:
  - List all SARs
  - Create new SAR drafts (manager only)
  - Submit SARs (manager only)
  - View SAR details

**Backend Endpoints Used**:
- `GET /aml/alerts` - List alerts
- `POST /aml/alerts/{id}/escalate` - Escalate to case
- `GET /aml/cases` - List cases
- `POST /aml/cases/{id}/graph-expand` - Expand transaction network
- `POST /aml/cases/{id}/close` - Close case
- `GET /aml/sars` - List SARs
- `POST /aml/sars` - Create SAR
- `POST /aml/sars/{id}/submit` - Submit SAR

## Authorization Flow

### Graph Queries
```
User enters Cypher/Gremlin query
    ↓
Frontend sends to Backend API
    ↓
Backend checks Cerbos authorization
    ↓
IF ALLOWED:
    Backend sends query to PuppyGraph
    ↓
    PuppyGraph executes query
    ↓
    PuppyGraph queries PostgreSQL via JDBC
    ↓
    Results returned to Frontend
IF DENIED:
    HTTP 403 returned to Frontend
```

### AML Operations
```
User clicks action (e.g., "Escalate Alert")
    ↓
Frontend sends request to Backend API
    ↓
Backend checks Cerbos authorization
    ↓
IF ALLOWED:
    Backend executes operation (Trino query)
    ↓
    Results returned to Frontend
IF DENIED:
    HTTP 403 returned to Frontend
```

## UI Components

### Graph Query Interface
- Query language selector (Cypher/Gremlin)
- Query input textarea
- Execute and Clear buttons
- Results display area
- Execution time display

### AML Management Interface
- Tab navigation (Alerts, Cases, SARs)
- Item cards with:
  - Header with ID and status badges
  - Body with details
  - Action buttons
- Refresh buttons for each section
- Create SAR button (manager only)

## Styling

New CSS classes added:
- `.graph-query-interface` - Graph query tab container
- `.graph-results` - Graph query results container
- `.json-results` - JSON formatted results
- `.aml-management-interface` - AML tab container
- `.aml-tabs` - Sub-tab navigation
- `.aml-section` - Sub-tab content sections
- `.aml-item` - Individual alert/case/SAR card
- `.badge-*` - Status badges with color coding

## Next Steps

1. **Rebuild Frontend**: `just rebuild policy-registry-frontend`
2. **Test Graph Queries**: Try Cypher and Gremlin queries
3. **Test AML Management**: Create alerts, escalate to cases, create SARs
4. **Enhance UI**: Add detail views for alerts, cases, and SARs
5. **Graph Visualization**: Add D3.js or similar for graph visualization

## Testing

### Test Graph Query
1. Navigate to "Graph Query" tab
2. Select "openCypher" or "Gremlin"
3. Enter a query
4. Click "Execute Graph Query"
5. Verify results display
6. Check Cerbos logs to see authorization decision

### Test AML Management
1. Navigate to "AML Management" tab
2. Click "Alerts" sub-tab
3. Click "Refresh" to load alerts
4. Click "Escalate to Case" on an alert
5. Switch to "Cases" sub-tab to see new case
6. Click "Expand Graph" to see transaction network
7. Switch to "SARs" sub-tab
8. Click "Create SAR" (manager only)
9. Click "Submit" on a draft SAR

---

**Status**: ✅ UI Implementation Complete  
**Ready for**: Frontend rebuild and testing
