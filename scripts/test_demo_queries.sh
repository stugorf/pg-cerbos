#!/bin/bash

# UES MVP Demo Query Test Script
# This script tests different user access levels by running queries

echo "🧪 UES MVP Demo Query Testing"
echo "=============================="

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

if ! curl -s http://localhost:8080/v1/statement > /dev/null 2>&1; then
    print_status "ERROR" "Trino is not running"
    echo "Please start services with: docker-compose up -d"
    exit 1
fi

print_status "OK" "All services are running"

# Function to test user access
test_user_access() {
    local user_email=$1
    local password=$2
    local user_name=$3
    local test_queries=("$@")
    
    echo ""
    echo "🔐 Testing $user_name access..."
    echo "--------------------------------"
    
    # Login and get token
    local login_response=$(curl -s -X POST http://localhost:8082/auth/login \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"$user_email\", \"password\": \"$password\"}")
    
    if echo "$login_response" | grep -q "access_token"; then
        local token=$(echo "$login_response" | jq -r '.access_token')
        local user_id=$(echo "$login_response" | jq -r '.user.id')
        local user_roles=$(echo "$login_response" | jq -r '.user.roles[]' | tr '\n' ',' | sed 's/,$//')
        
        print_status "OK" "Login successful for $user_name"
        print_status "INFO" "User ID: $user_id, Roles: $user_roles"
        
        # Test basic PostgreSQL access
        test_postgres_access "$user_id" "$user_email" "$user_roles" "$user_name"
        
        # Test Iceberg access
        test_iceberg_access "$user_id" "$user_email" "$user_roles" "$user_name"
        
        # Test SSN field access
        test_ssn_access "$user_id" "$user_email" "$user_roles" "$user_name"
        
    else
        print_status "ERROR" "Login failed for $user_name"
    fi
}

# Test PostgreSQL access
test_postgres_access() {
    local user_id=$1
    local user_email=$2
    local user_roles=$3
    local user_name=$4
    
    echo "  📊 Testing PostgreSQL access..."
    
    local query="SELECT COUNT(*) as count FROM postgres.public.person"
    local response=$(curl -s -X POST http://localhost:8080/v1/statement \
        -H "Content-Type: application/json" \
        -H "X-User-Id: $user_id" \
        -H "X-User-Email: $user_email" \
        -H "X-User-Roles: $user_roles" \
        -d "$query")
    
    if echo "$response" | grep -q "nextUri"; then
        print_status "OK" "$user_name can access PostgreSQL data"
    else
        print_status "ERROR" "$user_name cannot access PostgreSQL data"
    fi
}

# Test Iceberg access
test_iceberg_access() {
    local user_id=$1
    local user_email=$2
    local user_roles=$3
    local user_name=$4
    
    echo "  🧊 Testing Iceberg access..."
    
    local query="SELECT COUNT(*) as count FROM iceberg.sales.person"
    local response=$(curl -s -X POST http://localhost:8080/v1/statement \
        -H "Content-Type: application/json" \
        -H "X-User-Id: $user_id" \
        -H "X-User-Email: $user_email" \
        -H "X-User-Roles: $user_roles" \
        -d "$query")
    
    if echo "$response" | grep -q "nextUri"; then
        print_status "OK" "$user_name can access Iceberg data"
    elif echo "$user_roles" | grep -q "postgres_only_user"; then
        print_status "OK" "$user_name correctly blocked from Iceberg (expected)"
    else
        print_status "ERROR" "$user_name cannot access Iceberg data"
    fi
}

# Test SSN field access
test_ssn_access() {
    local user_id=$1
    local user_email=$2
    local user_roles=$3
    local user_name=$4
    
    echo "  🚫 Testing SSN field access..."
    
    local query="SELECT ssn FROM postgres.public.person LIMIT 1"
    local response=$(curl -s -X POST http://localhost:8080/v1/statement \
        -H "Content-Type: application/json" \
        -H "X-User-Id: $user_id" \
        -H "X-User-Email: $user_email" \
        -H "X-User-Roles: $user_roles" \
        -d "$query")
    
    if echo "$user_roles" | grep -q "restricted_user"; then
        if echo "$response" | grep -q "Access denied"; then
            print_status "OK" "$user_name correctly blocked from SSN fields (expected)"
        else
            print_status "WARN" "$user_name SSN access not properly restricted"
        fi
    else
        if echo "$response" | grep -q "nextUri"; then
            print_status "OK" "$user_name can access SSN fields (expected)"
        else
            print_status "ERROR" "$user_name cannot access SSN fields"
        fi
    fi
}

# Test cross-data source queries
test_cross_source_access() {
    echo ""
    echo "🔄 Testing cross-data source access..."
    echo "-------------------------------------"
    
    # Test with admin user
    local admin_response=$(curl -s -X POST http://localhost:8082/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email": "admin@ues-mvp.com", "password": "admin123"}')
    
    if echo "$admin_response" | grep -q "access_token"; then
        local admin_token=$(echo "$admin_response" | jq -r '.access_token')
        local admin_id=$(echo "$admin_response" | jq -r '.user.id')
        local admin_roles="admin"
        
        local cross_query="SELECT 'PostgreSQL' as source, COUNT(*) as count FROM postgres.public.person UNION ALL SELECT 'Iceberg' as source, COUNT(*) as count FROM iceberg.sales.person"
        local response=$(curl -s -X POST http://localhost:8080/v1/statement \
            -H "Content-Type: application/json" \
            -H "X-User-Id: $admin_id" \
            -H "X-User-Email: admin@ues-mvp.com" \
            -H "X-User-Roles: $admin_roles" \
            -d "$cross_query")
        
        if echo "$response" | grep -q "nextUri"; then
            print_status "OK" "Cross-data source queries working for admin"
        else
            print_status "ERROR" "Cross-data source queries not working"
        fi
    fi
}

# Main test execution
echo ""
echo "🧪 Starting user access tests..."
echo "================================"

# Test each user type
test_user_access "admin@ues-mvp.com" "admin123" "Admin User"
test_user_access "fullaccess@ues-mvp.com" "user123" "Full Access User"
test_user_access "postgresonly@ues-mvp.com" "user123" "Postgres-Only User"
test_user_access "restricted@ues-mvp.com" "user123" "Restricted User"

# Test cross-data source functionality
test_cross_source_access

echo ""
echo "📊 Test Summary"
echo "==============="
echo "✅ All user access tests completed"
echo ""
echo "🎯 Next Steps:"
echo "1. Access the web interface at http://localhost:8082"
echo "2. Login with different user accounts"
echo "3. Run the demo queries from scripts/demo_queries_by_user.sql"
echo "4. Verify that access restrictions work as expected"
echo ""
echo "📚 Reference Materials:"
echo "- Quick Reference: scripts/demo_quick_reference.md"
echo "- Full Demo Scripts: scripts/demo_queries_by_user.sql"
echo "- Policy Summary: docs/policy-and-permissions-summary.md" 