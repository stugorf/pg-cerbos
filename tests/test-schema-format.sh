#!/bin/bash
# Test PuppyGraph schema format compliance

set -e

echo "🧪 Testing PuppyGraph Schema Format"

SCHEMA_FILE="puppygraph/aml-schema.json"

# Check schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo "❌ Schema file not found: $SCHEMA_FILE"
    exit 1
fi

# Validate JSON
if ! cat "$SCHEMA_FILE" | jq . > /dev/null 2>&1; then
    echo "❌ Schema JSON is invalid"
    exit 1
fi
echo "✅ Schema JSON is valid"

# Check for mappedTableSource (should not exist)
if cat "$SCHEMA_FILE" | jq -e '.graph.edges[] | select(.mappedTableSource != null)' > /dev/null 2>&1; then
    echo "❌ Schema contains mappedTableSource (should use tableSource)"
    echo "   Edges with mappedTableSource:"
    cat "$SCHEMA_FILE" | jq -r '.graph.edges[] | select(.mappedTableSource != null) | .label'
    exit 1
fi
echo "✅ No mappedTableSource found"

# Check for from/to (should not exist)
if cat "$SCHEMA_FILE" | jq -e '.graph.edges[] | select(.from != null or .to != null)' > /dev/null 2>&1; then
    echo "❌ Schema contains from/to (should use fromVertex/toVertex)"
    echo "   Edges with from/to:"
    cat "$SCHEMA_FILE" | jq -r '.graph.edges[] | select(.from != null or .to != null) | .label'
    exit 1
fi
echo "✅ No from/to found"

# Check all edges have required fields
MISSING_FIELDS=$(cat "$SCHEMA_FILE" | jq -r '.graph.edges[] | select(.fromVertex == null or .toVertex == null or .tableSource == null or .id == null or .fromId == null or .toId == null) | .label')

if [ -n "$MISSING_FIELDS" ]; then
    echo "❌ Edges missing required fields:"
    echo "$MISSING_FIELDS"
    exit 1
fi
echo "✅ All edges have required fields (fromVertex, toVertex, tableSource, id, fromId, toId)"

# Check all vertices have required fields
MISSING_VERTEX_FIELDS=$(cat "$SCHEMA_FILE" | jq -r '.graph.vertices[] | select(.label == null or .oneToOne == null) | .label')

if [ -n "$MISSING_VERTEX_FIELDS" ]; then
    echo "❌ Vertices missing required fields:"
    echo "$MISSING_VERTEX_FIELDS"
    exit 1
fi
echo "✅ All vertices have required fields (label, oneToOne)"

# Verify catalog configuration
CATALOG_COUNT=$(cat "$SCHEMA_FILE" | jq '.catalogs | length')
if [ "$CATALOG_COUNT" -eq 0 ]; then
    echo "❌ No catalogs defined"
    exit 1
fi
echo "✅ Catalog configuration found ($CATALOG_COUNT catalog(s))"

echo "✅ Schema format test passed"
