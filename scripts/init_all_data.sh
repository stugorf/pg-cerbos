#!/bin/bash

# UES MVP Complete Data Initialization Script
# This script ensures all tables have demo data for new developers

echo "🚀 Initializing complete UES MVP demo data..."

# Check if services are running
echo "📊 Checking service status..."
if ! docker compose ps | grep -q "Up"; then
    echo "❌ Services are not running. Please start them first:"
    echo "   docker compose up -d"
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

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker compose exec postgres pg_isready -U postgres > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ PostgreSQL did not become ready in time"
        exit 1
    fi
    echo "   Attempt $i/30..."
    sleep 2
done

echo ""
echo "🏗️  Initializing PostgreSQL demo data..."

# Initialize PostgreSQL demo data
docker compose exec postgres psql -U postgres -d demo_data -c "
-- Ensure person table exists with demo data
CREATE TABLE IF NOT EXISTS person (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    job_title VARCHAR(100) NOT NULL,
    ssn VARCHAR(20) UNIQUE NOT NULL,
    gender VARCHAR(10) NOT NULL,
    age INTEGER NOT NULL
);

-- Clear existing data and insert fresh demo data
TRUNCATE person;

INSERT INTO person (first_name, last_name, job_title, ssn, gender, age) VALUES
('John', 'Smith', 'Software Engineer', '123-45-6789', 'Male', 28),
('Sarah', 'Johnson', 'Data Analyst', '234-56-7890', 'Female', 32),
('Michael', 'Brown', 'Product Manager', '345-67-8901', 'Male', 35),
('Emily', 'Davis', 'UX Designer', '456-78-9012', 'Female', 29),
('David', 'Wilson', 'DevOps Engineer', '567-89-0123', 'Male', 31),
('Lisa', 'Anderson', 'Business Analyst', '678-90-1234', 'Female', 33),
('Robert', 'Taylor', 'Frontend Developer', '789-01-2345', 'Male', 27),
('Jennifer', 'Martinez', 'Backend Developer', '890-12-3456', 'Female', 30),
('Christopher', 'Garcia', 'QA Engineer', '901-23-4567', 'Male', 26),
('Amanda', 'Rodriguez', 'Scrum Master', '012-34-5678', 'Female', 34);

SELECT 'PostgreSQL person table initialized with ' || COUNT(*) || ' rows' as status FROM person;
"

echo ""
echo "🏗️  Initializing Iceberg demo data..."

# Initialize Iceberg demo data
docker compose exec trino-coordinator trino --execute "
-- Drop and recreate person table with correct schema
DROP TABLE IF EXISTS iceberg.sales.person;

CREATE TABLE iceberg.sales.person (
    id bigint,
    first_name varchar,
    last_name varchar,
    job_title varchar,
    ssn varchar,
    gender varchar,
    age integer
);

-- Insert comprehensive demo data
INSERT INTO iceberg.sales.person (id, first_name, last_name, job_title, ssn, gender, age) VALUES
(1, 'Alex', 'Thompson', 'Data Scientist', '111-22-3333', 'Male', 28),
(2, 'Maria', 'Gonzalez', 'Frontend Developer', '222-33-4444', 'Female', 31),
(3, 'James', 'Lee', 'Backend Developer', '333-44-5555', 'Male', 29),
(4, 'Sophia', 'Chen', 'Machine Learning Engineer', '444-55-6666', 'Female', 26),
(5, 'Daniel', 'White', 'Cloud Architect', '555-66-7777', 'Male', 34),
(6, 'Olivia', 'Harris', 'Security Engineer', '666-77-8888', 'Female', 27),
(7, 'William', 'Clark', 'Database Administrator', '777-88-9999', 'Male', 33),
(8, 'Ava', 'Lewis', 'Network Engineer', '888-99-0000', 'Female', 25),
(9, 'Ethan', 'Robinson', 'Site Reliability Engineer', '999-00-1111', 'Male', 30),
(10, 'Isabella', 'Walker', 'Technical Writer', '000-11-2222', 'Female', 32),
(11, 'Noah', 'Hall', 'Data Engineer', '111-33-4444', 'Male', 29),
(12, 'Emma', 'Allen', 'Product Owner', '222-44-5555', 'Female', 31),
(13, 'Liam', 'Young', 'System Administrator', '333-55-6666', 'Male', 28),
(14, 'Charlotte', 'King', 'Business Intelligence Analyst', '444-66-7777', 'Female', 26),
(15, 'Mason', 'Wright', 'Full Stack Developer', '555-77-8888', 'Male', 32);

SELECT 'Iceberg person table initialized with ' || COUNT(*) || ' rows' as status FROM iceberg.sales.person;
"

echo ""
echo "🔐 Verifying authentication system..."

# Verify auth system has data
docker compose exec postgres psql -U postgres -d policy_store -c "
SELECT 'Users: ' || COUNT(*) as status FROM users;
SELECT 'Roles: ' || COUNT(*) as status FROM roles;
SELECT 'Permissions: ' || COUNT(*) as status FROM permissions;
"

echo ""
echo "🧪 Testing queries..."

# Test PostgreSQL query
echo "Testing PostgreSQL query..."
docker compose exec trino-coordinator trino --execute "
SELECT 'PostgreSQL test' as source, COUNT(*) as count FROM postgres.public.person;
"

# Test Iceberg query
echo "Testing Iceberg query..."
docker compose exec trino-coordinator trino --execute "
SELECT 'Iceberg test' as source, COUNT(*) as count FROM iceberg.sales.person;
"

echo ""
echo "🎉 Complete data initialization finished!"
echo ""
echo "📋 Available data sources:"
echo "   ✅ PostgreSQL: postgres.public.person (10 rows)"
echo "   ✅ Iceberg: iceberg.sales.person (15 rows)"
echo "   ✅ Authentication: Users, roles, and permissions configured"
echo ""
echo "🧪 Test queries you can run:"
echo "   SELECT * FROM postgres.public.person LIMIT 3;"
echo "   SELECT * FROM iceberg.sales.person LIMIT 3;"
echo "   SELECT COUNT(*) FROM postgres.public.person;"
echo "   SELECT COUNT(*) FROM iceberg.sales.person;"
echo ""
echo "🔐 Test users available:"
echo "   - admin@pg-cerbos.com (admin123) - Full access"
echo "   - fullaccess@pg-cerbos.com (user123) - Full access"
echo "   - postgresonly@pg-cerbos.com (user123) - Postgres only"
echo "   - restricted@pg-cerbos.com (user123) - Restricted (no SSN)"
echo ""
echo "🌐 Access the web interface at: http://localhost:8082" 