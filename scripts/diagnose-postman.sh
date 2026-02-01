#!/bin/bash
# Diagnostic script for Postman/API requests

set -e

echo "🔍 Diagnosing Postman Request Issue"
echo "===================================="
echo ""

# Check if Envoy is running
echo "1. Checking Envoy status..."
if docker compose ps envoy 2>/dev/null | grep -q "Up"; then
    echo "   ✅ Envoy is running"
else
    echo "   ❌ Envoy is NOT running"
    echo "   → Start with: docker compose up -d envoy"
    exit 1
fi
echo ""

# Check if adapter is running
echo "2. Checking Cerbos Adapter status..."
if docker compose ps cerbos-adapter 2>/dev/null | grep -q "Up"; then
    echo "   ✅ Cerbos Adapter is running"
else
    echo "   ❌ Cerbos Adapter is NOT running"
    exit 1
fi
echo ""

# Check if Trino is running
echo "3. Checking Trino status..."
if docker compose ps trino-coordinator 2>/dev/null | grep -q "Up"; then
    echo "   ✅ Trino is running"
else
    echo "   ❌ Trino is NOT running"
    exit 1
fi
echo ""

# Test adapter health
echo "4. Testing Cerbos Adapter health endpoint..."
ADAPTER_HEALTH=$(curl -s http://localhost:3594/health 2>&1)
if echo "$ADAPTER_HEALTH" | grep -q "healthy"; then
    echo "   ✅ Adapter health check passed"
    echo "   Response: $ADAPTER_HEALTH"
else
    echo "   ⚠️  Adapter health check failed or unexpected response"
    echo "   Response: $ADAPTER_HEALTH"
fi
echo ""

# Test direct Trino access (bypasses auth)
echo "5. Testing direct Trino access (no auth)..."
TRINO_INFO=$(curl -s http://localhost:8080/v1/info 2>&1 | head -5)
if echo "$TRINO_INFO" | grep -q "nodeVersion\|coordinator"; then
    echo "   ✅ Trino is accessible directly"
    echo "   Response preview: $(echo "$TRINO_INFO" | head -2)"
else
    echo "   ⚠️  Trino direct access issue"
    echo "   Response: $TRINO_INFO"
fi
echo ""

# Test Envoy endpoint
echo "6. Testing Envoy endpoint (with auth headers)..."
ENVOY_RESPONSE=$(curl -s -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@pg-cerbos.com' \
  -H 'x-user-roles: full_access_user' \
  -H 'Content-Type: text/plain' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 1' \
  http://localhost:8081/v1/statement 2>&1)

if echo "$ENVOY_RESPONSE" | grep -q "detail.*Not Found"; then
    echo "   ❌ Got 'Not Found' error"
    echo "   Full response: $ENVOY_RESPONSE"
elif echo "$ENVOY_RESPONSE" | grep -q "columns\|data\|id"; then
    echo "   ✅ Request succeeded!"
    echo "   Response preview: $(echo "$ENVOY_RESPONSE" | head -5)"
else
    echo "   ⚠️  Unexpected response"
    echo "   Full response: $ENVOY_RESPONSE"
fi
echo ""

# Check Envoy logs for errors
echo "7. Checking recent Envoy logs for errors..."
ENVOY_ERRORS=$(docker compose logs envoy --tail=20 2>&1 | grep -iE "(error|ERROR|critical|denied|failed)" || echo "No errors found")
if [ "$ENVOY_ERRORS" != "No errors found" ]; then
    echo "   ⚠️  Found errors in Envoy logs:"
    echo "$ENVOY_ERRORS"
else
    echo "   ✅ No errors in recent Envoy logs"
fi
echo ""

# Check adapter logs
echo "8. Checking recent Cerbos Adapter logs..."
ADAPTER_LOGS=$(docker compose logs cerbos-adapter --tail=10 2>&1 | tail -5)
echo "   Recent adapter logs:"
echo "$ADAPTER_LOGS"
echo ""

echo "===================================="
echo "Diagnosis complete!"
echo ""
echo "If you're still getting 'Not Found', check:"
echo "1. Are you using POST method (not GET)?"
echo "2. Is the URL exactly: http://localhost:8081/v1/statement ?"
echo "3. Are all three headers present: x-user-id, x-user-email, x-user-roles?"
echo "4. Is the body set to 'raw' with your SQL query?"
