-- Query Results Schema for UES MVP
-- This schema stores query results to avoid Trino query expiration issues

-- Create the query_results database if it doesn't exist
SELECT 'CREATE DATABASE query_results'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'query_results')\gexec

-- Connect to the query_results database
\c query_results;

-- Table to store query metadata
CREATE TABLE IF NOT EXISTS queries (
    id VARCHAR(100) PRIMARY KEY,
    user_id INTEGER NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    sql_query TEXT NOT NULL,
    catalog VARCHAR(100),
    schema VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'QUEUED',
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    execution_time_ms BIGINT,
    rows_returned INTEGER DEFAULT 0,
    bytes_processed BIGINT DEFAULT 0,
    trino_next_uri TEXT,
    trino_info_uri TEXT
);

-- Table to store query result columns
CREATE TABLE IF NOT EXISTS query_columns (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(100) NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    column_name VARCHAR(255) NOT NULL,
    column_type VARCHAR(100),
    column_position INTEGER NOT NULL,
    UNIQUE(query_id, column_position)
);

-- Table to store query result data
CREATE TABLE IF NOT EXISTS query_results (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(100) NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    row_number INTEGER NOT NULL,
    column_position INTEGER NOT NULL,
    cell_value TEXT,
    UNIQUE(query_id, row_number, column_position)
);

-- Table to store query statistics
CREATE TABLE IF NOT EXISTS query_stats (
    id SERIAL PRIMARY KEY,
    query_id VARCHAR(100) NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    stat_name VARCHAR(100) NOT NULL,
    stat_value TEXT,
    stat_type VARCHAR(50) DEFAULT 'string',
    UNIQUE(query_id, stat_name)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_queries_user_id ON queries(user_id);
CREATE INDEX IF NOT EXISTS idx_queries_status ON queries(status);
CREATE INDEX IF NOT EXISTS idx_queries_submitted_at ON queries(submitted_at);
CREATE INDEX IF NOT EXISTS idx_query_results_query_id ON query_results(query_id);
CREATE INDEX IF NOT EXISTS idx_query_columns_query_id ON query_columns(query_id);

-- Function to clean up old queries (older than 24 hours)
CREATE OR REPLACE FUNCTION cleanup_old_queries()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM queries 
    WHERE submitted_at < CURRENT_TIMESTAMP - INTERVAL '24 hours';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create a scheduled job to clean up old queries (if pg_cron is available)
-- SELECT cron.schedule('cleanup-old-queries', '0 */6 * * *', 'SELECT cleanup_old_queries();'); 