# PuppyGraph Web Search and Community Investigation

## Search Results Summary

### Documentation Findings

Based on the official PuppyGraph documentation ([Edge Reference](https://docs.puppygraph.com/reference/schema/edge/), [Vertex Reference](https://docs.puppygraph.com/reference/schema/vertex/)):

**Key Requirements:**
1. **Edge `id` field must be string type and unique** - This is a strict requirement
2. **Edge `from` and `to` fields must match the node ID type** - Critical for relationship resolution
3. **Schema format**: Documentation shows `mappedTableSource` with `metaFields` as simple string mappings
4. **Parser branch format**: Uses `tableSource` with `fromVertex`/`toVertex` and complex field objects

**Critical Insight**: There appears to be a discrepancy between:
- **API Documentation Format**: `mappedTableSource` with `metaFields: {"id": "field_name", "from": "field_name", "to": "field_name"}`
- **JSON Upload Format (Parser Branch)**: `tableSource` with `fromVertex`/`toVertex` and complex `id`/`fromId`/`toId` field objects

### Error Analysis

**Error Message**: "can not access data source table attributes:map[]"
**Error Code**: 244
**Status Code**: 244 (internal PuppyGraph error)

This error suggests PuppyGraph's backend is:
1. Successfully connecting to PostgreSQL via JDBC
2. Attempting to query table metadata (columns, types, constraints)
3. Getting an empty map/result from the metadata query

### Community Resources

**GitHub Repository**: Found `puppygraph/puppygraph-getting-started` repository with examples and demos. No specific issues about error 244 were found in search results.

**Discord**: No direct Discord invite link found in search results. The PuppyGraph documentation and GitHub repository likely contain community links.

**GitHub Issues**: Searched for issues related to error 244, PostgreSQL schema validation, and metadata access - no specific matching issues found in search results.

### Potential Solutions from Documentation

1. **Type Consistency**: Ensure all vertex IDs and edge `from`/`to` fields use the same type (preferably string)
2. **Schema Format**: The parser branch format (`tableSource` with `fromVertex`/`toVertex`) appears to be the working format for JSON file uploads, despite documentation showing `mappedTableSource`
3. **JDBC Connection**: Verify JDBC connection string and driver compatibility

### Next Steps for Community Engagement

1. **Check PuppyGraph GitHub Repository**: 
   - Repository: `puppygraph/puppygraph-getting-started` (examples)
   - Main repository likely at `puppygraph/puppygraph`
   - Search for issues related to:
     - Error code 244
     - PostgreSQL metadata access failures
     - "can not access data source table attributes"
     - Schema validation with PostgreSQL 14.1

2. **Join PuppyGraph Community**:
   - Check PuppyGraph documentation footer/links for Discord/Slack invite
   - Look for community links in GitHub repository README
   - Check PuppyGraph website for community resources

3. **Post Question/Issue**: Include:
   - **PuppyGraph version**: 0.111
   - **PostgreSQL version**: 14.1
   - **Error message**: "can not access data source table attributes:map[]"
   - **Error code**: 244
   - **Schema format**: `tableSource` with `fromVertex`/`toVertex` (parser branch format)
   - **Key finding**: Parser branch format works, but current setup fails with identical schema
   - **Environment**: Docker Compose, PostgreSQL 14.1, PuppyGraph 0.111

### Documentation References

- [Edge Schema Reference](https://docs.puppygraph.com/reference/schema/edge/)
- [Vertex Schema Reference](https://docs.puppygraph.com/reference/schema/vertex/)
- [PostgreSQL Getting Started](https://docs.puppygraph.com/getting-started/querying-postgresql-data-as-a-graph/)
- [Connecting to PostgreSQL](https://docs.puppygraph.com/connecting/connecting-to-postgresql)

### Key Insights from Documentation

**Critical Requirements:**
1. **Edge `id` field must be string type and unique** - This is a strict requirement
2. **Edge `from` and `to` fields must match node ID types** - Type mismatch causes validation failures
3. **Schema Format Discrepancy**: 
   - Documentation shows `mappedTableSource` with `metaFields` as simple string mappings
   - Parser branch (working) uses `tableSource` with `fromVertex`/`toVertex` and complex field objects
   - This suggests two different schema formats: API format vs JSON upload format

**PostgreSQL Compatibility:**
- PostgreSQL 14.1 is supported (used in official tutorial)
- Text/varchar fields map to String type
- Integer fields map to Int type
- Edge `from`/`to` fields must match vertex ID types exactly

### Search Results Summary

**What Was Found:**
- ✅ Official PuppyGraph documentation with detailed schema requirements
- ✅ PostgreSQL integration examples and tutorials
- ✅ Schema format specifications for nodes and edges
- ✅ Data type mapping requirements

**What Was NOT Found:**
- ❌ Specific Discord community links or invite
- ❌ GitHub issues about error code 244
- ❌ Community discussions about this specific error
- ❌ Known compatibility issues with PuppyGraph 0.111 and PostgreSQL 14.1

**Recommendation**: 
The error appears to be a PuppyGraph backend issue with metadata access during query execution, not a schema format problem. The schema structure matches the working parser branch format. This likely requires:
1. Contacting PuppyGraph support directly
2. Checking PuppyGraph GitHub repository for similar issues
3. Testing with a different PuppyGraph version
4. Verifying if there are any environment-specific configuration differences
