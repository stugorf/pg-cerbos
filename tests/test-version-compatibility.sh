#!/bin/bash
# Test PuppyGraph version compatibility

set -e

echo "🧪 Testing PuppyGraph Version Compatibility"

# Check version from logs
VERSION=$(docker logs pg-cerbos-puppygraph 2>&1 | grep -i "version" | head -1 | grep -oE "0\.\d+" | head -1)

if [ -z "$VERSION" ]; then
    echo "⚠️  Could not determine PuppyGraph version from logs"
    # Try alternative method: check compose.yml
    VERSION=$(grep -E "puppygraph/puppygraph:" compose.yml | grep -oE "0\.\d+" | head -1)
    if [ -z "$VERSION" ]; then
        echo "❌ Could not determine PuppyGraph version"
        exit 1
    fi
fi

echo "📦 PuppyGraph version: $VERSION"

# Check if version is 0.112 or higher
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)

if [ "$MAJOR" -eq 0 ] && [ "$MINOR" -ge 112 ]; then
    echo "✅ Version is compatible (0.112+)"
elif [ "$MAJOR" -eq 0 ] && [ "$MINOR" -lt 112 ]; then
    echo "⚠️  Version may not be compatible (expected 0.112+, got $VERSION)"
    echo "   Schema format may need adjustment for older versions"
    exit 1
else
    echo "⚠️  Unexpected version format: $VERSION"
    exit 1
fi

# Verify version in compose.yml matches
COMPOSE_VERSION=$(grep -E "puppygraph/puppygraph:" compose.yml | grep -oE "0\.\d+" | head -1)
if [ "$COMPOSE_VERSION" != "$VERSION" ]; then
    echo "⚠️  Version mismatch: compose.yml has $COMPOSE_VERSION, running version is $VERSION"
    echo "   Consider restarting: docker compose restart puppygraph"
fi

echo "✅ Version compatibility test passed"
