-- UES MVP Demo Queries by User Role
-- This file contains demo queries to showcase different user permission levels
-- Run these queries through the web interface at http://localhost:8082

-- ============================================================================
-- ADMIN USER (admin@ues-mvp.com) - Full System Access
-- ============================================================================
-- Password: admin123
-- Capabilities: Full access to all data sources, all fields, system administration

-- 1. PostgreSQL Data Access - Full Access
SELECT 'PostgreSQL Full Access Test' as test_type, COUNT(*) as total_records FROM postgres.public.person

-- 2. PostgreSQL with SSN - Full Access (SSN visible)
SELECT id, first_name, last_name, job_title, ssn, gender 
FROM postgres.public.person 
ORDER BY id 
LIMIT 5

-- 3. Iceberg Data Access - Full Access
SELECT 'Iceberg Full Access Test' as test_type, COUNT(*) as total_records FROM iceberg.demo.employee_performance

-- 4. Iceberg Performance Data - Full Access
SELECT employee_id, performance_score, projects_completed, department 
FROM iceberg.demo.employee_performance 
ORDER BY performance_score DESC 
LIMIT 5

-- 5. Cross-Data Source Query - Full Access
SELECT 
    'PostgreSQL' as source,
    COUNT(*) as record_count,
    'Full access including SSN' as access_level
FROM postgres.public.person
UNION ALL
SELECT 
    'Iceberg' as source,
    COUNT(*) as record_count,
    'Performance metrics data' as access_level
FROM iceberg.demo.employee_performance

-- 6. System Tables Access - Admin Only
SELECT 'System Access Test' as test_type, COUNT(*) as total_policies FROM postgres.public.policies
SELECT 'User Management Test' as test_type, COUNT(*) as total_users FROM postgres.public.users

-- ============================================================================
-- FULL ACCESS USER (fullaccess@ues-mvp.com) - Full Data Access
-- ============================================================================
-- Password: user123
-- Capabilities: Full access to all data sources and fields, no system administration

-- 1. PostgreSQL Data Access - Full Access
SELECT 'PostgreSQL Full Access Test' as test_type, COUNT(*) as total_records FROM postgres.public.person

-- 2. PostgreSQL with SSN - Full Access (SSN visible)
SELECT id, first_name, last_name, job_title, ssn, gender 
FROM postgres.public.person 
WHERE job_title LIKE '%Engineer%'
ORDER BY last_name

-- 3. Iceberg Data Access - Full Access
SELECT 'Iceberg Full Access Test' as test_type, COUNT(*) as total_records FROM iceberg.demo.employee_performance

-- 4. Iceberg Performance Data - Full Access
SELECT employee_id, performance_score, projects_completed, department 
FROM iceberg.demo.employee_performance 
ORDER BY performance_score DESC

-- 5. Cross-Data Source Analysis - Full Access
SELECT 
    p.job_title,
    COUNT(p.id) as postgres_count,
    COUNT(ep.employee_id) as iceberg_count,
    'Full access to both sources' as access_note
FROM postgres.public.person p
FULL OUTER JOIN iceberg.demo.employee_performance ep ON p.id = ep.employee_id
GROUP BY p.job_title
ORDER BY postgres_count DESC

-- 6. Complex Queries - Full Access
SELECT 
    department as source,
    COUNT(*) as count,
    AVG(performance_score) as avg_performance,
    'Full field access' as access_level
FROM iceberg.demo.employee_performance
GROUP BY department
ORDER BY avg_performance DESC

-- ============================================================================
-- POSTGRES-ONLY USER (postgresonly@ues-mvp.com) - PostgreSQL Only
-- ============================================================================
-- Password: user123
-- Capabilities: PostgreSQL access only, no Iceberg access

-- 1. PostgreSQL Data Access - Full Access
SELECT 'PostgreSQL Access Test' as test_type, COUNT(*) as total_records FROM postgres.public.person;

-- 2. PostgreSQL with SSN - Full Access (SSN visible)
SELECT id, first_name, last_name, job_title, ssn, gender 
FROM postgres.public.person 
WHERE gender = 'Female'
ORDER BY first_name;

-- 3. PostgreSQL Data Analysis - Full Access
SELECT 
    job_title,
    COUNT(*) as count,
    'PostgreSQL only access' as access_note
FROM postgres.public.person
GROUP BY job_title
ORDER BY count DESC;

-- 4. PostgreSQL Field Analysis - Full Access
SELECT 
    'SSN Analysis' as analysis_type,
    COUNT(DISTINCT ssn) as unique_ssns,
    'Full SSN access' as access_level
FROM postgres.public.person;

-- 5. PostgreSQL Complex Query - Full Access
SELECT 
    first_name,
    last_name,
    job_title,
    ssn,
    CASE 
        WHEN job_title LIKE '%Engineer%' THEN 'Technical Role'
        WHEN job_title LIKE '%Analyst%' THEN 'Analytical Role'
        ELSE 'Other Role'
    END as role_category,
    'PostgreSQL full access' as access_note
FROM postgres.public.person
ORDER BY role_category, last_name;

-- 6. Iceberg Access Test - Should Fail
-- This query should fail for postgres-only users
-- SELECT 'Iceberg Access Test' as test_type, COUNT(*) as total_records FROM iceberg.sales.person;

-- ============================================================================
-- RESTRICTED USER (restricted@ues-mvp.com) - Restricted Access
-- ============================================================================
-- Password: user123
-- Capabilities: Both data sources, SSN fields masked/restricted

-- 1. PostgreSQL Data Access - Restricted (SSN masked)
SELECT 'PostgreSQL Restricted Access Test' as test_type, COUNT(*) as total_records FROM postgres.public.person;

-- 2. PostgreSQL without SSN - Accessible
SELECT id, first_name, last_name, job_title, gender 
FROM postgres.public.person 
ORDER BY id 
LIMIT 5;

-- 3. Iceberg Data Access - Restricted (SSN masked)
SELECT 'Iceberg Restricted Access Test' as test_type, COUNT(*) as total_records FROM iceberg.demo.employee_performance;

-- 4. Iceberg Performance Data - Accessible
SELECT employee_id, performance_score, projects_completed, department 
FROM iceberg.demo.employee_performance 
ORDER BY performance_score DESC 
LIMIT 5;

-- 5. Cross-Data Source Analysis - Restricted (No SSN)
SELECT 
    p.job_title,
    COUNT(p.id) as postgres_count,
    COUNT(ep.employee_id) as iceberg_count,
    'Restricted access - SSN masked' as access_note
FROM postgres.public.person p
FULL OUTER JOIN iceberg.demo.employee_performance ep ON p.id = ep.employee_id
GROUP BY p.job_title
ORDER BY postgres_count DESC

-- 6. Complex Queries - Restricted (No SSN)
SELECT 
    department as source,
    COUNT(*) as count,
    AVG(performance_score) as avg_performance,
    'Restricted access - SSN not available' as access_level
FROM iceberg.demo.employee_performance
GROUP BY department
ORDER BY avg_performance DESC

-- 7. SSN Field Access Test - Should Fail
-- These queries should fail for restricted users
-- SELECT ssn FROM postgres.public.person LIMIT 1;
-- SELECT ssn FROM iceberg.demo.employee_performance LIMIT 1;
-- SELECT id, first_name, ssn FROM postgres.public.person WHERE ssn LIKE '123%';

-- ============================================================================
-- COMPARISON QUERIES - Test Different Access Levels
-- ============================================================================

-- Query 1: Basic Count Comparison
-- Admin and Full Access: Should see all data
-- Postgres Only: Should see only PostgreSQL data
-- Restricted: Should see both but SSN masked

-- Query 2: SSN Field Access
-- Admin and Full Access: Should see SSN values
-- Postgres Only: Should see SSN values (PostgreSQL only)
-- Restricted: Should be blocked from SSN queries

-- Query 3: Cross-Data Source
-- Admin and Full Access: Should work with full data
-- Postgres Only: Should fail on Iceberg references
-- Restricted: Should work but SSN masked

-- ============================================================================
-- TESTING INSTRUCTIONS
-- ============================================================================

/*
To test these queries:

1. Start the services:
   docker-compose up -d

2. Initialize the system:
   just init

3. Access the web interface:
   http://localhost:8083/auth.html

4. Test each user role:
   - Login with different accounts
   - Run queries appropriate for each role
   - Verify access restrictions work correctly

5. Expected Results:
   - Admin: Full access to everything
   - Full Access: Full data access, no admin features
   - Postgres Only: PostgreSQL only, no Iceberg
   - Restricted: Both sources, SSN blocked/masked

6. Verify SSN Protection:
   - Admin/Full Access: Can see SSN values
   - Restricted: SSN queries should be blocked
   - Column masking should hide SSN values in results
*/ 