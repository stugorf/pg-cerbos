#!/bin/bash
# Start Envoy service

set -e

echo "🚀 Starting Envoy..."

# Check if Cerbos adapter is running (required dependency)
if ! docker compose ps cerbos-adapter | grep -q "Up"; then
    echo "⚠️  Cerbos adapter not running. Starting it first..."
    docker compose up -d cerbos-adapter
    sleep 3
fi

# Start Envoy
echo "Starting Envoy..."
docker compose up -d envoy

# Wait a moment
sleep 2

# Check status
echo ""
echo "Checking Envoy status..."
docker compose ps envoy

# Test if Envoy is responding
echo ""
echo "Testing Envoy endpoint..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/v1/info | grep -q "200\|404"; then
    echo "✅ Envoy is responding!"
else
    echo "⚠️  Envoy may still be starting. Check logs with:"
    echo "   docker compose logs envoy"
fi

echo ""
echo "✅ Done! Envoy should now be running on port 8081."
