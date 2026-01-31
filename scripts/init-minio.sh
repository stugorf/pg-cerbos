#!/bin/bash

# MinIO Initialization Script for UES MVP
# This script ensures the warehouse bucket exists and is properly configured

echo "🚀 Initializing MinIO for UES MVP"
echo "=================================="

# Wait for MinIO to be ready
echo "⏳ Waiting for MinIO to be ready..."
sleep 10

# Install mc (MinIO Client) if not available
if ! command -v mc &> /dev/null; then
    echo "📦 Installing MinIO Client..."
    wget -O /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc
    chmod +x /usr/local/bin/mc
fi

# Configure mc client
echo "🔧 Configuring MinIO client..."
mc alias set local http://localhost:9000 ${MINIO_ROOT_USER:-minio} ${MINIO_ROOT_PASSWORD:-minio123}

# Create warehouse bucket if it doesn't exist
echo "🏗️  Creating warehouse bucket..."
if ! mc ls local/warehouse &> /dev/null; then
    mc mb local/warehouse
    echo "✅ Warehouse bucket created"
else
    echo "✅ Warehouse bucket already exists"
fi

# Set bucket policy for Iceberg
echo "🔐 Setting bucket policy..."
mc policy set download local/warehouse

echo "🎉 MinIO initialization complete!"
echo "📋 Available buckets:"
mc ls local

echo ""
echo "🔗 MinIO Console: http://localhost:9001"
echo "   Username: ${MINIO_ROOT_USER:-minio}"
echo "   Password: ${MINIO_ROOT_PASSWORD:-minio123}" 