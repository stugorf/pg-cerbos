#!/bin/bash

# UES MVP Web Interface Test Script
# This script tests the web interface functionality and user authentication

echo "🌐 UES MVP Web Interface Testing"
echo "================================="

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
echo "📊 Checking service status..."
if ! curl -s http://localhost:8082/health > /dev/null; then
    print_status "ERROR" "Policy Registry Backend is not running"
    echo "Please start services with: docker-compose up -d"
    exit 1
fi

print_status "OK" "Policy Registry Backend is running"

# Test user authentication
echo ""
echo "🔐 Testing User Authentication..."
echo "================================="

# Test admin user login
echo "Testing Admin User login..."
ADMIN_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@pg-cerbos.com", "password": "admin123"}')

if echo "$ADMIN_RESPONSE" | grep -q "access_token"; then
    ADMIN_TOKEN=$(echo "$ADMIN_RESPONSE" | jq -r '.access_token')
    ADMIN_USER=$(echo "$ADMIN_RESPONSE" | jq -r '.user.email')
    ADMIN_ROLES=$(echo "$ADMIN_RESPONSE" | jq -r '.user.roles[]' | tr '\n' ',' | sed 's/,$//')
    print_status "OK" "Admin user login successful"
    print_status "INFO" "User: $ADMIN_USER, Roles: $ADMIN_ROLES"
else
    print_status "ERROR" "Admin user login failed"
    echo "Response: $ADMIN_RESPONSE"
fi

# Test full access user login
echo ""
echo "Testing Full Access User login..."
FULL_ACCESS_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "fullaccess@pg-cerbos.com", "password": "user123"}')

if echo "$FULL_ACCESS_RESPONSE" | grep -q "access_token"; then
    FULL_ACCESS_TOKEN=$(echo "$FULL_ACCESS_RESPONSE" | jq -r '.access_token')
    FULL_ACCESS_USER=$(echo "$FULL_ACCESS_RESPONSE" | jq -r '.user.email')
    FULL_ACCESS_ROLES=$(echo "$FULL_ACCESS_RESPONSE" | jq -r '.user.roles[]' | tr '\n' ',' | sed 's/,$//')
    print_status "OK" "Full Access user login successful"
    print_status "INFO" "User: $FULL_ACCESS_USER, Roles: $FULL_ACCESS_ROLES"
else
    print_status "ERROR" "Full Access user login failed"
    echo "Response: $FULL_ACCESS_RESPONSE"
fi

# Test postgres-only user login
echo ""
echo "Testing Postgres-Only User login..."
POSTGRES_ONLY_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "postgresonly@pg-cerbos.com", "password": "user123"}')

if echo "$POSTGRES_ONLY_RESPONSE" | grep -q "access_token"; then
    POSTGRES_ONLY_TOKEN=$(echo "$POSTGRES_ONLY_RESPONSE" | jq -r '.access_token')
    POSTGRES_ONLY_USER=$(echo "$POSTGRES_ONLY_RESPONSE" | jq -r '.user.email')
    POSTGRES_ONLY_ROLES=$(echo "$POSTGRES_ONLY_RESPONSE" | jq -r '.user.roles[]' | tr '\n' ',' | sed 's/,$//')
    print_status "OK" "Postgres-Only user login successful"
    print_status "INFO" "User: $POSTGRES_ONLY_USER, Roles: $POSTGRES_ONLY_ROLES"
else
    print_status "ERROR" "Postgres-Only user login failed"
    echo "Response: $POSTGRES_ONLY_RESPONSE"
fi

# Test restricted user login
echo ""
echo "Testing Restricted User login..."
RESTRICTED_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "restricted@pg-cerbos.com", "password": "user123"}')

if echo "$RESTRICTED_RESPONSE" | grep -q "access_token"; then
    RESTRICTED_TOKEN=$(echo "$RESTRICTED_RESPONSE" | jq -r '.access_token')
    RESTRICTED_USER=$(echo "$RESTRICTED_RESPONSE" | jq -r '.user.email')
    RESTRICTED_ROLES=$(echo "$RESTRICTED_RESPONSE" | jq -r '.user.roles[]' | tr '\n' ',' | sed 's/,$//')
    print_status "OK" "Restricted user login successful"
    print_status "INFO" "User: $RESTRICTED_USER, Roles: $RESTRICTED_ROLES"
else
    print_status "ERROR" "Restricted user login failed"
    echo "Response: $RESTRICTED_RESPONSE"
fi

# Test API endpoints
echo ""
echo "🔌 Testing API Endpoints..."
echo "============================"

# Test permissions endpoint (admin only)
if [ ! -z "$ADMIN_TOKEN" ]; then
    echo "Testing permissions endpoint (admin only)..."
    PERMISSIONS_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8082/permissions)
    if echo "$PERMISSIONS_RESPONSE" | grep -q "postgres_full_access"; then
        print_status "OK" "Permissions endpoint accessible to admin"
        PERMISSION_COUNT=$(echo "$PERMISSIONS_RESPONSE" | jq '. | length')
        print_status "INFO" "Found $PERMISSION_COUNT permissions"
    else
        print_status "ERROR" "Permissions endpoint not working for admin"
    fi
fi

# Test users endpoint (admin only)
if [ ! -z "$ADMIN_TOKEN" ]; then
    echo "Testing users endpoint (admin only)..."
    USERS_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8082/users)
    if echo "$USERS_RESPONSE" | grep -q "admin@pg-cerbos.com"; then
        print_status "OK" "Users endpoint accessible to admin"
        USER_COUNT=$(echo "$USERS_RESPONSE" | jq '. | length')
        print_status "INFO" "Found $USER_COUNT users"
    else
        print_status "ERROR" "Users endpoint not working for admin"
    fi
fi

# Test non-admin access to admin endpoints
if [ ! -z "$RESTRICTED_TOKEN" ]; then
    echo "Testing non-admin access to admin endpoints..."
    PERMISSIONS_RESPONSE=$(curl -s -H "Authorization: Bearer $RESTRICTED_TOKEN" http://localhost:8082/permissions)
    if echo "$PERMISSIONS_RESPONSE" | grep -q "Admin access required"; then
        print_status "OK" "Non-admin users correctly blocked from permissions endpoint"
    else
        print_status "WARN" "Non-admin users may have access to admin endpoints"
    fi
fi

# Test user info endpoint
echo ""
echo "Testing user info endpoint..."
if [ ! -z "$ADMIN_TOKEN" ]; then
    USER_INFO_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:8082/auth/me)
    if echo "$USER_INFO_RESPONSE" | grep -q "admin@pg-cerbos.com"; then
        print_status "OK" "User info endpoint working for admin"
    else
        print_status "ERROR" "User info endpoint not working for admin"
    fi
fi

# Summary
echo ""
echo "📊 Test Summary"
echo "==============="
echo "✅ Web interface authentication tests completed"
echo ""
echo "🎯 Next Steps:"
echo "1. Access the web interface at http://localhost:8082"
echo "2. Login with different user accounts to test the UI"
echo "3. Use the SQL query interface to test data access"
echo "4. Verify that access restrictions work in the web interface"
echo ""
echo "🔐 Test User Accounts:"
echo "- Admin: admin@pg-cerbos.com (admin123)"
echo "- Full Access: fullaccess@pg-cerbos.com (user123)"
echo "- Postgres Only: postgresonly@pg-cerbos.com (user123)"
echo "- Restricted: restricted@pg-cerbos.com (user123)"
echo ""
echo "📚 Demo Queries:"
echo "Use the queries from scripts/demo_queries_by_user.sql in the web interface"
echo ""
echo "⚠️  Note: Direct Trino access requires proper authentication headers."
echo "   The web interface handles this automatically." 