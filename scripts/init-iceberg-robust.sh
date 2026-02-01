#!/bin/bash

# UES MVP Robust Iceberg Initialization Script
# This script properly initializes the Iceberg catalog and schemas

echo "🚀 Robust Iceberg Initialization for UES MVP"
echo "============================================="

# Configuration
TRINO_HOST="localhost"
TRINO_PORT="8080"
ADMIN_USER="admin"
MAX_RETRIES=5
RETRY_DELAY=10

# Function to wait for Trino to be ready
wait_for_trino() {
    echo "📊 Waiting for Trino to be ready..."
    for i in {1..30}; do
        if curl -s "http://${TRINO_HOST}:${TRINO_PORT}/v1/info" > /dev/null 2>&1; then
            echo "✅ Trino is ready!"
            return 0
        fi
        if [ $i -eq 30 ]; then
            echo "❌ Trino did not become ready in time"
            return 1
        fi
        echo "   Attempt $i/30..."
        sleep 2
    done
}

# Function to execute a Trino query and wait for completion
execute_trino_query() {
    local query="$1"
    local description="$2"
    
    echo "🔍 $description..."
    echo "   Query: $query"
    
    # Submit query
    local response=$(curl -s -X POST "http://${TRINO_HOST}:${TRINO_PORT}/v1/statement" \
        -H "Content-Type: application/json" \
        -H "X-Trino-User: ${ADMIN_USER}" \
        -d "$query")
    
    local query_id=$(echo "$response" | jq -r '.id')
    if [ "$query_id" = "null" ] || [ "$query_id" = "" ]; then
        echo "   ❌ Failed to get query ID"
        echo "   Response: $response"
        return 1
    fi
    
    echo "   ✅ Query submitted with ID: $query_id"
    
    # Wait for completion with timeout
    local start_time=$(date +%s)
    local timeout=120  # 2 minutes timeout
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -gt $timeout ]; then
            echo "   ❌ Query timed out after ${timeout}s"
            # Cancel the query
            curl -s -X DELETE "http://${TRINO_HOST}:${TRINO_PORT}/v1/query/${query_id}" > /dev/null
            return 1
        fi
        
        # Get query status
        local status_response=$(curl -s -H "X-Trino-User: ${ADMIN_USER}" "http://${TRINO_HOST}:${TRINO_PORT}/v1/query" | \
            jq -r ".[] | select(.queryId == \"$query_id\") | .state")
        
        if [ "$status_response" = "FINISHED" ]; then
            echo "   ✅ Query completed successfully"
            return 0
        elif [ "$status_response" = "FAILED" ]; then
            echo "   ❌ Query failed"
            return 1
        elif [ "$status_response" = "FINISHING" ]; then
            echo "   ⏳ Query finishing..."
            sleep 5
        else
            echo "   ⏳ Query status: $status_response"
            sleep 5
        fi
    done
}

# Function to check if schema exists
check_schema_exists() {
    local catalog="$1"
    local schema="$2"
    
    local response=$(curl -s -X POST "http://${TRINO_HOST}:${TRINO_PORT}/v1/statement" \
        -H "Content-Type: application/json" \
        -H "X-Trino-User: ${ADMIN_USER}" \
        -d "SHOW SCHEMAS FROM $catalog")
    
    local query_id=$(echo "$response" | jq -r '.id')
    if [ "$query_id" = "null" ] || [ "$query_id" = "" ]; then
        return 1
    fi
    
    # Wait for completion
    sleep 10
    
    # Get results
    local next_uri=$(echo "$response" | jq -r '.nextUri')
    if [ "$next_uri" != "null" ] && [ "$next_uri" != "" ]; then
        local results=$(curl -s "$next_uri")
        if echo "$results" | jq -r '.data[]' | grep -q "^$schema$"; then
            return 0
        fi
    fi
    
    return 1
}

# Main execution
main() {
    # Wait for Trino
    if ! wait_for_trino; then
        exit 1
    fi
    
    # Wait a bit more for catalogs to initialize
    echo "⏳ Waiting for catalogs to initialize..."
    sleep 15
    
    # Check if Iceberg catalog is available
    echo "🔍 Checking Iceberg catalog availability..."
    if ! execute_trino_query "SHOW CATALOGS" "Checking available catalogs"; then
        echo "❌ Failed to check catalogs"
        exit 1
    fi
    
    # Wait for catalog query to complete
    sleep 10
    
    # Check if iceberg catalog is in the results
    local catalog_response=$(curl -s -X POST "http://${TRINO_HOST}:${TRINO_PORT}/v1/statement" \
        -H "Content-Type: application/json" \
        -H "X-Trino-User: ${ADMIN_USER}" \
        -d "SHOW CATALOGS")
    
    local catalog_id=$(echo "$catalog_response" | jq -r '.id')
    if [ "$catalog_id" != "null" ] && [ "$catalog_id" != "" ]; then
        sleep 15
        
        # Get results
        local next_uri=$(echo "$catalog_response" | jq -r '.nextUri')
        if [ "$next_uri" != "null" ] && [ "$next_uri" != "" ]; then
            local results=$(curl -s "$next_uri")
            if echo "$results" | jq -r '.data[]' | grep -q "iceberg"; then
                echo "✅ Iceberg catalog is available"
            else
                echo "❌ Iceberg catalog not found in results"
                exit 1
            fi
        else
            echo "❌ Failed to get catalog results"
            exit 1
        fi
    else
        echo "❌ Failed to get catalog query ID"
        exit 1
    fi
    
    # Create schemas if they don't exist
    echo "🏗️  Creating Iceberg schemas..."
    
    # Create demo schema
    if ! check_schema_exists "iceberg" "demo"; then
        echo "   Creating iceberg.demo schema..."
        if ! execute_trino_query "CREATE SCHEMA IF NOT EXISTS iceberg.demo" "Creating demo schema"; then
            echo "   ❌ Failed to create demo schema"
            exit 1
        fi
        echo "   ✅ Demo schema created"
    else
        echo "   ✅ Demo schema already exists"
    fi
    
    # Create sales schema
    if ! check_schema_exists "iceberg" "sales"; then
        echo "   Creating iceberg.sales schema..."
        if ! execute_trino_query "CREATE SCHEMA IF NOT EXISTS iceberg.sales" "Creating sales schema"; then
            echo "   ❌ Failed to create sales schema"
            exit 1
        fi
        echo "   ✅ Sales schema created"
    else
        echo "   ✅ Sales schema already exists"
    fi
    
    # Create sample tables and data
    echo "📋 Creating sample tables and data..."
    
    # Create person table in sales schema
    if ! execute_trino_query "CREATE TABLE IF NOT EXISTS iceberg.sales.person (
        id bigint,
        first_name varchar,
        last_name varchar,
        job_title varchar,
        age integer
    )" "Creating person table"; then
        echo "   ❌ Failed to create person table"
        exit 1
    fi
    
    # Insert sample data
    if ! execute_trino_query "INSERT INTO iceberg.sales.person (id, first_name, last_name, job_title, age) VALUES
(1, 'Alex', 'Thompson', 'Data Scientist', 28),
(2, 'Maria', 'Gonzalez', 'Frontend Developer', 31),
(3, 'James', 'Lee', 'Backend Developer', 29),
(4, 'Sophia', 'Chen', 'Machine Learning Engineer', 26),
(5, 'Daniel', 'White', 'Cloud Architect', 34)" "Inserting sample data"; then
        echo "   ❌ Failed to insert sample data"
        exit 1
    fi
    
    # Create employee_performance table in demo schema
    if ! execute_trino_query "CREATE TABLE IF NOT EXISTS iceberg.demo.employee_performance (
        employee_id bigint,
        performance_score decimal(5,2),
        projects_completed integer,
        department varchar
    )" "Creating employee_performance table"; then
        echo "   ❌ Failed to create employee_performance table"
        exit 1
    fi
    
    # Insert sample performance data
    if ! execute_trino_query "INSERT INTO iceberg.demo.employee_performance (employee_id, performance_score, projects_completed, department) VALUES
(1, 4.2, 8, 'Engineering'),
(2, 3.8, 6, 'Engineering'),
(3, 4.5, 10, 'Engineering'),
(4, 4.1, 7, 'Data Science'),
(5, 3.9, 5, 'Infrastructure')" "Inserting performance data"; then
        echo "   ❌ Failed to insert performance data"
        exit 1
    fi
    
    # Verify tables exist
    echo "🔍 Verifying tables..."
    if ! execute_trino_query "SHOW TABLES FROM iceberg.sales" "Verifying sales tables"; then
        echo "   ❌ Failed to verify sales tables"
        exit 1
    fi
    
    if ! execute_trino_query "SHOW TABLES FROM iceberg.demo" "Verifying demo tables"; then
        echo "   ❌ Failed to verify demo tables"
        exit 1
    fi
    
    # Test queries
    echo "🧪 Testing table access..."
    if ! execute_trino_query "SELECT COUNT(*) as count FROM iceberg.sales.person" "Testing person table"; then
        echo "   ❌ Failed to test person table"
        exit 1
    fi
    
    if ! execute_trino_query "SELECT COUNT(*) as count FROM iceberg.demo.employee_performance" "Testing performance table"; then
        echo "   ❌ Failed to test performance table"
        exit 1
    fi
    
    echo ""
    echo "🎉 Robust Iceberg initialization complete!"
    echo ""
    echo "📋 Available schemas and tables:"
    echo "   - iceberg.sales.person (Iceberg - Nessie catalog)"
    echo "   - iceberg.demo.employee_performance (Iceberg - Nessie catalog)"
    echo "   - postgres.public.person (PostgreSQL)"
    echo ""
    echo "🧪 Test queries:"
    echo "   SELECT * FROM iceberg.sales.person LIMIT 3;"
    echo "   SELECT * FROM iceberg.demo.employee_performance LIMIT 3;"
    echo "   SELECT * FROM postgres.public.person LIMIT 3;"
    echo ""
    echo "🔐 Test with different users:"
    echo "   - admin@pg-cerbos.com (admin123) - Full access"
    echo "   - fullaccess@pg-cerbos.com (user123) - Full access"
    echo "   - postgresonly@pg-cerbos.com (user123) - Postgres only"
    echo "   - restricted@pg-cerbos.com (user123) - Restricted (no SSN)"
    echo ""
    echo "⚠️  Note: Iceberg tables now persist across container rebuilds!"
    echo "   Tables are stored in s3a://warehouse/ with Nessie catalog persistence"
}

# Run main function
main "$@" 