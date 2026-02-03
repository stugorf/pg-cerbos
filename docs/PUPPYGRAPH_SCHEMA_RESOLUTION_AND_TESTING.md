# PuppyGraph Schema Resolution and Testing Guide

## Executive Summary

This document summarizes the journey to successfully configure PuppyGraph 0.112 to load and validate the AML schema, and provides guidance for creating tests and regression tests to prevent future issues.

## Resolution Journey

### Initial Problem
- PuppyGraph schema was not loading from `SCHEMA_PATH` environment variable
- Schema did not appear in the UI
- Schema validation failed with error 244

### Key Steps Taken

#### 1. Version Upgrade (0.108 → 0.112)
**Issue**: PuppyGraph 0.108 had known validation issues with PostgreSQL metadata access.

**Solution**: Upgraded to PuppyGraph 0.112
```yaml
# compose.yml
puppygraph:
  image: puppygraph/puppygraph:0.112
```

**Result**: Newer version with improved validation logic.

#### 2. Schema Format Correction
**Issue**: PuppyGraph 0.112 rejected the `mappedTableSource` format with errors:
- `meaningless key 'mappedTableSource from to'`
- `fromVertex: missing name`
- `tableSource: is required`
- `fromId: is required`
- `toId: is required`

**Root Cause**: Discrepancy between API documentation format and JSON file format:
- **API Documentation**: Uses `mappedTableSource` with `metaFields` (simple string mappings)
- **JSON File Format (0.112)**: Requires `tableSource` with `fromVertex`/`toVertex` and complex field objects

**Solution**: Converted all 8 edges from `mappedTableSource` to `tableSource` format:

**Before (Rejected)**:
```json
{
  "label": "OWNS",
  "from": "Customer",
  "to": "Account",
  "mappedTableSource": {
    "catalog": "aml_postgres",
    "schema": "aml",
    "table": "account",
    "metaFields": {
      "id": "account_id",
      "from": "customer_id",
      "to": "account_id"
    }
  },
  "attributes": []
}
```

**After (Accepted)**:
```json
{
  "label": "OWNS",
  "fromVertex": "Customer",
  "toVertex": "Account",
  "tableSource": {
    "catalog": "aml_postgres",
    "schema": "aml",
    "table": "account"
  },
  "id": {
    "fields": [
      {
        "type": "Int",
        "field": "account_id",
        "alias": "account_id"
      }
    ]
  },
  "fromId": {
    "fields": [
      {
        "type": "Int",
        "field": "customer_id",
        "alias": "customer_id"
      }
    ]
  },
  "toId": {
    "fields": [
      {
        "type": "Int",
        "field": "account_id",
        "alias": "account_id"
      }
    ]
  }
}
```

**Key Changes**:
1. `from`/`to` → `fromVertex`/`toVertex`
2. `mappedTableSource` → `tableSource`
3. `metaFields` → `id`/`fromId`/`toId` field objects
4. Removed `attributes` arrays
5. Added unique aliases for edges sharing source tables

#### 3. Edge ID Uniqueness
**Issue**: Multiple edges share the same source table and ID field, causing potential conflicts.

**Solution**: Added unique aliases for edge IDs:
- `SENT_TXN`: Uses alias `sent_txn_id`
- `TO_ACCOUNT`: Uses alias `to_account_id`
- `FLAGS_CUSTOMER`: Uses alias `flags_customer_id`
- `FLAGS_ACCOUNT`: Uses alias `flags_account_id`
- `FROM_ALERT`: Uses alias `from_alert_id`

#### 4. Configuration Verification
**Verified**:
- ✅ `SCHEMA_PATH=/puppygraph/conf/aml-schema.json` environment variable set
- ✅ Schema file exists and is readable in container
- ✅ Volume mount: `./puppygraph:/puppygraph/conf:ro`
- ✅ Schema loads at startup: "Starting gremlin server, with initial schema"
- ✅ `ConfigurationReady: true` in status

### Final Working Configuration

**compose.yml**:
```yaml
puppygraph:
  image: puppygraph/puppygraph:0.112
  environment:
    - SCHEMA_PATH=/puppygraph/conf/aml-schema.json
  volumes:
    - ./puppygraph:/puppygraph/conf:ro
```

**Schema Structure**:
- 7 vertices: Customer, Account, Transaction, Alert, Case, CaseNote, SAR
- 8 edges: OWNS, SENT_TXN, TO_ACCOUNT, FLAGS_CUSTOMER, FLAGS_ACCOUNT, FROM_ALERT, HAS_NOTE, RESULTED_IN
- All edges use `tableSource` format with `fromVertex`/`toVertex` and `id`/`fromId`/`toId` field objects

## Testing Strategy

### 1. Schema Loading Tests

#### Test: Schema Loads at Startup
**Purpose**: Verify schema loads automatically via `SCHEMA_PATH`

**Test Steps**:
```bash
# 1. Restart PuppyGraph
docker compose restart puppygraph

# 2. Wait for startup
sleep 15

# 3. Check logs for schema loading
docker logs pg-cerbos-puppygraph 2>&1 | grep -i "initial schema"

# 4. Verify ConfigurationReady status
docker logs pg-cerbos-puppygraph 2>&1 | grep "ConfigurationReady" | tail -1
```

**Expected Results**:
- ✅ Logs show: "Starting gremlin server, with initial schema"
- ✅ `"ConfigurationReady":true`
- ✅ `"Healthy":true`

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-schema-loading.sh

set -e

echo "🧪 Testing PuppyGraph Schema Loading"

# Restart service
docker compose restart puppygraph
sleep 15

# Check schema loading
if docker logs pg-cerbos-puppygraph 2>&1 | grep -q "initial schema"; then
    echo "✅ Schema loading message found"
else
    echo "❌ Schema loading message not found"
    exit 1
fi

# Check configuration ready
if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"ConfigurationReady":true'; then
    echo "✅ Configuration ready"
else
    echo "❌ Configuration not ready"
    exit 1
fi

echo "✅ Schema loading test passed"
```

#### Test: Schema Appears in UI
**Purpose**: Verify schema is accessible via API and UI

**Test Steps**:
```bash
# 1. Check schema API endpoint
curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq '.graph.vertices | length'

# 2. Verify vertices count
# Expected: 7

# 3. Verify edges count
curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq '.graph.edges | length'
# Expected: 8
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-schema-api.sh

set -e

echo "🧪 Testing PuppyGraph Schema API"

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"

# Get schema
SCHEMA=$(curl -s -u "$USER:$PASS" "$PUPPYGRAPH_URL/schemajson")

# Check for errors
if echo "$SCHEMA" | jq -e '.Status == "Error"' > /dev/null 2>&1; then
    echo "❌ Schema API returned error: $(echo "$SCHEMA" | jq -r '.Message')"
    exit 1
fi

# Verify vertex count
VERTEX_COUNT=$(echo "$SCHEMA" | jq '.graph.vertices | length')
if [ "$VERTEX_COUNT" -eq 7 ]; then
    echo "✅ Vertex count correct: $VERTEX_COUNT"
else
    echo "❌ Vertex count incorrect: expected 7, got $VERTEX_COUNT"
    exit 1
fi

# Verify edge count
EDGE_COUNT=$(echo "$SCHEMA" | jq '.graph.edges | length')
if [ "$EDGE_COUNT" -eq 8 ]; then
    echo "✅ Edge count correct: $EDGE_COUNT"
else
    echo "❌ Edge count incorrect: expected 8, got $EDGE_COUNT"
    exit 1
fi

echo "✅ Schema API test passed"
```

#### Test: Schema Validation
**Purpose**: Verify schema passes validation in PuppyGraph

**Test Steps**:
```bash
# 1. Upload schema via API
curl -X POST -u puppygraph:puppygraph123 \
  -H "Content-Type: application/json" \
  -d @puppygraph/aml-schema.json \
  http://localhost:8081/schema

# 2. Check response for errors
# Expected: No validation errors
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-schema-validation.sh

set -e

echo "🧪 Testing PuppyGraph Schema Validation"

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"
SCHEMA_FILE="puppygraph/aml-schema.json"

# Upload schema
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d @"$SCHEMA_FILE" \
  "$PUPPYGRAPH_URL/schema")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo "✅ Schema validation passed (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" -eq 400 ]; then
    echo "❌ Schema validation failed (HTTP $HTTP_CODE)"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
    exit 1
else
    echo "⚠️  Unexpected response (HTTP $HTTP_CODE)"
    echo "$BODY"
    exit 1
fi

echo "✅ Schema validation test passed"
```

### 2. Query Execution Tests

#### Test: Basic Vertex Queries
**Purpose**: Verify vertices can be queried

**Test Queries**:
```cypher
// Test 1: Get all customers
MATCH (c:Customer) RETURN c LIMIT 5

// Test 2: Get all accounts
MATCH (a:Account) RETURN a LIMIT 5

// Test 3: Get all transactions
MATCH (t:Transaction) RETURN t LIMIT 5
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-vertex-queries.sh

set -e

echo "🧪 Testing PuppyGraph Vertex Queries"

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"

# Test Customer query
CUSTOMER_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (c:Customer) RETURN c LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query")

if echo "$CUSTOMER_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Customer query failed: $(echo "$CUSTOMER_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Customer query succeeded"
fi

# Test Account query
ACCOUNT_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (a:Account) RETURN a LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query")

if echo "$ACCOUNT_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Account query failed: $(echo "$ACCOUNT_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Account query succeeded"
fi

echo "✅ Vertex query tests passed"
```

#### Test: Edge Traversal Queries
**Purpose**: Verify edges can be traversed

**Test Queries**:
```cypher
// Test 1: Customer owns Account
MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 5

// Test 2: Account sent Transaction
MATCH (a:Account)-[:SENT_TXN]->(t:Transaction) RETURN a, t LIMIT 5

// Test 3: Case from Alert
MATCH (c:Case)-[:FROM_ALERT]->(a:Alert) RETURN c, a LIMIT 5
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-edge-queries.sh

set -e

echo "🧪 Testing PuppyGraph Edge Queries"

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"

# Test OWNS edge
OWNS_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query")

if echo "$OWNS_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ OWNS edge query failed: $(echo "$OWNS_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ OWNS edge query succeeded"
fi

# Test SENT_TXN edge
SENT_TXN_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (a:Account)-[:SENT_TXN]->(t:Transaction) RETURN a, t LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query")

if echo "$SENT_TXN_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ SENT_TXN edge query failed: $(echo "$SENT_TXN_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ SENT_TXN edge query succeeded"
fi

echo "✅ Edge query tests passed"
```

#### Test: Complex Graph Queries
**Purpose**: Verify complex multi-hop traversals work

**Test Queries**:
```cypher
// Test: Case → Alert → Customer → Account → Transaction
MATCH (c:Case)-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
      -[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
RETURN c, a, cust, acc, txn LIMIT 5
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-complex-queries.sh

set -e

echo "🧪 Testing PuppyGraph Complex Queries"

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"

COMPLEX_QUERY="MATCH (c:Case)-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction) RETURN c, a, cust, acc, txn LIMIT 1"

RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$COMPLEX_QUERY\"}" \
  "$PUPPYGRAPH_URL/api/query")

if echo "$RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Complex query failed: $(echo "$RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Complex query succeeded"
fi

echo "✅ Complex query test passed"
```

### 3. Regression Tests

#### Test: Schema Format Validation
**Purpose**: Ensure schema format remains compatible with PuppyGraph 0.112

**Test Steps**:
```bash
# 1. Validate JSON structure
cat puppygraph/aml-schema.json | jq . > /dev/null

# 2. Check all edges use tableSource format
cat puppygraph/aml-schema.json | jq '.graph.edges[] | select(.mappedTableSource != null)'

# 3. Check all edges have fromVertex/toVertex
cat puppygraph/aml-schema.json | jq '.graph.edges[] | select(.fromVertex == null or .toVertex == null)'

# 4. Check all edges have id/fromId/toId
cat puppygraph/aml-schema.json | jq '.graph.edges[] | select(.id == null or .fromId == null or .toId == null)'
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-schema-format.sh

set -e

echo "🧪 Testing PuppyGraph Schema Format"

SCHEMA_FILE="puppygraph/aml-schema.json"

# Validate JSON
if ! cat "$SCHEMA_FILE" | jq . > /dev/null 2>&1; then
    echo "❌ Schema JSON is invalid"
    exit 1
fi
echo "✅ Schema JSON is valid"

# Check for mappedTableSource (should not exist)
if cat "$SCHEMA_FILE" | jq -e '.graph.edges[] | select(.mappedTableSource != null)' > /dev/null 2>&1; then
    echo "❌ Schema contains mappedTableSource (should use tableSource)"
    exit 1
fi
echo "✅ No mappedTableSource found"

# Check for from/to (should not exist)
if cat "$SCHEMA_FILE" | jq -e '.graph.edges[] | select(.from != null or .to != null)' > /dev/null 2>&1; then
    echo "❌ Schema contains from/to (should use fromVertex/toVertex)"
    exit 1
fi
echo "✅ No from/to found"

# Check all edges have required fields
MISSING_FIELDS=$(cat "$SCHEMA_FILE" | jq -r '.graph.edges[] | select(.fromVertex == null or .toVertex == null or .tableSource == null or .id == null or .fromId == null or .toId == null) | .label')

if [ -n "$MISSING_FIELDS" ]; then
    echo "❌ Edges missing required fields: $MISSING_FIELDS"
    exit 1
fi
echo "✅ All edges have required fields"

echo "✅ Schema format test passed"
```

#### Test: Version Compatibility
**Purpose**: Ensure schema works with PuppyGraph 0.112

**Test Steps**:
```bash
# 1. Check PuppyGraph version
docker exec pg-cerbos-puppygraph cat /puppygraph/version 2>/dev/null || \
  docker logs pg-cerbos-puppygraph 2>&1 | grep -i "version" | head -1

# 2. Verify version is 0.112
# Expected: version 0.112
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-version-compatibility.sh

set -e

echo "🧪 Testing PuppyGraph Version Compatibility"

# Check version from logs
VERSION=$(docker logs pg-cerbos-puppygraph 2>&1 | grep -i "version" | head -1 | grep -oE "0\.\d+" | head -1)

if [ -z "$VERSION" ]; then
    echo "⚠️  Could not determine PuppyGraph version"
    exit 1
fi

echo "📦 PuppyGraph version: $VERSION"

# Check if version is 0.112 or higher
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)

if [ "$MAJOR" -eq 0 ] && [ "$MINOR" -ge 112 ]; then
    echo "✅ Version is compatible (0.112+)"
else
    echo "⚠️  Version may not be compatible (expected 0.112+, got $VERSION)"
    exit 1
fi

echo "✅ Version compatibility test passed"
```

#### Test: Configuration Persistence
**Purpose**: Ensure schema loads correctly after container restart

**Test Steps**:
```bash
# 1. Restart PuppyGraph
docker compose restart puppygraph

# 2. Wait for startup
sleep 20

# 3. Verify schema loaded
docker logs pg-cerbos-puppygraph 2>&1 | grep -i "ConfigurationReady" | tail -1

# 4. Verify schema accessible
curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq '.graph.vertices | length'
```

**Automated Test Script**:
```bash
#!/bin/bash
# tests/test-configuration-persistence.sh

set -e

echo "🧪 Testing PuppyGraph Configuration Persistence"

# Restart service
echo "🔄 Restarting PuppyGraph..."
docker compose restart puppygraph
sleep 20

# Check configuration ready
if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"ConfigurationReady":true'; then
    echo "✅ Configuration ready after restart"
else
    echo "❌ Configuration not ready after restart"
    exit 1
fi

# Check schema accessible
VERTEX_COUNT=$(curl -s -u puppygraph:puppygraph123 http://localhost:8081/schemajson | jq '.graph.vertices | length')

if [ "$VERTEX_COUNT" -eq 7 ]; then
    echo "✅ Schema accessible after restart (vertices: $VERTEX_COUNT)"
else
    echo "❌ Schema not accessible after restart (vertices: $VERTEX_COUNT, expected 7)"
    exit 1
fi

echo "✅ Configuration persistence test passed"
```

## Test Suite Integration

### Adding Tests to Justfile

Add these recipes to `Justfile`:

```justfile
# Test PuppyGraph schema loading
test-puppygraph-schema:
    bash tests/test-schema-loading.sh

# Test PuppyGraph schema API
test-puppygraph-api:
    bash tests/test-schema-api.sh

# Test PuppyGraph schema validation
test-puppygraph-validation:
    bash tests/test-schema-validation.sh

# Test PuppyGraph vertex queries
test-puppygraph-vertices:
    bash tests/test-vertex-queries.sh

# Test PuppyGraph edge queries
test-puppygraph-edges:
    bash tests/test-edge-queries.sh

# Test PuppyGraph complex queries
test-puppygraph-complex:
    bash tests/test-complex-queries.sh

# Test PuppyGraph schema format
test-puppygraph-format:
    bash tests/test-schema-format.sh

# Test PuppyGraph version compatibility
test-puppygraph-version:
    bash tests/test-version-compatibility.sh

# Test PuppyGraph configuration persistence
test-puppygraph-persistence:
    bash tests/test-configuration-persistence.sh

# Run all PuppyGraph tests
test-puppygraph-all:
    just test-puppygraph-schema
    just test-puppygraph-api
    just test-puppygraph-validation
    just test-puppygraph-format
    just test-puppygraph-version
    just test-puppygraph-vertices
    just test-puppygraph-edges
    just test-puppygraph-complex
    just test-puppygraph-persistence
```

### Python Test Suite

Create `tests/test_puppygraph_schema.py`:

```python
"""Tests for PuppyGraph schema loading and validation."""

import pytest
import requests
import json
from pathlib import Path


class TestPuppyGraphSchema:
    """Test suite for PuppyGraph schema functionality."""
    
    BASE_URL = "http://localhost:8081"
    USERNAME = "puppygraph"
    PASSWORD = "puppygraph123"
    SCHEMA_FILE = Path("puppygraph/aml-schema.json")
    
    @pytest.fixture
    def auth(self):
        """Basic auth tuple for requests."""
        return (self.USERNAME, self.PASSWORD)
    
    def test_schema_file_exists(self):
        """Test that schema file exists."""
        assert self.SCHEMA_FILE.exists(), "Schema file not found"
    
    def test_schema_file_valid_json(self):
        """Test that schema file is valid JSON."""
        with open(self.SCHEMA_FILE) as f:
            schema = json.load(f)
        assert "catalogs" in schema
        assert "graph" in schema
        assert "vertices" in schema["graph"]
        assert "edges" in schema["graph"]
    
    def test_schema_format(self, auth):
        """Test that schema uses correct format for PuppyGraph 0.112."""
        with open(self.SCHEMA_FILE) as f:
            schema = json.load(f)
        
        # Check all edges use tableSource format
        for edge in schema["graph"]["edges"]:
            assert "tableSource" in edge, f"Edge {edge['label']} missing tableSource"
            assert "fromVertex" in edge, f"Edge {edge['label']} missing fromVertex"
            assert "toVertex" in edge, f"Edge {edge['label']} missing toVertex"
            assert "id" in edge, f"Edge {edge['label']} missing id"
            assert "fromId" in edge, f"Edge {edge['label']} missing fromId"
            assert "toId" in edge, f"Edge {edge['label']} missing toId"
            
            # Should not have mappedTableSource
            assert "mappedTableSource" not in edge, \
                f"Edge {edge['label']} should not use mappedTableSource"
            assert "from" not in edge, \
                f"Edge {edge['label']} should not use 'from' (use 'fromVertex')"
            assert "to" not in edge, \
                f"Edge {edge['label']} should not use 'to' (use 'toVertex')"
    
    def test_schema_api_accessible(self, auth):
        """Test that schema is accessible via API."""
        response = requests.get(
            f"{self.BASE_URL}/schemajson",
            auth=auth,
            timeout=10
        )
        assert response.status_code == 200, \
            f"Schema API returned {response.status_code}"
        
        schema = response.json()
        assert "graph" in schema
        assert len(schema["graph"]["vertices"]) == 7
        assert len(schema["graph"]["edges"]) == 8
    
    def test_schema_validation(self, auth):
        """Test that schema passes validation."""
        with open(self.SCHEMA_FILE) as f:
            schema_data = f.read()
        
        response = requests.post(
            f"{self.BASE_URL}/schema",
            auth=auth,
            headers={"Content-Type": "application/json"},
            data=schema_data,
            timeout=30
        )
        
        assert response.status_code == 200, \
            f"Schema validation failed: {response.status_code} - {response.text}"
    
    def test_vertex_query(self, auth):
        """Test basic vertex query."""
        query = {"query": "MATCH (c:Customer) RETURN c LIMIT 1"}
        response = requests.post(
            f"{self.BASE_URL}/api/query",
            auth=auth,
            json=query,
            timeout=30
        )
        assert response.status_code == 200, \
            f"Vertex query failed: {response.status_code}"
        assert "error" not in response.json(), \
            f"Query returned error: {response.json()}"
    
    def test_edge_query(self, auth):
        """Test basic edge traversal query."""
        query = {"query": "MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1"}
        response = requests.post(
            f"{self.BASE_URL}/api/query",
            auth=auth,
            json=query,
            timeout=30
        )
        assert response.status_code == 200, \
            f"Edge query failed: {response.status_code}"
        assert "error" not in response.json(), \
            f"Query returned error: {response.json()}"
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: PuppyGraph Schema Tests

on:
  push:
    paths:
      - 'puppygraph/aml-schema.json'
      - 'compose.yml'
  pull_request:
    paths:
      - 'puppygraph/aml-schema.json'
      - 'compose.yml'

jobs:
  test-schema:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start services
        run: |
          docker compose up -d
          sleep 30
      
      - name: Test schema format
        run: just test-puppygraph-format
      
      - name: Test schema loading
        run: just test-puppygraph-schema
      
      - name: Test schema validation
        run: just test-puppygraph-validation
      
      - name: Test queries
        run: |
          just test-puppygraph-vertices
          just test-puppygraph-edges
          just test-puppygraph-complex
```

## Monitoring and Alerts

### Health Check Endpoint

Create a health check script that can be called by monitoring systems:

```bash
#!/bin/bash
# scripts/health-check-puppygraph.sh

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"

# Check service health
HEALTH=$(curl -s -u "$USER:$PASS" "$PUPPYGRAPH_URL/api/health" 2>/dev/null)

if [ $? -ne 0 ] || [ -z "$HEALTH" ]; then
    echo "❌ PuppyGraph service is down"
    exit 1
fi

# Check schema accessible
SCHEMA=$(curl -s -u "$USER:$PASS" "$PUPPYGRAPH_URL/schemajson" 2>/dev/null)

if echo "$SCHEMA" | jq -e '.Status == "Error"' > /dev/null 2>&1; then
    echo "❌ Schema is not accessible"
    exit 1
fi

# Check vertex count
VERTEX_COUNT=$(echo "$SCHEMA" | jq '.graph.vertices | length')

if [ "$VERTEX_COUNT" -ne 7 ]; then
    echo "⚠️  Unexpected vertex count: $VERTEX_COUNT (expected 7)"
    exit 1
fi

echo "✅ PuppyGraph is healthy"
exit 0
```

## Best Practices

1. **Version Pinning**: Always pin PuppyGraph version in `compose.yml` to prevent unexpected changes
2. **Schema Validation**: Run schema format tests before committing changes
3. **Query Testing**: Test all edge types after schema changes
4. **Documentation**: Keep schema format documentation up to date
5. **Regression Testing**: Run full test suite after PuppyGraph version upgrades

## Troubleshooting

### Schema Not Loading
1. Check `SCHEMA_PATH` environment variable
2. Verify schema file exists in container
3. Check logs for validation errors
4. Verify schema format matches PuppyGraph 0.112 requirements

### Validation Failing
1. Check schema format (should use `tableSource`, not `mappedTableSource`)
2. Verify all edges have `fromVertex`/`toVertex` and `id`/`fromId`/`toId`
3. Check for JSON syntax errors
4. Verify PostgreSQL connection is working

### Queries Failing
1. Verify schema is loaded and validated
2. Check PostgreSQL tables exist and have data
3. Verify edge field mappings match actual table columns
4. Check PuppyGraph logs for detailed error messages

## References

- [PuppyGraph Schema Documentation](https://docs.puppygraph.com/reference/schema/)
- [PuppyGraph 0.112 Release Notes](https://docs.puppygraph.com/releases)
- `docs/SCHEMA_FORMAT_FIX_0.112.md` - Detailed format fix documentation
- `docs/SCHEMA_LOADING_VERIFICATION.md` - Schema loading verification guide
