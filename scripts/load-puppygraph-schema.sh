#!/bin/bash
# Load PuppyGraph schema via API (if available) or provide manual instructions
# This script attempts to load the AML schema into PuppyGraph

set -e

PUPPYGRAPH_URL="${PUPPYGRAPH_URL:-http://localhost:8081}"
PUPPYGRAPH_USER="${PUPPYGRAPH_USER:-puppygraph}"
PUPPYGRAPH_PASSWORD="${PUPPYGRAPH_PASSWORD:-puppygraph123}"
SCHEMA_FILE="${SCHEMA_FILE:-./puppygraph/aml-schema.json}"

echo "🐕 Loading PuppyGraph AML Schema"
echo "================================="
echo ""

# Check if schema file exists
if [ ! -f "$SCHEMA_FILE" ]; then
    echo "❌ Schema file not found: $SCHEMA_FILE"
    exit 1
fi

echo "📄 Schema file: $SCHEMA_FILE"
echo ""

# Wait for PuppyGraph to be ready
echo "⏳ Waiting for PuppyGraph to be ready..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f "${PUPPYGRAPH_URL}/api/health" > /dev/null 2>&1; then
        echo "✅ PuppyGraph is ready!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ PuppyGraph did not become ready in time"
    exit 1
fi

echo ""
echo "📤 Attempting to upload schema..."
echo ""

# Try to upload schema via API (if available)
# Note: PuppyGraph may require authentication via Web UI
# This is a placeholder for API-based upload if supported

SCHEMA_CONTENT=$(cat "$SCHEMA_FILE")

# Attempt API upload (may require authentication token)
UPLOAD_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    -u "${PUPPYGRAPH_USER}:${PUPPYGRAPH_PASSWORD}" \
    -d "$SCHEMA_CONTENT" \
    "${PUPPYGRAPH_URL}/api/schema" 2>/dev/null || echo "000")

HTTP_CODE=$(echo "$UPLOAD_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$UPLOAD_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "✅ Schema uploaded successfully!"
    echo ""
    echo "$RESPONSE_BODY" | jq '.' 2>/dev/null || echo "$RESPONSE_BODY"
else
    echo "⚠️  API upload not available or requires different authentication"
    echo ""
    echo "📋 Manual Upload Instructions:"
    echo "=============================="
    echo ""
    echo "1. Open PuppyGraph Web UI: ${PUPPYGRAPH_URL}"
    echo "   Username: ${PUPPYGRAPH_USER}"
    echo "   Password: ${PUPPYGRAPH_PASSWORD}"
    echo ""
    echo "2. Navigate to: Schema → Upload Schema"
    echo ""
    echo "3. Select the schema file: ${SCHEMA_FILE}"
    echo ""
    echo "4. Click 'Upload' and verify the schema loads"
    echo ""
    echo "💡 The schema file is located at: $(realpath "$SCHEMA_FILE")"
fi

echo ""
echo "✅ Schema loading process complete!"
