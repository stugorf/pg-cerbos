#!/bin/bash
# Rebuild and restart the cerbos-adapter

set -e

echo "🔨 Rebuilding cerbos-adapter..."
docker compose build cerbos-adapter

echo "🔄 Restarting cerbos-adapter..."
docker compose restart cerbos-adapter

echo "⏳ Waiting for adapter to start..."
sleep 3

echo "✅ Checking adapter health..."
curl -s http://localhost:3594/health | jq . || echo "Health check failed"

echo ""
echo "📋 Recent adapter logs:"
docker compose logs cerbos-adapter --tail=20

echo ""
echo "✅ Rebuild complete! Check logs above for DEBUG output showing registered routes."
