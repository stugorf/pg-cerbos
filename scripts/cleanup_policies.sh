#!/bin/bash

# Cleanup Policies for UES MVP
# This script removes any existing policies to prevent conflicts

set -e

echo "🧹 Cleaning up existing policies..."
echo "=================================="

# Configuration
API_BASE="http://localhost:8082"

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

# Check if service is running
echo "🔍 Checking service status..."
if ! curl -s "$API_BASE/health" > /dev/null; then
    print_error "Policy Registry API is not running at $API_BASE"
    exit 1
fi

print_success "Policy Registry API is running"

# Login as admin to get token
echo ""
print_status "Logging in as admin user..."
ADMIN_RESPONSE=$(curl -s -X POST "$API_BASE/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@ues-mvp.com", "password": "admin123"}')

if echo "$ADMIN_RESPONSE" | grep -q "access_token"; then
    ADMIN_TOKEN=$(echo "$ADMIN_RESPONSE" | jq -r '.access_token')
    print_success "Admin login successful"
else
    print_error "Admin login failed"
    echo "Response: $ADMIN_RESPONSE"
    exit 1
fi

# Get list of existing policies
echo ""
print_status "Checking existing policies..."
POLICIES_RESPONSE=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_BASE/policies")

if echo "$POLICIES_RESPONSE" | grep -q "id"; then
    # Extract policy IDs
    POLICY_IDS=$(echo "$POLICIES_RESPONSE" | jq -r '.[].id')
    POLICY_COUNT=$(echo "$POLICY_IDS" | wc -l)
    
    if [ "$POLICY_COUNT" -gt 0 ]; then
        print_warning "Found $POLICY_COUNT existing policies. Cleaning them up..."
        
        # Delete each policy
        for POLICY_ID in $POLICY_IDS; do
            print_status "Deleting policy ID: $POLICY_ID"
            DELETE_RESPONSE=$(curl -s -X DELETE \
                -H "Authorization: Bearer $ADMIN_TOKEN" \
                "$API_BASE/policies/$POLICY_ID")
            
            if echo "$DELETE_RESPONSE" | grep -q "successfully"; then
                print_success "Policy $POLICY_ID deleted successfully"
            else
                print_warning "Failed to delete policy $POLICY_ID: $DELETE_RESPONSE"
            fi
        done
        
        print_success "Policy cleanup complete"
    else
        print_success "No existing policies found"
    fi
else
    print_success "No existing policies found"
fi

echo ""
echo "✅ Policy cleanup complete!"
echo "=========================="
echo ""
echo "💡 Next step: Create new working policies" 