-- Create databases for UES MVP
SELECT 'CREATE DATABASE demo_data'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'demo_data')\gexec

SELECT 'CREATE DATABASE policy_store'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'policy_store')\gexec

SELECT 'CREATE DATABASE query_results'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'query_results')\gexec

SELECT 'CREATE DATABASE nessie'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'nessie')\gexec

-- Create nessie user and grant permissions
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nessie') THEN
        CREATE USER nessie WITH PASSWORD 'nessie';
    END IF;
END
$$;
GRANT ALL PRIVILEGES ON DATABASE nessie TO nessie;
ALTER USER nessie CREATEDB;

-- Grant schema permissions within the nessie database
\c nessie
GRANT ALL ON SCHEMA public TO nessie;
ALTER SCHEMA public OWNER TO nessie;

-- Set search_path for postgres user to include aml schema
-- This ensures PuppyGraph can access tables in the aml schema without explicit qualification
ALTER USER postgres SET search_path = aml, public;

-- Set database-level search_path as additional safeguard for PuppyGraph metadata queries
\c demo_data
ALTER DATABASE demo_data SET search_path = aml, public;
