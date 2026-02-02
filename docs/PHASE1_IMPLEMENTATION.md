# Phase 1 Implementation: Cypher Query Parsing

## Summary

Phase 1 of the RBAC/ABAC enhancement has been completed. This phase implements Cypher query parsing to extract metadata for authorization purposes.

## What Was Implemented

### 1. Cypher Parser Module (`cypher_parser.py`)

A comprehensive Cypher query parser that extracts:

- **Node Labels**: All node types referenced in the query (Customer, Transaction, Account, etc.)
- **Relationship Types**: All relationship types (OWNS, SENT_TXN, TO_ACCOUNT, etc.)
- **Traversal Depth**: Maximum number of hops in the query
- **Query Patterns**: Type of query (simple, path, multi_match, with_clause, union)
- **Path Variables**: Named path variables in the query
- **Aggregation Functions**: Detection of COUNT, SUM, AVG, etc.
- **Query Clauses**: WHERE, ORDER BY, LIMIT detection
- **Resource Attributes**: Extraction of attributes from WHERE clauses (risk_rating, amount, pep_flag, etc.)
- **Complexity Estimates**: Estimated node and edge counts

### 2. Integration with Authorization Flow

**Updated Files:**
- `app.py`: `/query/graph` endpoint now parses Cypher queries before authorization
- `cerbos_client.py`: Enhanced to support additional principal and resource attributes
- `Dockerfile`: Updated to include `cypher_parser.py`

**Authorization Flow:**
1. User submits Cypher query via `/query/graph` endpoint
2. Query is parsed to extract metadata
3. Resource attributes are extracted from WHERE clauses
4. All metadata is passed to Cerbos for authorization
5. Cerbos evaluates policies based on parsed metadata
6. Decision is logged and enforced

### 3. Unit Tests

Comprehensive test suite (`test_cypher_parser.py`) covering:
- Node label extraction
- Relationship type extraction
- Traversal depth calculation
- Aggregation function detection
- Query pattern detection
- Path variable extraction
- Resource attribute extraction
- Query clause detection
- Full query parsing

## Example Usage

### Before (Basic Authorization)
```python
# Only query_type was passed to Cerbos
allowed, reason, policy = cerbos_client.check_resource_access(
    user_id=str(current_user.id),
    user_email=current_user.email,
    user_roles=user_roles,
    resource_kind="transaction",
    resource_id="graph-query",
    action="graph_expand",
    attributes={"query_type": "cypher"}
)
```

### After (Enhanced Authorization)
```python
# Query is parsed and metadata is extracted
cypher_metadata = parse_cypher_query(query)
resource_attributes = extract_resource_attributes(query)

# All metadata is passed to Cerbos
allowed, reason, policy = cerbos_client.check_resource_access(
    user_id=str(current_user.id),
    user_email=current_user.email,
    user_roles=user_roles,
    resource_kind="cypher_query",
    resource_id="graph-query",
    action="execute",
    attributes={
        "query_type": "cypher",
        "query": query,
        **cypher_metadata,  # node_labels, relationship_types, max_depth, etc.
        **resource_attributes  # risk_rating, transaction_amount, pep_flag, etc.
    }
)
```

## Parsed Metadata Structure

```python
{
    "node_labels": ["Customer", "Account", "Transaction"],  # Set converted to list
    "relationship_types": ["OWNS", "SENT_TXN"],  # Set converted to list
    "max_depth": 2,  # Number of hops
    "has_aggregations": False,  # Boolean
    "query_pattern": "simple",  # simple, path, multi_match, with_clause, union
    "path_variables": [],  # List of path variable names
    "has_where_clause": True,  # Boolean
    "has_order_by": True,  # Boolean
    "has_limit": True,  # Boolean
    "estimated_nodes": 30,  # Rough estimate
    "estimated_edges": 20,  # Rough estimate
    # Resource attributes from WHERE clauses:
    "risk_rating": "high",  # Extracted from WHERE clause
    "transaction_amount_min": 50000.0,  # Extracted from WHERE clause
    "pep_flag": True,  # Extracted from WHERE clause or node properties
    "severity": "high"  # Extracted from WHERE clause
}
```

## Example Queries and Parsed Results

### Example 1: Simple Query
```cypher
MATCH (c:Customer) WHERE c.risk_rating = 'high' RETURN c
```

**Parsed Metadata:**
- `node_labels`: ["Customer"]
- `relationship_types`: []
- `max_depth`: 0
- `has_where_clause`: True
- `risk_rating`: "high"

### Example 2: Complex Path Query
```cypher
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
WHERE txn.amount > 50000
RETURN path
LIMIT 10
```

**Parsed Metadata:**
- `node_labels`: ["Customer", "Account", "Transaction"]
- `relationship_types`: ["OWNS", "SENT_TXN", "TO_ACCOUNT"]
- `max_depth`: 3
- `query_pattern`: "path"
- `path_variables`: ["path"]
- `has_where_clause`: True
- `has_limit`: True
- `transaction_amount_min`: 50000.0

### Example 3: Aggregation Query
```cypher
MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 50000
WITH cust, COUNT(txn) as high_value_count, SUM(txn.amount) as total_amount
RETURN cust, high_value_count, total_amount
```

**Parsed Metadata:**
- `node_labels`: ["Customer", "Account", "Transaction"]
- `relationship_types`: ["OWNS", "SENT_TXN"]
- `max_depth`: 2
- `has_aggregations`: True
- `query_pattern`: "with_clause"
- `transaction_amount_min`: 50000.0

## Next Steps

Phase 1 is complete. The next phases are:

### Phase 2: Enhanced RBAC (Next)
- Create `cypher_query.yaml` Cerbos policy
- Implement role-based restrictions (depth, node types, etc.)
- Create role hierarchy using derived roles

### Phase 3: Enhanced ABAC
- Add user attributes (team, region, clearance_level)
- Enhance resource attribute extraction
- Create attribute-based policies

### Phase 4: Query Complexity Analysis
- Improve complexity estimation
- Add execution time limits
- Add result set size limits

## Testing

Run the unit tests:
```bash
cd policy-registry/backend
pytest test_cypher_parser.py -v
```

Or using just:
```bash
just test-cypher-parser  # (if added to Justfile)
```

## Files Modified

1. **`policy-registry/backend/cypher_parser.py`** (NEW)
   - Complete Cypher query parser implementation

2. **`policy-registry/backend/app.py`**
   - Updated `/query/graph` endpoint to use parser
   - Integrated parsed metadata into Cerbos authorization

3. **`policy-registry/backend/cerbos_client.py`**
   - Added `principal_attributes` parameter to `check_resource_access`
   - Enhanced attribute handling for sets/lists

4. **`policy-registry/backend/Dockerfile`**
   - Added `cypher_parser.py` to COPY command

5. **`policy-registry/backend/test_cypher_parser.py`** (NEW)
   - Comprehensive unit test suite

## Notes

- Sets are converted to comma-separated strings for Cerbos compatibility
- The parser uses regex patterns - it's not a full Cypher parser but sufficient for authorization
- Error handling: If parsing fails, the system falls back to basic authorization
- The parser handles common Cypher patterns but may not cover all edge cases

## Backward Compatibility

- Gremlin queries continue to use the existing authorization flow
- Cypher queries now use enhanced authorization with parsing
- Existing policies continue to work (backward compatible)
- New `cypher_query` resource kind is used for Cypher queries, but `transaction` is still supported
