#!/bin/bash
# Start Cerbos adapter service

set -e

echo "🔧 Building and starting Cerbos adapter..."

# First, ensure Cerbos is running
echo "Checking Cerbos status..."
if ! docker compose ps cerbos | grep -q "Up"; then
    echo "Starting Cerbos first..."
    docker compose up -d cerbos
    echo "Waiting for Cerbos to be ready..."
    sleep 5
fi

# Build the adapter image
echo "Building adapter image..."
docker compose build cerbos-adapter

# Start the adapter (it will wait for Cerbos to be ready)
echo "Starting adapter..."
docker compose up -d cerbos-adapter

# Wait a moment for it to start
sleep 3

# Check status
echo ""
echo "Checking adapter status..."
docker compose ps cerbos-adapter

# Check health
echo ""
echo "Checking adapter health..."
if curl -f http://localhost:3594/health 2>/dev/null; then
    echo "✅ Adapter is healthy!"
else
    echo "⚠️  Adapter may still be starting. Check logs with:"
    echo "   docker compose logs cerbos-adapter"
fi

echo ""
echo "✅ Done! Adapter should now be running."
