#!/bin/bash

# UES MVP Complete Initialization Script
# This script sets up the entire system for new developers
# 
# IMPORTANT: This script includes database schema compatibility fixes:
# - Adds missing 'updated_at' column to policies table in policy_store database
# - Adds missing 'trino_query_id' column to queries table in query_results database
# These fixes prevent the "generator didn't stop after throw()" error during query execution.

set -e

echo "🚀 UES MVP Complete Initialization"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name=$1
    local url=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts - waiting..."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start after $max_attempts attempts"
    return 1
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    print_success "Docker is running"
}

# Function to check if .env file exists
check_env() {
    if [ ! -f .env ]; then
        print_warning ".env file not found. Creating from .env.example..."
        if [ -f .env.example ]; then
            cp .env.example .env
            print_success ".env file created from .env.example"
        else
            print_error ".env.example file not found. Please create a .env file with required environment variables."
            exit 1
        fi
    else
        print_success ".env file found"
    fi
}

# Main initialization process
main() {
    echo "🔍 Pre-flight checks..."
    check_docker
    check_env
    
    echo ""
    echo "🐳 Starting services..."
    print_status "Starting Docker Compose services..."
    docker compose up -d --build
    
    echo ""
    echo "⏳ Waiting for services to be ready..."
    
    # Wait for Postgres
    print_status "Waiting for Postgres to be ready..."
    local postgres_ready=false
    local attempt=1
    local max_attempts=60
    
    while [ $attempt -le $max_attempts ] && [ "$postgres_ready" = false ]; do
        if docker exec pg-cerbos-postgres pg_isready -U postgres > /dev/null 2>&1; then
            postgres_ready=true
            print_success "Postgres is ready!"
        else
            echo "   Attempt $attempt/$max_attempts - waiting..."
            sleep 2
            attempt=$((attempt + 1))
        fi
    done
    
    if [ "$postgres_ready" = false ]; then
        print_error "Postgres failed to start after $max_attempts attempts"
        exit 1
    fi
    
    # Wait for Trino Coordinator
    wait_for_service "Trino Coordinator" "http://localhost:8080/v1/info" 60
    
    # Wait for MinIO to be ready
    wait_for_service "MinIO" "http://localhost:9000/minio/health/live" 60
    
    # Initialize MinIO warehouse bucket
    print_status "Initializing MinIO warehouse bucket..."
    if docker exec pg-cerbos-minio bash /docker-entrypoint-initdb.d/init-minio.sh >/dev/null 2>&1; then
        print_success "MinIO warehouse bucket initialized"
    else
        print_warning "MinIO initialization had issues - this may be normal if already configured"
    fi
    
    # Additional Trino health check and cleanup
    print_status "Performing Trino health check and cleanup..."
    sleep 5
    
    # Check for and kill any hanging queries
    print_status "Checking for hanging queries..."
    HANGING_QUERIES=$(docker exec pg-cerbos-trino-coordinator trino --execute "SELECT query_id FROM system.runtime.queries WHERE state = 'RUNNING' AND query_id != (SELECT query_id FROM system.runtime.queries WHERE state = 'RUNNING' ORDER BY created DESC LIMIT 1)" 2>/dev/null | grep -v "query_id" | tr -d '"' || echo "")
    
    if [ -n "$HANGING_QUERIES" ]; then
        print_warning "Found hanging queries, cleaning them up..."
        for QUERY_ID in $HANGING_QUERIES; do
            if [ -n "$QUERY_ID" ]; then
                print_status "Killing hanging query: $QUERY_ID"
                docker exec pg-cerbos-trino-coordinator trino --execute "CALL system.runtime.kill_query('$QUERY_ID')" >/dev/null 2>&1
            fi
        done
        print_success "Hanging queries cleaned up"
    else
        print_success "No hanging queries found"
    fi
    
    # Wait for Policy Registry API
    wait_for_service "Policy Registry API" "http://localhost:8082/health" 60
    
    # Wait for Cerbos
    wait_for_service "Cerbos" "http://localhost:3593/_cerbos/health" 60
    
    echo ""
    echo "🗄️ Initializing databases..."
    
    # Wait a bit more for Postgres to fully initialize
    print_status "Waiting for Postgres to fully initialize..."
    sleep 10
    
    # Check if databases were created
    print_status "Verifying database initialization..."
    if docker exec pg-cerbos-postgres psql -U postgres -lqt | grep -q demo_data; then
        print_success "Demo data database created"
    else
        print_warning "Demo data database not found - this may be normal on first run"
    fi
    
    if docker exec pg-cerbos-postgres psql -U postgres -lqt | grep -q policy_store; then
        print_success "Policy store database created"
    else
        print_warning "Policy store database not found - this may be normal on first run"
    fi
    
    if docker exec pg-cerbos-postgres psql -U postgres -lqt | grep -q query_results; then
        print_success "Query results database created"
    else
        print_warning "Query results database not found - this may be normal on first run"
    fi
    
    # Fix schema compatibility issues
    print_status "Checking and fixing schema compatibility..."
    if docker exec pg-cerbos-postgres psql -U postgres -d policy_store -c "ALTER TABLE policies ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();" > /dev/null 2>&1; then
        print_success "Schema compatibility check completed"
    else
        print_warning "Schema compatibility check failed - this may be normal if table doesn't exist yet"
    fi
    
    # Fix query results database schema compatibility
    print_status "Checking and fixing query results database schema..."
    if docker exec pg-cerbos-query-results psql -U postgres -d query_results -c "ALTER TABLE queries ADD COLUMN IF NOT EXISTS trino_query_id character varying(100)" > /dev/null 2>&1; then
        print_success "Query results database schema compatibility ensured"
    else
        print_warning "Query results database schema check failed - this may be normal if table doesn't exist yet"
    fi
    
    echo ""
    echo "🧊 Initializing Iceberg with Catalog Persistence..."
    print_status "Running robust Iceberg initialization..."
    
    # Wait for Trino to be fully ready
    sleep 5
    
    # Use our new robust Iceberg initialization script
    if bash scripts/init-iceberg-robust.sh; then
        print_success "Robust Iceberg initialization completed successfully"
    else
        print_warning "Robust Iceberg initialization had issues - this may be normal on first run"
        print_warning "Iceberg queries may not work until the catalog is properly initialized"
        print_warning "PostgreSQL queries will work normally"
    fi
    
    echo ""
    echo "🔐 Checking and seeding database data..."
    
    # Check if seed data exists in policy_store database
    print_status "Checking if database seed data exists..."
    USER_COUNT=$(docker exec pg-cerbos-postgres psql -U postgres -d policy_store -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' ' || echo "0")
    ROLE_COUNT=$(docker exec pg-cerbos-postgres psql -U postgres -d policy_store -t -c "SELECT COUNT(*) FROM roles;" 2>/dev/null | tr -d ' ' || echo "0")
    
    if [ "$USER_COUNT" -gt 0 ] && [ "$ROLE_COUNT" -gt 0 ]; then
        print_success "Database already seeded with $USER_COUNT users and $ROLE_COUNT roles"
        
        # Ensure admin user is active even if already seeded
        print_status "Ensuring admin user is active..."
        docker exec pg-cerbos-postgres psql -U postgres -d policy_store -c "UPDATE users SET is_active = TRUE WHERE email = 'admin@pg-cerbos.com';" > /dev/null 2>&1
        
        # Verify admin user is active
        ADMIN_ACTIVE=$(docker exec pg-cerbos-postgres psql -U postgres -d policy_store -t -c "SELECT is_active FROM users WHERE email = 'admin@pg-cerbos.com';" 2>/dev/null | tr -d ' ' || echo "NULL")
        if [ "$ADMIN_ACTIVE" = "t" ]; then
            print_success "Admin user is now active"
        else
            print_warning "Admin user activation status: $ADMIN_ACTIVE"
        fi
        
        # Final schema compatibility check after seeding
        print_status "Performing final schema compatibility check..."
        docker exec pg-cerbos-postgres psql -U postgres -d policy_store -c "ALTER TABLE policies ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();" > /dev/null 2>&1
        print_success "Schema compatibility ensured"
    else
        print_warning "Database not seeded. Running seed scripts manually..."
        
        # Run the seed scripts manually
        print_status "Seeding roles and permissions..."
        docker exec pg-cerbos-postgres psql -U postgres -d policy_store -f /docker-entrypoint-initdb.d/30-auth-schema.sql > /dev/null 2>&1
        docker exec pg-cerbos-postgres psql -U postgres -d policy_store -f /docker-entrypoint-initdb.d/40-auth-seed-data.sql > /dev/null 2>&1
        
        # Verify seeding was successful
        sleep 2
        USER_COUNT_AFTER=$(docker exec pg-cerbos-postgres psql -U postgres -d policy_store -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' ' || echo "0")
        ROLE_COUNT_AFTER=$(docker exec pg-cerbos-postgres psql -U postgres -d policy_store -t -c "SELECT COUNT(*) FROM roles;" 2>/dev/null | tr -d ' ' || echo "0")
        
        if [ "$USER_COUNT_AFTER" -gt 0 ] && [ "$ROLE_COUNT_AFTER" -gt 0 ]; then
            print_success "Database seeded successfully with $USER_COUNT_AFTER users and $ROLE_COUNT_AFTER roles"
            
            # Fix admin user is_active field if needed
            print_status "Ensuring admin user is active..."
            docker exec pg-cerbos-postgres psql -U postgres -d policy_store -c "UPDATE users SET is_active = TRUE WHERE email = 'admin@pg-cerbos.com';" > /dev/null 2>&1
            
            # Verify admin user is active
            ADMIN_ACTIVE=$(docker exec pg-cerbos-postgres psql -U postgres -d policy_store -t -c "SELECT is_active FROM users WHERE email = 'admin@pg-cerbos.com';" 2>/dev/null | tr -d ' ' || echo "NULL")
            if [ "$ADMIN_ACTIVE" = "t" ]; then
                print_success "Admin user is now active"
            else
                print_warning "Admin user activation status: $ADMIN_ACTIVE"
            fi
            
            # Final schema compatibility check after seeding
            print_status "Performing final schema compatibility check..."
            docker exec pg-cerbos-postgres psql -U postgres -d policy_store -c "ALTER TABLE policies ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now();" > /dev/null 2>&1
            print_success "Schema compatibility ensured"
        else
            print_error "Database seeding failed"
            exit 1
        fi
    fi
    
    echo ""
    echo "🔐 Cerbos policies are managed via the UI or directly in cerbos/policies/"
    print_status "Cerbos policies are automatically loaded from the mounted volume"
    
    echo ""
    echo "✅ Initialization complete!"
    echo ""
    echo "🌐 Services available at:"
    echo "   • Authentication UI: http://localhost:8083/auth.html"
    echo "   • Policy Registry UI: http://localhost:8083"
    echo "   • Policy Registry API: http://localhost:8082"
    echo "   • Trino Coordinator: http://localhost:8080"
    echo "   • Cerbos PDP: http://localhost:3593"
    echo ""
    echo "👥 Demo users:"
    echo "   • Admin: admin@pg-cerbos.com / admin123"
    echo "   • Full Access: fullaccess@pg-cerbos.com / user123"
    echo "   • Postgres Only: postgresonly@pg-cerbos.com / user123"
    echo "   • Restricted: restricted@pg-cerbos.com / user123"
    echo ""
    echo "🚀 You can now:"
    echo "   1. Open http://localhost:8083/auth.html"
    echo "   2. Login with any demo user"
    echo "   3. Execute SQL queries through the web interface"
    echo "   4. Manage policies and users (admin only)"
    echo ""
    echo "📊 Demo Data Available:"
echo "   • PostgreSQL: postgres.public.person (10 records with names, SSNs, job titles)"
echo "   • Iceberg: iceberg.demo.employee_performance (10 records with performance metrics)"
    echo ""
    echo "💡 Sample Queries:"
echo "   • SELECT * FROM postgres.public.person LIMIT 5;"
echo "   • SELECT COUNT(*) FROM postgres.public.person;"
echo "   • SELECT job_title, COUNT(*) FROM postgres.public.person GROUP BY job_title;"
echo "   • SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC;"
echo "   • SELECT p.first_name, p.last_name, p.job_title, ep.performance_score, ep.department FROM postgres.public.person p JOIN iceberg.demo.employee_performance ep ON p.id = ep.employee_id ORDER BY ep.performance_score DESC LIMIT 5;"
    echo ""
    echo "💡 Use 'just logs' to view service logs"
    echo "💡 Use 'just down' to stop all services"
}

# Run main function
main "$@" 