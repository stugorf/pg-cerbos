-- Create databases for UES MVP
CREATE DATABASE demo_data;
CREATE DATABASE policy_store;
CREATE DATABASE query_results;
CREATE DATABASE nessie;

-- Create nessie user and grant permissions
CREATE USER nessie WITH PASSWORD 'nessie';
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