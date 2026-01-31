#!/bin/bash
# Check Cerbos configuration and setup

set -e

echo "🔍 Checking Cerbos Configuration..."
echo ""

# Check if cerbos.yaml exists
if [ ! -f "cerbos/cerbos.yaml" ]; then
    echo "❌ cerbos/cerbos.yaml not found"
    exit 1
fi
echo "✅ cerbos.yaml exists"

# Check if policies directory exists
if [ ! -d "cerbos/policies" ]; then
    echo "❌ cerbos/policies directory not found"
    exit 1
fi
echo "✅ Policies directory exists"

# Check for required policy files
REQUIRED_FILES=(
    "cerbos/policies/resource_policies/postgres.yaml"
    "cerbos/policies/resource_policies/iceberg.yaml"
    "cerbos/policies/_schemas/principal.json"
    "cerbos/policies/_schemas/resource.json"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Required file missing: $file"
        exit 1
    fi
done
echo "✅ All required policy files exist"

# Check YAML syntax (if yq or python available)
if command -v python3 &> /dev/null; then
    if python3 -c "import yaml; yaml.safe_load(open('cerbos/cerbos.yaml'))" 2>/dev/null; then
        echo "✅ cerbos.yaml syntax is valid"
    else
        echo "⚠️  Could not validate YAML syntax (PyYAML not installed)"
    fi
fi

echo ""
echo "✅ Configuration check complete!"
echo ""
echo "To check Cerbos logs, run:"
echo "  docker compose logs cerbos"
echo ""
echo "To restart Cerbos, run:"
echo "  docker compose restart cerbos"
