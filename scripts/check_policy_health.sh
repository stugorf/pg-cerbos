#!/bin/bash

# Check Policy Health for UES MVP
# This script verifies that the policy system is working correctly

set -e

echo "🏥 Checking Policy System Health"
echo "================================"

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

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check OPA health
echo "🔍 Checking OPA health..."
if curl -s "http://localhost:8181/health" > /dev/null; then
    print_success "OPA is running"
else
    print_error "OPA is not responding"
    exit 1
fi

# Check if policies are loaded in OPA
echo ""
print_status "Checking if policies are loaded in OPA..."
OPA_POLICIES=$(curl -s "http://localhost:8181/v1/policies")

if echo "$OPA_POLICIES" | grep -q "envoy.authz"; then
    print_success "Policies are loaded in OPA"
    echo "   Found: $(echo "$OPA_POLICIES" | jq '.result | length') policy(ies)"
else
    print_error "No policies loaded in OPA"
    echo "   This will cause 'Access denied by policy' errors"
fi

# Check policy registry health
echo ""
print_status "Checking policy registry health..."
if curl -s "http://localhost:8082/health" > /dev/null; then
    print_success "Policy registry is running"
else
    print_error "Policy registry is not responding"
    exit 1
fi

# Check if we can authenticate and get policies
echo ""
print_status "Checking policy registry authentication..."
LOGIN_RESPONSE=$(curl -s -X POST "http://localhost:8082/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@ues-mvp.com", "password": "admin123"}')

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    print_success "Authentication working"
    ADMIN_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    
    # Get policies from registry
    POLICIES_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "http://localhost:8082/policies")
    
    if echo "$POLICIES_RESPONSE" | grep -q "id"; then
        POLICY_COUNT=$(echo "$POLICIES_RESPONSE" | jq '. | length')
        print_success "Policy registry has $POLICY_COUNT policy(ies)"
        
        # Check for duplicate paths
        PATHS=$(echo "$POLICIES_RESPONSE" | jq -r '.[].path')
        DUPLICATE_PATHS=$(echo "$PATHS" | sort | uniq -d)
        
        if [ -n "$DUPLICATE_PATHS" ]; then
            print_warning "Found duplicate policy paths:"
            echo "$DUPLICATE_PATHS" | while read -r path; do
                echo "   - $path"
            done
            echo "   This can cause conflicts and prevent policies from loading"
        else
            print_success "No duplicate policy paths found"
        fi
    else
        print_warning "No policies found in registry"
    fi
else
    print_error "Authentication failed"
    echo "   Response: $LOGIN_RESPONSE"
fi

# Test basic authorization
echo ""
print_status "Testing basic authorization..."
TEST_RESPONSE=$(curl -s -X POST "http://localhost:8081/v1/statement" \
    -H 'x-user-roles: admin' \
    -d 'SELECT 1')

if echo "$TEST_RESPONSE" | grep -q "invalid_parameter"; then
    print_warning "Authorization is working (policy allowed the request)"
    print_warning "But there's a request format issue (this is expected for now)"
elif echo "$TEST_RESPONSE" | grep -q "Access denied"; then
    print_error "Authorization is NOT working - policies are not functioning"
else
    print_success "Authorization test completed"
fi

echo ""
echo "✅ Policy health check complete!"
echo "==============================="
echo ""
echo "💡 If you see issues:"
echo "   1. Run 'just cleanup-policies' to remove broken policies"
echo "   2. Run 'bash scripts/create_exact_rego_policy.sh' to create working ones"
echo "   3. Check OPA logs: 'docker logs mvp-opa --tail 10'" 