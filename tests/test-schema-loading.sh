#!/bin/bash
# Test PuppyGraph schema loading at startup

set -e

echo "🧪 Testing PuppyGraph Schema Loading"

# Restart service
echo "🔄 Restarting PuppyGraph..."
docker compose restart puppygraph
sleep 15

# Check schema loading
if docker logs pg-cerbos-puppygraph 2>&1 | grep -q "initial schema"; then
    echo "✅ Schema loading message found"
else
    echo "❌ Schema loading message not found"
    exit 1
fi

# Check configuration ready
if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"ConfigurationReady":true'; then
    echo "✅ Configuration ready"
else
    echo "❌ Configuration not ready"
    exit 1
fi

# Check service healthy
if docker logs pg-cerbos-puppygraph 2>&1 | grep -q '"Healthy":true'; then
    echo "✅ Service healthy"
else
    echo "⚠️  Service not healthy (may be starting up)"
fi

echo "✅ Schema loading test passed"
