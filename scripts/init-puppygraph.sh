#!/bin/bash
# Initialize PuppyGraph with AML schema
# This script waits for PuppyGraph to be ready and provides instructions for schema upload

set -e

PUPPYGRAPH_URL="${PUPPYGRAPH_URL:-http://localhost:8081}"
PUPPYGRAPH_USER="${PUPPYGRAPH_USER:-puppygraph}"
PUPPYGRAPH_PASSWORD="${PUPPYGRAPH_PASSWORD:-puppygraph123}"
SCHEMA_FILE="${SCHEMA_FILE:-./puppygraph/aml-schema.json}"

echo "🐕 Initializing PuppyGraph for AML PoC"
echo "========================================"
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
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ PuppyGraph did not become ready in time"
    echo "   Please check PuppyGraph logs: docker logs pg-cerbos-puppygraph"
    exit 1
fi

echo ""
echo "📋 Schema Upload Instructions"
echo "============================"
echo ""
echo "PuppyGraph schema must be uploaded via the Web UI."
echo ""
echo "1. Open PuppyGraph Web UI: ${PUPPYGRAPH_URL}"
echo "   Username: ${PUPPYGRAPH_USER}"
echo "   Password: ${PUPPYGRAPH_PASSWORD}"
echo ""
echo "2. Navigate to the Schema page"
echo ""
echo "3. Click 'Upload Schema' or use the schema builder"
echo ""
echo "4. Upload the schema file: ${SCHEMA_FILE}"
echo ""
echo "5. Verify the schema loads correctly"
echo ""
echo "Alternative: Use the PuppyGraph CLI or API to upload the schema programmatically"
echo ""
echo "📄 Schema file location: ${SCHEMA_FILE}"
echo ""
echo "✅ PuppyGraph initialization script complete!"
echo ""
echo "💡 Tip: You can also use the PuppyGraph Web UI to explore the graph"
echo "   and test queries once the schema is loaded."
