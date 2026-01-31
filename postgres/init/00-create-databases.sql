-- Create databases for UES MVP
CREATE DATABASE demo_data;
CREATE DATABASE policy_store;
CREATE DATABASE query_results;
CREATE DATABASE nessie;

-- Create nessie user and grant permissions
CREATE USER nessie WITH PASSWORD 'nessie';
GRANT ALL PRIVILEGES ON DATABASE nessie TO nessie;
GRANT ALL PRIVILEGES ON SCHEMA public TO nessie;
ALTER USER nessie CREATEDB;