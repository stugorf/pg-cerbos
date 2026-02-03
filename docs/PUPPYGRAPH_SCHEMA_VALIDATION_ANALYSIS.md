# PuppyGraph Schema Validation Issue - Analysis & Resolution Plan

## Executive Summary

The PuppyGraph schema validation is failing with the error: **"failed to execute validation query"** and **"can not access data source table attributes:map[]"**. After reviewing the [PuppyGraph Schema Documentation](https://docs.puppygraph.com/reference/schema/), I've identified several potential issues and developed a comprehensive resolution plan.

## Current Schema Analysis

### ✅ What's Correct

1. **Catalog Definition**: JDBC connection to PostgreSQL 14 is properly configured
2. **Vertex Structure**: Using `oneToOne` with `tableSource` is correct for PostgreSQL
3. **ID Fields**: All vertices have proper `id` field definitions
4. **Attributes**: Field types match PostgreSQL column types (String, Int, DateTime, Boolean, Double)
5. **Table Names**: All table names are unquoted (PuppyGraph handles quoting automatically)

### ❌ Potential Issues Identified

#### Issue 1: Edge Table Source Mismatch
**Problem**: Edges are pointing to **vertex tables** instead of dedicated edge tables.

**Example**:
- `OWNS` edge points to `account` table (which is a vertex table)
- `FROM_ALERT` edge points to `case` table (which is a vertex table)

**Impact**: PuppyGraph expects edges to either:
- Point to dedicated edge tables with explicit `from`/`to` columns, OR
- Use a different schema format for implicit relationships

**Documentation Reference**: According to [PuppyGraph Schema Docs](https://docs.puppygraph.com/reference/schema/), edges should map to tables that have explicit `from` and `to` fields, or use `mappedTableSource` with `metaFields`.

#### Issue 2: Edge ID Field Conflicts
**Problem**: Edge `id` fields are using the same fields as vertex IDs.

**Example**:
- `OWNS` edge uses `account_id` as both the edge ID and the `toId`
- This creates ambiguity about what uniquely identifies the edge

**Impact**: PuppyGraph may not be able to uniquely identify edges, causing validation to fail.

#### Issue 3: Reserved Word Handling
**Problem**: The `case` table is a PostgreSQL reserved word. While we've unquoted it in the schema, PuppyGraph's validation query might still have issues accessing it.

**Evidence**: The error mentions "can not access data source table attributes" which could indicate the validation query is failing when trying to read the `case` table metadata.

#### Issue 4: Missing Edge Attributes
**Problem**: Most edges don't define `attributes`, which might be required for proper schema validation.

**Documentation Reference**: The [Edge documentation](https://docs.puppygraph.com/reference/schema/edge) shows edges should have attributes defined if the source table has additional columns beyond `id`, `from`, and `to`.

## Root Cause Hypothesis

The validation failure is most likely caused by **Issue #1**: Edges pointing to vertex tables. PuppyGraph's validation query tries to:
1. Connect to PostgreSQL via JDBC
2. Query table metadata (columns, types, constraints)
3. Verify that edge tables have the required `from` and `to` fields

When edges point to vertex tables (like `account` or `case`), PuppyGraph gets confused because:
- These tables don't have explicit `from`/`to` columns
- The edge relationships are **implicit** (via foreign keys in the vertex tables)
- PuppyGraph can't find the edge metadata it expects

## Resolution Plan

### Phase 1: Verify Current Schema Format Compatibility

**Action**: Check if our `tableSource` format with `id`/`fromId`/`toId` is the correct format for implicit relationships in PostgreSQL.

**Steps**:
1. Review PuppyGraph documentation for "implicit edge relationships" or "foreign key edges"
2. Check if there's a different schema format for edges that derive from vertex table foreign keys
3. Compare our schema with the PostgreSQL example in the documentation

**Expected Outcome**: Confirm whether we need to use `mappedTableSource` with `metaFields` instead of `tableSource` with separate `id`/`fromId`/`toId`.

### Phase 2: Test Edge Table Source Resolution

**Action**: Verify that PuppyGraph can actually access the tables referenced in edges.

**Steps**:
1. Test direct JDBC connection from PuppyGraph container to PostgreSQL
2. Verify PuppyGraph can query `information_schema` for table metadata
3. Check if the `case` table (reserved word) is accessible via JDBC
4. Test a simple query: `SELECT * FROM aml.case LIMIT 1`

**Expected Outcome**: Identify if the issue is connectivity, permissions, or schema format.

### Phase 3: Restructure Edge Definitions (If Needed)

**Option A: Create Explicit Edge Tables**
- Create dedicated edge tables in PostgreSQL (e.g., `aml.owns`, `aml.sent_txn`)
- Populate them with `from_id`, `to_id`, and edge attributes
- Update schema to point edges to these tables

**Option B: Use Implicit Relationship Format**
- If PuppyGraph supports implicit relationships, update schema format
- May need to use `mappedTableSource` with `metaFields` pointing to foreign key columns
- Ensure edge `id` is unique (might need composite keys or generated IDs)

**Option C: Hybrid Approach**
- Keep vertex tables as-is
- Create views that expose edge relationships
- Point edges to these views instead of vertex tables

### Phase 4: Fix Reserved Word Issue

**Action**: Ensure the `case` table is properly handled.

**Steps**:
1. Test if PuppyGraph can access `aml."case"` (quoted) vs `aml.case` (unquoted)
2. Check if JDBC connection string needs special configuration for reserved words
3. Consider renaming the table if PuppyGraph has persistent issues (last resort)

### Phase 5: Add Missing Edge Attributes

**Action**: Define attributes for edges that have additional columns in source tables.

**Steps**:
1. Review each edge's source table
2. Identify columns that aren't `id`, `from`, or `to` equivalents
3. Add these as edge attributes in the schema

**Example**: The `transaction` table has `amount`, `timestamp`, `channel`, `country` - these should be attributes on edges that use this table.

### Phase 6: Comprehensive Testing

**Action**: Test the schema after fixes.

**Steps**:
1. Restart PuppyGraph with updated schema
2. Test validation in Web UI
3. Run test Cypher queries:
   - `MATCH (c:Customer) RETURN c LIMIT 1`
   - `MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1`
   - `MATCH (c:Case)-[:FROM_ALERT]->(a:Alert) RETURN c, a LIMIT 1`
4. Verify all edges work correctly
5. Test complex traversals

## Immediate Next Steps

1. **Verify Schema Format**: Check PuppyGraph documentation for the correct format for implicit edge relationships in PostgreSQL
2. **Test JDBC Connectivity**: Verify PuppyGraph can access all tables, especially `case`
3. **Check Edge Format**: Compare our edge definitions with documentation examples
4. **Test Simple Query**: Try a basic query to see if the schema actually works despite validation error

## Risk Assessment

- **Low Risk**: Testing and verification steps
- **Medium Risk**: Restructuring edge definitions (may require data migration)
- **High Risk**: Renaming `case` table (would require schema changes and data migration)

## Success Criteria

✅ Schema validates successfully in PuppyGraph Web UI  
✅ All test Cypher queries execute without errors  
✅ All edges can be traversed correctly  
✅ Complex graph queries work as expected  
✅ No "can not access data source table attributes" errors

## References

- [PuppyGraph Schema Documentation](https://docs.puppygraph.com/reference/schema/)
- [PuppyGraph PostgreSQL Tutorial](https://docs.puppygraph.com/getting-started/querying-postgresql-data-as-a-graph/)
- [Edge Schema Reference](https://docs.puppygraph.com/reference/schema/edge)
- [Node (Vertex) Schema Reference](https://docs.puppygraph.com/reference/schema/node-vertex)
