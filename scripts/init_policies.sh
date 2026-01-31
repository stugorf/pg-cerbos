#!/bin/bash

# Initialize Policy System for UES MVP (JSON Fixed Version)
# This script loads the comprehensive authorization policies into the system

set -e

echo "🚀 Initializing UES MVP Policy System (JSON Fixed Version)"
echo "=========================================================="

# Configuration
API_BASE="http://localhost:8082"
OPA_URL="http://localhost:8181"

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

# Check if services are running
echo "🔍 Checking service status..."
if ! curl -s "$API_BASE/health" > /dev/null; then
    print_error "Policy Registry API is not running at $API_BASE"
    exit 1
fi

if ! curl -s "$OPA_URL/health" > /dev/null; then
    print_error "OPA is not running at $OPA_URL"
    exit 1
fi

print_success "Services are running"

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

# Create the comprehensive authorization policy
echo ""
print_status "Creating comprehensive authorization policy..."

# Read the policy from file and create a temporary JSON file
if [ -f "opa/authz-policy-fixed.rego" ]; then
    AUTHZ_POLICY_TEXT=$(cat "opa/authz-policy-fixed.rego")
    print_success "Using policy from opa/authz-policy-fixed.rego"
    
    # Create JSON payload using jq to properly escape the content
    AUTHZ_POLICY_JSON=$(jq -n \
        --arg name "envoy_authz_comprehensive" \
        --arg path "envoy/authz.rego" \
        --arg rego_text "$AUTHZ_POLICY_TEXT" \
        --arg bundle_name "main" \
        '{
            name: $name,
            path: $path,
            rego_text: $rego_text,
            published: true,
            bundle_name: $bundle_name
        }')
    
    print_success "JSON payload created successfully"
else
    print_error "Policy file opa/authz-policy-fixed.rego not found"
    exit 1
fi

POLICY_RESPONSE=$(curl -s -X POST "$API_BASE/policies" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$AUTHZ_POLICY_JSON")

echo "Policy creation response: $POLICY_RESPONSE"

if echo "$POLICY_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    POLICY_ID=$(echo "$POLICY_RESPONSE" | jq -r '.id')
    print_success "Authorization policy created with ID: $POLICY_ID"
else
    print_error "Failed to create authorization policy"
    echo "Response: $POLICY_RESPONSE"
    exit 1
fi

# Create a field-level security policy
echo ""
print_status "Creating field-level security policy..."

# Read the field security policy from file
if [ -f "opa/field_security.rego" ]; then
    FIELD_SECURITY_POLICY_TEXT=$(cat "opa/field_security.rego")
    print_success "Using field security policy from opa/field_security.rego"
    
    # Create JSON payload using jq to properly escape the content
    FIELD_SECURITY_POLICY_JSON=$(jq -n \
        --arg name "field_level_security" \
        --arg path "envoy/field_security.rego" \
        --arg rego_text "$FIELD_SECURITY_POLICY_TEXT" \
        --arg bundle_name "main" \
        '{
            name: $name,
            path: $path,
            rego_text: $rego_text,
            published: true,
            bundle_name: $bundle_name
        }')
    
    print_success "Field security JSON payload created successfully"
else
    print_error "Field security policy file opa/field_security.rego not found"
    exit 1
fi

FIELD_POLICY_RESPONSE=$(curl -s -X POST "$API_BASE/policies" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$FIELD_SECURITY_POLICY_JSON")

echo "Field security policy creation response: $FIELD_POLICY_RESPONSE"

if echo "$FIELD_POLICY_RESPONSE" | jq -e '.id' > /dev/null 2>&1; then
    FIELD_POLICY_ID=$(echo "$FIELD_POLICY_RESPONSE" | jq -r '.id')
    print_success "Field security policy created with ID: $FIELD_POLICY_ID"
else
    print_error "Failed to create field security policy"
    echo "Response: $FIELD_POLICY_RESPONSE"
    exit 1
fi

# Wait for OPA to reload the bundle
echo ""
print_status "Waiting for OPA to reload policies..."
sleep 10

# Verify policies are loaded
echo ""
print_status "Verifying policies are loaded..."

# Check OPA bundle
BUNDLE_CONTENT=$(curl -s "$API_BASE/bundles/main.tar.gz" | tar -tz 2>/dev/null || echo "Bundle not accessible")

if echo "$BUNDLE_CONTENT" | grep -q "envoy/authz.rego"; then
    print_success "Authorization policy loaded in OPA bundle"
else
    print_warning "Authorization policy not yet loaded in bundle"
fi

if echo "$BUNDLE_CONTENT" | grep -q "envoy/field_security.rego"; then
    print_success "Field security policy loaded in OPA bundle"
else
    print_warning "Field security policy not yet loaded in bundle"
fi

# List all policies
echo ""
print_status "Current policies in system:"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" "$API_BASE/policies" | jq -r '.[] | "ID: \(.id) | Name: \(.name) | Published: \(.published) | Path: \(.path)"'

echo ""
echo "✅ Policy System Initialization Complete!"
echo "========================================"
echo ""
echo "📋 What was created:"
echo "   1. Comprehensive authorization policy (envoy/authz.rego)"
echo "   2. Field-level security policy (envoy/field_security.rego)"
echo ""
echo "🔄 Next steps:"
echo "   - Wait 5-10 seconds for OPA to reload policies"
echo "   - Test the authentication system: ./scripts/test_auth.sh"
echo "   - Access the UI: http://localhost:8083/auth.html"
echo ""
echo "💡 The policies will now enforce:"
echo "   - Role-based access control for all users"
echo "   - Field-level security (SSN blocking for restricted users)"
echo "   - Data source restrictions (PostgreSQL vs Iceberg)"
echo "   - Real-time query validation and blocking" 