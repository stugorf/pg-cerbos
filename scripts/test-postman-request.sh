#!/bin/bash
# Test the exact Postman request format

set -e

echo "🧪 Testing Postman Request Format"
echo "=================================="
echo ""

# Test 1: Using curl (equivalent to Postman)
echo "Test 1: POST request with headers and body"
echo "------------------------------------------"
RESPONSE=$(curl -v -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@ues-mvp.com' \
  -H 'x-user-roles: full_access_user' \
  -H 'Content-Type: text/plain' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement 2>&1)

echo "$RESPONSE"
echo ""

# Check if we got "Not Found"
if echo "$RESPONSE" | grep -q "detail.*Not Found"; then
    echo "❌ Got 'Not Found' error"
    echo ""
    echo "Checking what might be wrong..."
    echo ""
    
    # Check if Envoy is running
    echo "Checking Envoy status..."
    docker compose ps envoy 2>&1 | grep envoy || echo "Envoy not found in docker compose ps"
    echo ""
    
    # Check adapter logs
    echo "Recent adapter logs:"
    docker compose logs cerbos-adapter --tail=20 2>&1 | tail -10
    echo ""
    
    # Check Envoy logs
    echo "Recent Envoy logs:"
    docker compose logs envoy --tail=20 2>&1 | tail -10
else
    echo "✅ Request succeeded or got different response"
fi
