#!/bin/bash
# Test PuppyGraph vertex queries

set -e

echo "🧪 Testing PuppyGraph Vertex Queries"

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

# Test Customer query
echo "📊 Testing Customer query..."
CUSTOMER_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (c:Customer) RETURN c LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$CUSTOMER_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Customer query failed: $(echo "$CUSTOMER_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Customer query succeeded"
fi

# Test Account query
echo "📊 Testing Account query..."
ACCOUNT_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (a:Account) RETURN a LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$ACCOUNT_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Account query failed: $(echo "$ACCOUNT_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Account query succeeded"
fi

# Test Transaction query
echo "📊 Testing Transaction query..."
TRANSACTION_RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d '{"query": "MATCH (t:Transaction) RETURN t LIMIT 1"}' \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$TRANSACTION_RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Transaction query failed: $(echo "$TRANSACTION_RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Transaction query succeeded"
fi

echo "✅ Vertex query tests passed"
