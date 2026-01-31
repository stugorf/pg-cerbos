#!/bin/bash

# UES MVP Iceberg Initialization Script (Nessie Catalog)
# This script creates the necessary Iceberg tables using the Nessie catalog

echo "🚀 Initializing Iceberg tables for UES MVP (Nessie Catalog)"
echo "=========================================================="

# Check if Trino is running
echo "📊 Checking Trino status..."
if ! curl -s http://localhost:8080/v1/statement > /dev/null 2>&1; then
    echo "❌ Trino is not running. Please start the services first."
    echo "   Run: docker-compose up -d"
    exit 1
fi

# Wait for Trino to be ready
echo "⏳ Waiting for Trino to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8080/v1/statement > /dev/null 2>&1; then
        echo "✅ Trino is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Trino did not become ready in time"
        exit 1
    fi
    echo "   Attempt $i/30..."
    sleep 2
done

# Check if Iceberg catalog is available
echo "🔍 Checking Iceberg catalog availability..."
CATALOG_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/statement \
  -H "Content-Type: application/json" \
  -H "X-Trino-User: admin" \
  -d "SHOW CATALOGS")

# Get the query ID and wait for completion
CATALOG_ID=$(echo "$CATALOG_RESPONSE" | jq -r '.id')
if [ "$CATALOG_ID" != "null" ] && [ "$CATALOG_ID" != "" ]; then
    echo "✅ Catalog query initiated with ID: $CATALOG_ID"
else
    echo "❌ Failed to get catalog query ID"
    exit 1
fi

# Wait for catalog query to complete and check results
echo "⏳ Waiting for catalog query to complete..."
sleep 10

# Get the next URI and check results
NEXT_URI=$(echo "$CATALOG_RESPONSE" | jq -r '.nextUri')
if [ "$NEXT_URI" != "null" ] && [ "$NEXT_URI" != "" ]; then
    # Wait a bit more for the query to complete
    sleep 15
    
    # Check if iceberg catalog is in the results
    if curl -s "$NEXT_URI" | jq -r '.data[]' | grep -q "iceberg"; then
        echo "✅ Iceberg catalog is available"
    else
        echo "❌ Iceberg catalog not found in results. Check Trino configuration."
        exit 1
    fi
else
    echo "❌ Failed to get next URI for catalog query"
    exit 1
fi

# Create Iceberg schema and tables
echo "🏗️  Creating Iceberg schema and tables..."

# Create schema using Nessie catalog
SCHEMA_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/statement \
  -H "Content-Type: application/json" \
  -H "X-Trino-User: admin" \
  -d "CREATE SCHEMA IF NOT EXISTS iceberg.sales")

if echo "$SCHEMA_RESPONSE" | grep -q "nextUri"; then
    echo "   ✅ Schema creation initiated"
else
    echo "   ❌ Schema creation failed"
    echo "   Response: $SCHEMA_RESPONSE"
fi

# Wait for schema creation
echo "⏳ Waiting for schema creation..."
sleep 5

# Create person table
echo "📋 Creating person table..."
TABLE_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/statement \
  -H "Content-Type: application/json" \
  -H "X-Trino-User: admin" \
  -d "CREATE TABLE IF NOT EXISTS iceberg.sales.person (
    id bigint,
    first_name varchar,
    last_name varchar,
    job_title varchar,
    age integer
  )")

if echo "$TABLE_RESPONSE" | grep -q "nextUri"; then
    echo "   ✅ Table creation initiated"
else
    echo "   ❌ Table creation failed"
    echo "   Response: $TABLE_RESPONSE"
fi

# Wait for table creation
echo "⏳ Waiting for table creation..."
sleep 5

# Insert sample data
echo "📝 Inserting sample data..."
INSERT_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/statement \
  -H "Content-Type: application/json" \
  -H "X-Trino-User: admin" \
  -d "INSERT INTO iceberg.sales.person (id, first_name, last_name, job_title, age) VALUES
(1, 'Alex', 'Thompson', 'Data Scientist', 28),
(2, 'Maria', 'Gonzalez', 'Frontend Developer', 31),
(3, 'James', 'Lee', 'Backend Developer', 29),
(4, 'Sophia', 'Chen', 'Machine Learning Engineer', 26),
(5, 'Daniel', 'White', 'Cloud Architect', 34),
(6, 'Olivia', 'Harris', 'Security Engineer', 27),
(7, 'William', 'Clark', 'Database Administrator', 33),
(8, 'Ava', 'Lewis', 'Network Engineer', 25),
(9, 'Ethan', 'Robinson', 'Site Reliability Engineer', 30),
(10, 'Isabella', 'Walker', 'Technical Writer', 32)")

if echo "$INSERT_RESPONSE" | grep -q "nextUri"; then
    echo "   ✅ Data insertion initiated"
else
    echo "   ❌ Data insertion failed"
    echo "   Response: $INSERT_RESPONSE"
fi

# Wait for data insertion
echo "⏳ Waiting for data insertion..."
sleep 10

# Verify tables exist
echo "🔍 Verifying tables..."
VERIFY_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/statement \
  -H "Content-Type: application/json" \
  -H "X-Trino-User: admin" \
  -d "SHOW TABLES FROM iceberg.sales")

if echo "$VERIFY_RESPONSE" | grep -q "nextUri"; then
    echo "   ✅ Table verification initiated"
else
    echo "   ❌ Table verification failed"
    echo "   Response: $VERIFY_RESPONSE"
fi

# Wait for verification
echo "⏳ Waiting for verification..."
sleep 5

# Test a simple query
echo "🧪 Testing table access..."
TEST_RESPONSE=$(curl -s -X POST http://localhost:8080/v1/statement \
  -H "Content-Type: application/json" \
  -H "X-Trino-User: admin" \
  -d "SELECT COUNT(*) as count FROM iceberg.sales.person")

if echo "$TEST_RESPONSE" | grep -q "nextUri"; then
    echo "   ✅ Test query initiated"
else
    echo "   ❌ Test query failed"
    echo "   Response: $TEST_RESPONSE"
fi

echo ""
echo "🎉 Iceberg initialization complete!"
echo ""
echo "📋 Available tables:"
echo "   - postgres.public.person (PostgreSQL)"
echo "   - iceberg.sales.person (Iceberg - Nessie catalog)"
echo ""
echo "🧪 Test queries:"
echo "   SELECT * FROM postgres.public.person LIMIT 3;"
echo "   SELECT * FROM iceberg.sales.person LIMIT 3;"
echo ""
echo "🔐 Test with different users:"
echo "   - admin@ues-mvp.com (admin123) - Full access"
echo "   - fullaccess@ues-mvp.com (user123) - Full access"
echo "   - postgresonly@ues-mvp.com (user123) - Postgres only"
echo "   - restricted@ues-mvp.com (user123) - Restricted (no SSN)"
echo ""
echo "⚠️  Note: Iceberg tables use Nessie catalog with MinIO S3 backend"
echo "   Tables are created in s3a://warehouse/sales/ location" 