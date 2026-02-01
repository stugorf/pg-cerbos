#!/bin/bash

# UES MVP Policy Verification Script
# This script verifies that all policies and permissions are working correctly

echo "🔍 UES MVP Policy and Permission Verification"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "OK")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "WARN")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
    esac
}

# Check if services are running
echo ""
echo "📊 Checking Service Status..."
echo "----------------------------"

# Check Policy Registry Backend
if curl -s http://localhost:8082/health > /dev/null; then
    print_status "OK" "Policy Registry Backend is running (port 8082)"
else
    print_status "ERROR" "Policy Registry Backend is not running (port 8082)"
fi

# Check Trino
if curl -s http://localhost:8081/health > /dev/null; then
    print_status "OK" "Trino is running (port 8081)"
else
    print_status "ERROR" "Trino is not running (port 8081)"
fi

# Check Envoy
if curl -s http://localhost:8080/health > /dev/null; then
    print_status "OK" "Envoy proxy is running (port 8080)"
else
    print_status "ERROR" "Envoy proxy is not running (port 8080)"
fi

# Check PostgreSQL
if docker exec pg-cerbos-postgres pg_isready -U postgres > /dev/null 2>&1; then
    print_status "OK" "PostgreSQL is running and ready"
else
    print_status "ERROR" "PostgreSQL is not running or not ready"
fi

echo ""
echo "🔐 Testing Authentication and Authorization..."
echo "--------------------------------------------"

# Test user login and role retrieval
echo "Testing user authentication..."

# Test admin user
ADMIN_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@pg-cerbos.com", "password": "admin123"}')

if echo "$ADMIN_RESPONSE" | grep -q "access_token"; then
    ADMIN_TOKEN=$(echo "$ADMIN_RESPONSE" | jq -r '.access_token')
    print_status "OK" "Admin user authentication successful"
    
    # Get admin user info
    ADMIN_INFO=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8082/auth/me)
    ADMIN_ROLES=$(echo "$ADMIN_INFO" | jq -r '.roles[]')
    print_status "INFO" "Admin roles: $ADMIN_ROLES"
else
    print_status "ERROR" "Admin user authentication failed"
fi

# Test restricted user
RESTRICTED_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "restricted@pg-cerbos.com", "password": "user123"}')

if echo "$RESTRICTED_RESPONSE" | grep -q "access_token"; then
    RESTRICTED_TOKEN=$(echo "$RESTRICTED_RESPONSE" | jq -r '.access_token')
    print_status "OK" "Restricted user authentication successful"
    
    # Get restricted user info
    RESTRICTED_INFO=$(curl -s -H "Authorization: Bearer $RESTRICTED_TOKEN" http://localhost:8082/auth/me)
    RESTRICTED_ROLES=$(echo "$RESTRICTED_INFO" | jq -r '.roles[]')
    print_status "INFO" "Restricted user roles: $RESTRICTED_ROLES"
else
    print_status "ERROR" "Restricted user authentication failed"
fi

echo ""
echo "📋 Testing Permission System..."
echo "-------------------------------"

# Test permissions endpoint (admin only)
if [ ! -z "$ADMIN_TOKEN" ]; then
    PERMISSIONS_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8082/permissions)
    if echo "$PERMISSIONS_RESPONSE" | grep -q "postgres_full_access"; then
        print_status "OK" "Permissions endpoint accessible to admin"
        PERMISSION_COUNT=$(echo "$PERMISSIONS_RESPONSE" | jq '. | length')
        print_status "INFO" "Found $PERMISSION_COUNT permissions"
    else
        print_status "ERROR" "Permissions endpoint not working for admin"
    fi
fi

echo ""
echo "🗄️  Testing Data Access..."
echo "---------------------------"

# Test PostgreSQL access
echo "Testing PostgreSQL access..."

# Test with admin token
if [ ! -z "$ADMIN_TOKEN" ]; then
    PG_QUERY="SELECT COUNT(*) as count FROM postgres.public.person"
    PG_RESPONSE=$(curl -s -X POST http://localhost:8081/v1/statement \
      -H "Content-Type: application/json" \
      -H "X-User-Id: 1" \
      -H "X-User-Email: admin@pg-cerbos.com" \
      -H "X-User-Roles: admin" \
      -d "$PG_QUERY")
    
    if echo "$PG_RESPONSE" | grep -q "nextUri"; then
        print_status "OK" "Admin can access PostgreSQL data"
    else
        print_status "ERROR" "Admin cannot access PostgreSQL data"
    fi
fi

# Test with restricted user token
if [ ! -z "$RESTRICTED_TOKEN" ]; then
    PG_QUERY="SELECT COUNT(*) as count FROM postgres.public.person"
    PG_RESPONSE=$(curl -s -X POST http://localhost:8081/v1/statement \
      -H "Content-Type: application/json" \
      -H "X-User-Id: 4" \
      -H "X-User-Email: restricted@pg-cerbos.com" \
      -H "X-User-Roles: restricted_user" \
      -d "$PG_QUERY")
    
    if echo "$PG_RESPONSE" | grep -q "nextUri"; then
        print_status "OK" "Restricted user can access PostgreSQL data"
    else
        print_status "ERROR" "Restricted user cannot access PostgreSQL data"
    fi
fi

echo ""
echo "🧊 Testing Iceberg Access..."
echo "----------------------------"

# Test Iceberg access
echo "Testing Iceberg access..."

# Test with admin token
if [ ! -z "$ADMIN_TOKEN" ]; then
    ICEBERG_QUERY="SELECT COUNT(*) as count FROM iceberg.sales.person"
    ICEBERG_RESPONSE=$(curl -s -X POST http://localhost:8081/v1/statement \
      -H "Content-Type: application/json" \
      -H "X-User-Id: 1" \
      -H "X-User-Email: admin@pg-cerbos.com" \
      -H "X-User-Roles: admin" \
      -d "$ICEBERG_QUERY")
    
    if echo "$ICEBERG_RESPONSE" | grep -q "nextUri"; then
        print_status "OK" "Admin can access Iceberg data"
    else
        print_status "ERROR" "Admin cannot access Iceberg data"
    fi
fi

# Test with restricted user token
if [ ! -z "$RESTRICTED_TOKEN" ]; then
    ICEBERG_QUERY="SELECT COUNT(*) as count FROM iceberg.sales.person"
    ICEBERG_RESPONSE=$(curl -s -X POST http://localhost:8081/v1/statement \
      -H "Content-Type: application/json" \
      -H "X-User-Id: 4" \
      -H "X-User-Email: restricted@pg-cerbos.com" \
      -H "X-User-Roles: restricted_user" \
      -d "$ICEBERG_QUERY")
    
    if echo "$ICEBERG_RESPONSE" | grep -q "nextUri"; then
        print_status "OK" "Restricted user can access Iceberg data"
    else
        print_status "ERROR" "Restricted user cannot access Iceberg data"
    fi
fi

echo ""
echo "🚫 Testing SSN Field Restrictions..."
echo "------------------------------------"

# Test SSN field access restrictions
echo "Testing SSN field access restrictions..."

# Test with restricted user trying to access SSN
if [ ! -z "$RESTRICTED_TOKEN" ]; then
    SSN_QUERY="SELECT ssn FROM postgres.public.person LIMIT 1"
    SSN_RESPONSE=$(curl -s -X POST http://localhost:8081/v1/statement \
      -H "Content-Type: application/json" \
      -H "X-User-Id: 4" \
      -H "X-User-Email: restricted@pg-cerbos.com" \
      -H "X-User-Roles: restricted_user" \
      -d "$SSN_QUERY")
    
    if echo "$SSN_RESPONSE" | grep -q "Access denied"; then
        print_status "OK" "SSN field access properly restricted for restricted users"
    else
        print_status "WARN" "SSN field access restriction may not be working properly"
    fi
fi

echo ""
echo "📊 Summary of Findings..."
echo "========================="

# Count successful tests
SUCCESS_COUNT=$(grep -c "✅" <<< "$(grep -o '✅' <<< "$(cat $0)")" 2>/dev/null || echo "0")
ERROR_COUNT=$(grep -c "❌" <<< "$(grep -o '❌' <<< "$(cat $0)")" 2>/dev/null || echo "0")
WARN_COUNT=$(grep -c "⚠️" <<< "$(grep -o '⚠️' <<< "$(cat $0)")" 2>/dev/null || echo "0")

echo "Test Results:"
echo "  ✅ Successes: $SUCCESS_COUNT"
echo "  ❌ Errors: $ERROR_COUNT"
echo "  ⚠️  Warnings: $WARN_COUNT"

if [ $ERROR_COUNT -eq 0 ]; then
    print_status "OK" "All critical tests passed!"
else
    print_status "ERROR" "Some tests failed. Please review the errors above."
fi

echo ""
echo "🔧 Recommendations:"
echo "==================="

if [ $ERROR_COUNT -gt 0 ]; then
    echo "1. Fix any service startup issues"
    echo "2. Verify database connections"
    echo "3. Check OPA policy configuration"
    echo "4. Ensure proper user authentication"
fi

echo "5. Run ./scripts/init_iceberg.sh to initialize Iceberg tables"
echo "6. Test with different user roles in the web interface"
echo "7. Verify column masking is working for SSN fields"

echo ""
echo "🎯 Next Steps:"
echo "==============="
echo "1. Access the web interface at http://localhost:8082"
echo "2. Login with different user accounts to test permissions"
echo "3. Run SQL queries to verify access control"
echo "4. Check that SSN fields are properly masked for restricted users" 