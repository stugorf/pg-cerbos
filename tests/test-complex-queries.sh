#!/bin/bash
# Test PuppyGraph complex multi-hop traversal queries

set -e

echo "🧪 Testing PuppyGraph Complex Queries"

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

# Test complex traversal: Case → Alert → Customer → Account → Transaction
echo "📊 Testing complex traversal (Case → Alert → Customer → Account → Transaction)..."
COMPLEX_QUERY="MATCH (c:Case)-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction) RETURN c, a, cust, acc, txn LIMIT 1"

RESULT=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$COMPLEX_QUERY\"}" \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$RESULT" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Complex query failed: $(echo "$RESULT" | jq -r '.error')"
    exit 1
else
    echo "✅ Complex query succeeded"
fi

# Test another complex traversal: Alert → Customer → Account
echo "📊 Testing Alert → Customer → Account traversal..."
ALERT_CUSTOMER_QUERY="MATCH (a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)-[:OWNS]->(acc:Account) RETURN a, cust, acc LIMIT 1"

RESULT2=$(curl -s -X POST \
  -u "$USER:$PASS" \
  -H "Content-Type: application/json" \
  -d "{\"query\": \"$ALERT_CUSTOMER_QUERY\"}" \
  "$PUPPYGRAPH_URL/api/query" 2>/dev/null || echo '{"error":"Request failed"}')

if echo "$RESULT2" | jq -e '.error' > /dev/null 2>&1; then
    echo "❌ Alert-Customer-Account query failed: $(echo "$RESULT2" | jq -r '.error')"
    exit 1
else
    echo "✅ Alert-Customer-Account query succeeded"
fi

echo "✅ Complex query tests passed"
