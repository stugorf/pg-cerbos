#!/bin/bash
# Test PuppyGraph edge traversal queries

set -e

echo "🧪 Testing PuppyGraph Edge Queries"

PUPPYGRAPH_URL="http://localhost:8081"
USER="puppygraph"
PASS="puppygraph123"

# Wait for service to be ready (check ConfigurationReady in logs)
echo "⏳ Waiting for PuppyGraph to be ready..."
for i in {1..60}; do
    # Check if ConfigurationReady is true in logs
    if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"ConfigurationReady":true'; then
        # Give it a moment for schema to fully load
        sleep 3
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ PuppyGraph did not become ready in time"
        echo "   Check service status: docker compose ps puppygraph"
        echo "   Check logs: docker logs pg-cerbos-puppygraph | tail -20"
        exit 1
    fi
    sleep 2
done

# Test OWNS edge
echo "📊 Testing OWNS edge (Customer → Account)..."
OWNS_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$OWNS_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ OWNS edge query failed: $(echo "$OWNS_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ OWNS edge query succeeded"
fi

# Test SENT_TXN edge
echo "📊 Testing SENT_TXN edge (Account → Transaction)..."
SENT_TXN_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (a:Account)-[:SENT_TXN]->(t:Transaction) RETURN a, t LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$SENT_TXN_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ SENT_TXN edge query failed: $(echo "$SENT_TXN_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ SENT_TXN edge query succeeded"
fi

# Test FROM_ALERT edge
echo "📊 Testing FROM_ALERT edge (Case → Alert)..."
FROM_ALERT_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (c:Case)-[:FROM_ALERT]->(a:Alert) RETURN c, a LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$FROM_ALERT_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ FROM_ALERT edge query failed: $(echo "$FROM_ALERT_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ FROM_ALERT edge query succeeded"
fi

echo "✅ Edge query tests passed"
