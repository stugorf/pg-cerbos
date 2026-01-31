#!/bin/bash

# Validate Rego Syntax for UES MVP
# This script validates Rego policy files before loading them into OPA

set -e

echo "🔍 Validating Rego Policy Syntax"
echo "================================="

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

# Check if OPA is available for validation
if ! command -v opa &> /dev/null; then
    print_warning "OPA CLI not found. Installing OPA for validation..."
    
    # Install OPA on macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install opa
        else
            print_error "Homebrew not found. Please install OPA manually: https://www.openpolicyagent.org/docs/latest/#running-opa"
            exit 1
        fi
    else
        print_error "Please install OPA manually: https://www.openpolicyagent.org/docs/latest/#running-opa"
        exit 1
    fi
fi

print_success "OPA CLI found: $(opa version)"

# Directory containing Rego policies
POLICY_DIR="opa"
VALIDATION_ERRORS=0

echo ""
print_status "Validating policies in $POLICY_DIR directory..."

# Validate each .rego file
for policy_file in "$POLICY_DIR"/*.rego; do
    if [[ -f "$policy_file" ]]; then
        filename=$(basename "$policy_file")
        print_status "Validating $filename..."
        
        # Use OPA to check syntax
        if opa check "$policy_file" > /dev/null 2>&1; then
            print_success "✓ $filename syntax is valid"
        else
            print_error "✗ $filename has syntax errors"
            VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
            
            # Show detailed errors
            echo "  Validation errors:"
            opa check "$policy_file" 2>&1 | sed 's/^/    /'
        fi
        
        # Additional checks for common issues
        echo "  Checking for common issues..."
        
        # Check for proper package declaration
        if ! grep -q "^package " "$policy_file"; then
            print_warning "  - Missing package declaration"
        fi
        
        # Check for future keywords import
        if ! grep -q "import future.keywords" "$policy_file"; then
            print_warning "  - Missing future keywords import (recommended for modern Rego)"
        fi
        
        # Check for proper rule syntax
        if grep -q "if {" "$policy_file"; then
            if ! grep -q "import future.keywords.if" "$policy_file"; then
                print_warning "  - Using 'if' without future keywords import"
            fi
        fi
        
        if grep -q " in " "$policy_file"; then
            if ! grep -q "import future.keywords.in" "$policy_file"; then
                print_warning "  - Using 'in' without future keywords import"
            fi
        fi
        
        echo ""
    fi
done

# Test policy evaluation
echo ""
print_status "Testing policy evaluation..."

# Create a test input file
cat > /tmp/test_input.json << EOF
{
  "user_roles": ["admin"],
  "attributes": {
    "request": {
      "http": {
        "method": "POST",
        "path": "/v1/statement",
        "headers": {
          "x-user-id": "1",
          "x-user-email": "admin@example.com",
          "x-user-roles": "admin"
        },
        "body": "SELECT * FROM person"
      }
    }
  }
}
EOF

# Test the authz policy
if opa eval --data "$POLICY_DIR/authz-policy-fixed.rego" --input /tmp/test_input.json "data.envoy.authz.allow" > /dev/null 2>&1; then
    print_success "✓ Authz policy evaluation successful"
else
    print_error "✗ Authz policy evaluation failed"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

# Test the field security policy
if opa eval --data "$POLICY_DIR/field_security.rego" "data.envoy.field_security.ssn_access_allowed([\"admin\"])" > /dev/null 2>&1; then
    print_success "✓ Field security policy evaluation successful"
else
    print_error "✗ Field security policy evaluation failed"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

# Clean up test files
rm -f /tmp/test_input.json

echo ""
echo "================================="
echo "Validation Summary"
echo "================================="

if [ $VALIDATION_ERRORS -eq 0 ]; then
    print_success "All policies passed validation! ✅"
    echo ""
    echo "💡 Policies are ready to be loaded into OPA"
    echo "   Run: just ensure-policies"
else
    print_error "Found $VALIDATION_ERRORS validation error(s) ❌"
    echo ""
    echo "🔧 Please fix the errors above before loading policies"
    echo "   Common fixes:"
    echo "   - Check syntax: opa check <filename>"
    echo "   - Add missing imports: import future.keywords.if"
    echo "   - Fix rule syntax: use 'if' instead of 'if {'"
    echo "   - Validate with: opa eval --data <policy> --input <input> <query>"
fi

exit $VALIDATION_ERRORS 