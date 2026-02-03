#!/bin/bash
# Activate PuppyGraph schema for query execution
# This script uploads the schema via API to ensure it's fully activated for Bolt protocol queries

set -e

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"
SCHEMA_FILE="puppygraph/aml-schema.json"

echo "🔄 Activating PuppyGraph schema for query execution..."

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo "❌ Schema file not found: $SCHEMA_FILE"
    exit 1
fi

# Wait for PuppyGraph to be ready
echo "⏳ Waiting for PuppyGraph to be ready..."
for i in {1..60}; do
    if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"ConfigurationReady":true'; then
        sleep 5
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ PuppyGraph did not become ready"
        exit 1
    fi
    sleep 2
done

# Upload schema
echo "📤 Uploading schema..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d @"$SCHEMA_FILE" \
  "$PUPPYGRAPH_URL/schema")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -eq 200 ]; then
    STATUS=$(echo "$BODY" | jq -r '.Status // "Unknown"' 2>/dev/null || echo "Unknown")
    if [ "$STATUS" = "OK" ]; then
        echo "✅ Schema activated successfully"
        echo "   Message: $(echo "$BODY" | jq -r '.Message // ""' 2>/dev/null || echo "Schema updated")"
        exit 0
    else
        echo "⚠️  Unexpected status: $STATUS"
        echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
        exit 1
    fi
elif [ "$HTTP_CODE" -eq 400 ]; then
    ERROR_MSG=$(echo "$BODY" | jq -r '.Message // "Unknown error"' 2>/dev/null || echo "Unknown error")
    if echo "$ERROR_MSG" | grep -q "duplicate aliases"; then
        echo "⚠️  Schema uploaded with duplicate alias warnings (may need alias fixes)"
        echo "   Error: $ERROR_MSG"
        exit 1
    else
        echo "❌ Schema activation failed: $ERROR_MSG"
        exit 1
    fi
else
    echo "❌ Unexpected response: HTTP $HTTP_CODE"
    echo "$BODY" | jq . 2>/dev/null || echo "$BODY"
    exit 1
fi
