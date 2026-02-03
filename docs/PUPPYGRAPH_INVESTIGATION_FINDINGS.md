# PuppyGraph Schema Investigation Findings

## Current Status

**Error**: "can not access data source table attributes:map[]"  
**Affects**: Both vertex AND edge queries (previously only edges failed)

## Investigation Results

### Schema Format ✅
- Schema matches parser branch format exactly
- Uses `tableSource` with `fromVertex`/`toVertex`
- Edges point to vertex tables (e.g., `account` for `OWNS`)
- No attributes on edges

### Environment Comparison ✅
- **PuppyGraph Image**: Both use `puppygraph/puppygraph:stable`
- **PostgreSQL Version**: Both use `postgres:14.1-alpine`
- **JDBC Connection**: Identical (`jdbc:postgresql://postgres14:5432/demo_data`)
- **Schema Path**: Identical (`/puppygraph/conf/aml-schema.json`)
- **Environment Variables**: Identical

### Database State ✅
- **Tables Exist**: All AML tables present (`customer`, `account`, `transaction`, etc.)
- **Data Present**: 5 customers, 8 accounts, 8 transactions
- **Permissions**: Full SELECT grants on all tables
- **Schema Access**: `postgres` user has USAGE on `aml` schema
- **Table Metadata**: Accessible via `information_schema`

### Key Observations

1. **Schema Loads Successfully**: PuppyGraph reports `ConfigurationReady: true`
2. **Queries Fail at Execution**: Error occurs when executing queries, not during schema load
3. **Error Code 244**: Internal PuppyGraph error code suggesting metadata access failure
4. **Both Vertex and Edge Queries Fail**: Previously only edges failed, now vertices also fail

### Hypothesis

The error "can not access data source table attributes:map[]" suggests PuppyGraph's backend is:
1. Successfully connecting to PostgreSQL via JDBC
2. Attempting to query table column metadata
3. Getting an empty map/result from the metadata query

This could be caused by:
- **JDBC Driver Version Issue**: The PostgreSQL JDBC driver in PuppyGraph might not be compatible with PostgreSQL 14.1
- **Metadata Query Format**: PuppyGraph might be using a metadata query that doesn't work with our PostgreSQL setup
- **Schema Search Path**: PuppyGraph might not be setting the correct search_path when querying metadata
- **Connection Pool Issue**: The JDBC connection might be in a bad state

### Next Steps

1. **Test Direct JDBC Connection**: Try connecting to PostgreSQL from within PuppyGraph container using JDBC
2. **Check PuppyGraph Backend Logs**: Look for more detailed error messages in backend component logs
3. **Test with Different PostgreSQL Version**: Try PostgreSQL 13 or 15
4. **Check JDBC Driver Version**: Verify which PostgreSQL JDBC driver version PuppyGraph is using
5. **Test Schema Upload via UI**: Try uploading schema via PuppyGraph Web UI instead of file mount

### Files Checked

- ✅ `puppygraph/aml-schema.json` - Matches parser branch
- ✅ `compose.yml` - PuppyGraph configuration matches parser branch
- ✅ PostgreSQL tables and data - Present and accessible
- ✅ Permissions - All granted correctly

### Commands Run

- Schema format comparison
- Environment variable comparison
- Database state verification
- Permission verification
- Metadata query testing
- Schema loading verification
