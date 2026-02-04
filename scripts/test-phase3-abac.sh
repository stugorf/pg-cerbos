#!/bin/bash

# Phase 3 ABAC Verification Script
# Tests the Enhanced ABAC implementation for Cypher queries
# Verifies team-based, clearance-based, and region-based access control

set -e

echo "🧪 Phase 3: Enhanced ABAC Verification"
echo "======================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check if services are running
print_status "Checking service health..."

if ! curl -s http://localhost:8082/health > /dev/null 2>&1; then
    print_error "Backend service not responding. Please start services with 'just up'"
    exit 1
fi

if ! curl -s http://localhost:3593/_cerbos/health > /dev/null 2>&1; then
    print_error "Cerbos service not responding. Please start services with 'just up'"
    exit 1
fi

print_success "Services are running"

# Test 1: Verify user attributes API endpoints
print_status "Test 1: Verifying user attributes API endpoints..."

# Get auth token for admin
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@pg-cerbos.com", "password": "admin123"}' \
    | jq -r '.access_token')

if [ "$ADMIN_TOKEN" == "null" ] || [ -z "$ADMIN_TOKEN" ]; then
    print_error "Failed to get admin token"
    exit 1
fi

# Get user ID for junior analyst
JUNIOR_USER_ID=$(curl -s -X GET http://localhost:8082/users \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    | jq -r '.[] | select(.email == "analyst.junior@pg-cerbos.com") | .id')

if [ -z "$JUNIOR_USER_ID" ]; then
    print_error "Failed to find junior analyst user"
    exit 1
fi

# Get user attributes
ATTRIBUTES=$(curl -s -X GET "http://localhost:8082/users/$JUNIOR_USER_ID/attributes" \
    -H "Authorization: Bearer $ADMIN_TOKEN")

if echo "$ATTRIBUTES" | jq -e '.team' > /dev/null 2>&1; then
    TEAM=$(echo "$ATTRIBUTES" | jq -r '.team')
    CLEARANCE=$(echo "$ATTRIBUTES" | jq -r '.clearance_level')
    print_success "User attributes API working - Team: $TEAM, Clearance: $CLEARANCE"
else
    print_error "User attributes API not working correctly"
    echo "$ATTRIBUTES" | jq
    exit 1
fi

# Test 2: Verify Cypher parser extracts customer_team and customer_region
print_status "Test 2: Verifying Cypher parser extracts customer_team and customer_region..."

# This would require running the parser directly or via API
# For now, we'll verify the parser module exists
if [ -f "policy-registry/backend/cypher_parser.py" ]; then
    if grep -q "customer_team" policy-registry/backend/cypher_parser.py && \
       grep -q "customer_region" policy-registry/backend/cypher_parser.py; then
        print_success "Cypher parser includes customer_team and customer_region extraction"
    else
        print_error "Cypher parser missing customer_team or customer_region extraction"
        exit 1
    fi
else
    print_error "Cypher parser file not found"
    exit 1
fi

# Test 3: Verify Cerbos policies compile
print_status "Test 3: Verifying Cerbos policies compile..."

if command -v cerbos >/dev/null 2>&1; then
    if cerbos compile cerbos/policies > /dev/null 2>&1; then
        print_success "Cerbos policies compile successfully"
    else
        print_error "Cerbos policies failed to compile"
        cerbos compile cerbos/policies
        exit 1
    fi
else
    print_warning "Cerbos CLI not installed, skipping compile check"
    print_warning "Install with: brew install cerbos"
    print_warning "Or run: docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest compile /policies"
fi

# Test 4: Run ABAC test suite
print_status "Test 4: Running ABAC test suite..."

if command -v cerbos >/dev/null 2>&1; then
    if cerbos test cerbos/policies/tests/cypher_query_abac_test_suite.yaml > /dev/null 2>&1; then
        print_success "ABAC test suite passed"
    else
        print_error "ABAC test suite failed"
        cerbos test cerbos/policies/tests/cypher_query_abac_test_suite.yaml
        exit 1
    fi
else
    print_warning "Cerbos CLI not installed, skipping test suite"
    print_warning "Install with: brew install cerbos"
    print_warning "Or run: docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest test /policies/tests/cypher_query_abac_test_suite.yaml"
fi

# Test 5: Verify database schema
print_status "Test 5: Verifying database schema..."

# Check if user_attributes table exists
TABLE_EXISTS=$(docker compose exec -T postgres psql -U postgres -d postgres -tAc \
    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'user_attributes');" 2>/dev/null || echo "false")

if [ "$TABLE_EXISTS" == "t" ]; then
    print_success "user_attributes table exists"
    
    # Check if data exists
    ROW_COUNT=$(docker compose exec -T postgres psql -U postgres -d postgres -tAc \
        "SELECT COUNT(*) FROM user_attributes;" 2>/dev/null || echo "0")
    
    if [ "$ROW_COUNT" -gt "0" ]; then
        print_success "user_attributes table has $ROW_COUNT rows"
    else
        print_warning "user_attributes table is empty (may need to run migrations)"
    fi
else
    print_error "user_attributes table does not exist"
    print_warning "You may need to restart the postgres container to run migrations"
    exit 1
fi

echo ""
print_success "✅ Phase 3 ABAC verification complete!"
echo ""
echo "Next steps:"
echo "  1. Run 'just test-cypher-abac' to run the full ABAC test suite"
echo "  2. Test graph queries with different user attributes"
echo "  3. Verify team-based, clearance-based, and region-based restrictions"
