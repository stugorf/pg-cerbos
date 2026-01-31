#!/bin/bash
# Test authorization flow through Envoy

set -e

echo "🧪 Testing Authorization Flow"
echo "=============================="
echo ""

# Check if Envoy is running
if ! lsof -i :8081 >/dev/null 2>&1; then
    echo "❌ Envoy is not running on port 8081"
    echo ""
    echo "Please start Envoy first:"
    echo "  docker compose up -d envoy"
    echo ""
    echo "Or use:"
    echo "  just start-envoy"
    exit 1
fi

echo "✅ Envoy is running"
echo ""

# Test 1: Full Access User (should work)
echo "Test 1: Full Access User"
echo "------------------------"
curl -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@ues-mvp.com' \
  -H 'x-user-roles: full_access_user' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement 2>&1 | head -20

echo ""
echo ""

# Test 2: Restricted User - SSN query (should be denied)
echo "Test 2: Restricted User - SSN Query (should be denied)"
echo "-------------------------------------------------------"
curl -X POST \
  -H 'x-user-id: 4' \
  -H 'x-user-email: restricted@ues-mvp.com' \
  -H 'x-user-roles: restricted_user' \
  --data-binary 'SELECT ssn FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement 2>&1 | head -20

echo ""
echo ""

# Test 3: Postgres-Only User - Iceberg query (should be denied)
echo "Test 3: Postgres-Only User - Iceberg Query (should be denied)"
echo "-------------------------------------------------------------"
curl -X POST \
  -H 'x-user-id: 3' \
  -H 'x-user-email: postgresonly@ues-mvp.com' \
  -H 'x-user-roles: postgres_only_user' \
  --data-binary 'SELECT * FROM iceberg.demo.employee_performance LIMIT 5' \
  http://localhost:8081/v1/statement 2>&1 | head -20

echo ""
echo ""
echo "✅ Tests complete!"
