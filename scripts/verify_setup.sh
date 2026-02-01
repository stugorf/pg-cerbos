#!/bin/bash

# Test script for UES MVP Authentication System
# This script demonstrates the different user roles and their access levels

set -e

echo "🚀 Testing UES MVP Authentication System"
echo "========================================"

# Configuration
API_BASE="http://localhost:8082"
ENVOY_URL="http://localhost:8081"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if service is running
check_service() {
    local service_name=$1
    local url=$2
    
    if curl -s "$url" > /dev/null 2>&1; then
        print_success "$service_name is running"
        return 0
    else
        print_error "$service_name is not running at $url"
        return 1
    fi
}

# Check if required services are running
echo "🔍 Checking service status..."
check_service "Policy Registry API" "$API_BASE/health" || exit 1
check_service "Envoy Proxy" "$ENVOY_URL" || exit 1

echo ""
echo "🔐 Testing Authentication System"
echo "================================"

# Test 1: Admin User Login
echo ""
print_status "Testing Admin User Login..."
ADMIN_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@pg-cerbos.com", "password": "admin123"}')

if echo "$ADMIN_RESPONSE" | grep -q "access_token"; then
    ADMIN_TOKEN=$(echo "$ADMIN_RESPONSE" | jq -r '.access_token')
    print_success "Admin login successful"
    echo "   Token: ${ADMIN_TOKEN:0:20}..."
else
    print_error "Admin login failed"
    echo "   Response: $ADMIN_RESPONSE"
    exit 1
fi

# Test 2: Full Access User Login
echo ""
print_status "Testing Full Access User Login..."
FULL_ACCESS_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "fullaccess@pg-cerbos.com", "password": "user123"}')

if echo "$FULL_ACCESS_RESPONSE" | grep -q "access_token"; then
    FULL_ACCESS_TOKEN=$(echo "$FULL_ACCESS_RESPONSE" | jq -r '.access_token')
    print_success "Full access user login successful"
    echo "   Token: ${FULL_ACCESS_TOKEN:0:20}..."
else
    print_error "Full access user login failed"
    echo "   Response: $FULL_ACCESS_RESPONSE"
    exit 1
fi

# Test 3: Postgres Only User Login
echo ""
print_status "Testing Postgres Only User Login..."
POSTGRES_ONLY_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "postgresonly@pg-cerbos.com", "password": "user123"}')

if echo "$POSTGRES_ONLY_RESPONSE" | grep -q "access_token"; then
    POSTGRES_ONLY_TOKEN=$(echo "$POSTGRES_ONLY_RESPONSE" | jq -r '.access_token')
    print_success "Postgres only user login successful"
    echo "   Token: ${POSTGRES_ONLY_TOKEN:0:20}..."
else
    print_error "Postgres only user login failed"
    echo "   Response: $POSTGRES_ONLY_RESPONSE"
    exit 1
fi

# Test 4: Restricted User Login
echo ""
print_status "Testing Restricted User Login..."
RESTRICTED_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "restricted@pg-cerbos.com", "password": "user123"}')

if echo "$RESTRICTED_RESPONSE" | grep -q "access_token"; then
    RESTRICTED_TOKEN=$(echo "$RESTRICTED_RESPONSE" | jq -r '.access_token')
    print_success "Restricted user login successful"
    echo "   Token: ${RESTRICTED_TOKEN:0:20}..."
else
    print_error "Restricted user login failed"
    echo "   Response: $RESTRICTED_RESPONSE"
    exit 1
fi

echo ""
echo "🔍 Testing Authorization Policies"
echo "================================="

# Test 5: Admin can access all endpoints
echo ""
print_status "Testing Admin access to user management..."
ADMIN_USERS_RESPONSE=$(curl -s -X GET "$API_BASE/users" \
    -H "Authorization: Bearer $ADMIN_TOKEN")

if echo "$ADMIN_USERS_RESPONSE" | grep -q "email"; then
    print_success "Admin can access user management"
else
    print_error "Admin cannot access user management"
    echo "   Response: $ADMIN_USERS_RESPONSE"
fi

# Test 6: Non-admin cannot access user management
echo ""
print_status "Testing non-admin access to user management..."
FULL_ACCESS_USERS_RESPONSE=$(curl -s -X GET "$API_BASE/users" \
    -H "Authorization: Bearer $FULL_ACCESS_TOKEN")

if echo "$FULL_ACCESS_USERS_RESPONSE" | grep -q "Admin access required"; then
    print_success "Non-admin correctly denied access to user management"
else
    print_warning "Non-admin unexpectedly got access to user management"
    echo "   Response: $FULL_ACCESS_USERS_RESPONSE"
fi

echo ""
echo "📊 Testing SQL Query Interface Through JSON API"
echo "==============================================="

# Test 7: Full access user can query postgres
echo ""
print_status "Testing full access user querying postgres..."
FULL_ACCESS_POSTGRES_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $FULL_ACCESS_TOKEN" \
    -d '{"query": "SELECT * FROM postgres.public.demo_data LIMIT 1", "catalog": "postgres", "schema": "public"}')

if echo "$FULL_ACCESS_POSTGRES_RESPONSE" | grep -q "success.*true"; then
    print_success "Full access user can query postgres"
else
    print_error "Full access user cannot query postgres"
    echo "   Response: $FULL_ACCESS_POSTGRES_RESPONSE"
fi

# Test 8: Full access user can query iceberg
echo ""
print_status "Testing full access user querying iceberg..."
FULL_ACCESS_ICEBERG_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $FULL_ACCESS_TOKEN" \
    -d '{"query": "SELECT * FROM iceberg.sales.orders LIMIT 1", "catalog": "iceberg", "schema": "sales"}')

if echo "$FULL_ACCESS_ICEBERG_RESPONSE" | grep -q "success.*true"; then
    print_success "Full access user can query iceberg"
else
    print_error "Full access user cannot query iceberg"
    echo "   Response: $FULL_ACCESS_ICEBERG_RESPONSE"
fi

# Test 9: Postgres only user cannot query iceberg
echo ""
print_status "Testing postgres only user querying iceberg..."
POSTGRES_ONLY_ICEBERG_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $POSTGRES_ONLY_TOKEN" \
    -d '{"query": "SELECT * FROM iceberg.sales.orders LIMIT 1", "catalog": "iceberg", "schema": "sales"}')

if echo "$POSTGRES_ONLY_ICEBERG_RESPONSE" | grep -q "Access denied"; then
    print_success "Postgres only user correctly denied access to iceberg"
else
    print_warning "Postgres only user unexpectedly got access to iceberg"
    echo "   Response: $POSTGRES_ONLY_ICEBERG_RESPONSE"
fi

# Test 10: Restricted user cannot query SSN fields
echo ""
print_status "Testing restricted user querying SSN fields..."
RESTRICTED_SSN_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $RESTRICTED_TOKEN" \
    -d '{"query": "SELECT ssn FROM postgres.public.demo_data LIMIT 1", "catalog": "postgres", "schema": "public"}')

if echo "$RESTRICTED_SSN_RESPONSE" | grep -q "Access denied.*SSN"; then
    print_success "Restricted user correctly denied access to SSN fields"
else
    print_warning "Restricted user unexpectedly got access to SSN fields"
    echo "   Response: $RESTRICTED_SSN_RESPONSE"
fi

# Test 11: Restricted user can query non-SSN fields
echo ""
print_status "Testing restricted user querying non-SSN fields..."
RESTRICTED_NON_SSN_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $RESTRICTED_TOKEN" \
    -d '{"query": "SELECT name, email FROM postgres.public.demo_data LIMIT 1", "catalog": "postgres", "schema": "public"}')

if echo "$RESTRICTED_NON_SSN_RESPONSE" | grep -q "success.*true"; then
    print_success "Restricted user can query non-SSN fields"
else
    print_error "Restricted user cannot query non-SSN fields"
    echo "   Response: $RESTRICTED_NON_SSN_RESPONSE"
fi

# Test 12: Test specific table queries
echo ""
print_status "Testing specific table queries..."
print_status "  Testing postgres demo_data table access..."

POSTGRES_DEMO_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $FULL_ACCESS_TOKEN" \
    -d '{"query": "SELECT COUNT(*) as total_records FROM postgres.public.demo_data", "catalog": "postgres", "schema": "public"}')

if echo "$POSTGRES_DEMO_RESPONSE" | grep -q "success.*true"; then
    print_success "  Postgres demo_data table query successful"
else
    print_error "  Postgres demo_data table query failed"
    echo "     Response: $POSTGRES_DEMO_RESPONSE"
fi

# Test 13: Test field-level access control
echo ""
print_status "Testing field-level access control..."
print_status "  Testing SSN field access for different roles..."

# Admin should be able to access SSN
ADMIN_SSN_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d '{"query": "SELECT ssn FROM postgres.public.demo_data LIMIT 1", "catalog": "postgres", "schema": "public"}')

if echo "$ADMIN_SSN_RESPONSE" | grep -q "success.*true"; then
    print_success "  Admin can access SSN fields"
else
    print_error "  Admin cannot access SSN fields"
    echo "     Response: $ADMIN_SSN_RESPONSE"
fi

# Full access user should be able to access SSN
FULL_ACCESS_SSN_RESPONSE=$(curl -s -X POST "$API_BASE/query" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $FULL_ACCESS_TOKEN" \
    -d '{"query": "SELECT ssn FROM postgres.public.demo_data LIMIT 1", "catalog": "postgres", "schema": "public"}')

if echo "$FULL_ACCESS_SSN_RESPONSE" | grep -q "success.*true"; then
    print_success "  Full access user can access SSN fields"
else
    print_error "  Full access user cannot access SSN fields"
    echo "     Response: $FULL_ACCESS_SSN_RESPONSE"
fi

echo ""
echo "✅ Authentication System Test Complete!"
echo "======================================"
echo ""
echo "📋 Test Summary:"
echo "   - Admin user: Full access to all features and data"
echo "   - Full access user: Can query postgres and iceberg, all fields including SSN"
echo "   - Postgres only user: Can only query postgres, all fields"
echo "   - Restricted user: Can query both sources but SSN fields are blocked"
echo ""
echo "🔗 Access URLs:"
echo "   - Authentication UI: http://localhost:8083/auth.html"
echo "   - SQL Query Interface: http://localhost:8083/auth.html (after login)"
echo "   - Policy Registry API: http://localhost:8082"
echo "   - Envoy Proxy (Trino): http://localhost:8081"
echo "   - Trino UI: http://localhost:8080"
echo ""
echo "👤 Demo Users:"
echo "   - admin@pg-cerbos.com / admin123 (Admin)"
echo "   - fullaccess@pg-cerbos.com / user123 (Full Access)"
echo "   - postgresonly@pg-cerbos.com / user123 (Postgres Only)"
echo "   - restricted@pg-cerbos.com / user123 (Restricted)"
echo ""
echo "💡 SQL Query Interface Features:"
echo "   - Execute SQL queries directly in the browser"
echo "   - Real-time results display with formatted tables"
echo "   - Query history and saved queries"
echo "   - Role-based access control enforcement"
echo "   - Field-level security (SSN blocking for restricted users)"
echo "   - Support for both PostgreSQL and Iceberg data sources" 