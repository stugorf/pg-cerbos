# Parser Branch Solution

## Key Finding
The parser branch had a **working schema and validation**. The critical difference is:

### Parser Branch Configuration
- **JDBC URI**: `jdbc:postgresql://postgres14:5432/demo_data` (no parameters)
- **PuppyGraph Version**: Likely < 0.109 (before parallelized metadata retrieval)
- **Status**: ✅ **WORKING**

### Current Branch Configuration
- **JDBC URI**: `jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml` (with parameter)
- **PuppyGraph Version**: 0.111 (or 0.109+) with parallelized metadata retrieval
- **Status**: ❌ **BROKEN** (error 244)

## Root Cause
The `:stable` tag moved from a working version (likely 0.108 or earlier) to a broken version (0.109+). The parallelized metadata retrieval introduced in 0.109 has a bug that prevents accessing PostgreSQL table attributes.

## Solution Applied

### 1. Revert JDBC Connection String
Changed from:
```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml"
```

Back to parser branch format:
```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data"
```

### 2. Pin to PuppyGraph 0.108
Changed from:
```yaml
image: puppygraph/puppygraph:stable
```

To:
```yaml
image: puppygraph/puppygraph:0.108
```

## Why This Should Work

1. **0.108 is before the parallelization changes** - No metadata access bug
2. **Matches parser branch JDBC format** - No `currentSchema` parameter needed
3. **User-level search_path is still set** - `ALTER USER postgres SET search_path = aml, public;` provides the schema context

## Testing

After applying these changes:
1. Restart PuppyGraph with version 0.108
2. Test vertex query: `MATCH (c:Customer) RETURN c LIMIT 1`
3. Test edge query: `MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c, a LIMIT 1`

## If 0.108 Works

**Permanently pin to 0.108** in `compose.yml`:
```yaml
puppygraph:
  image: puppygraph/puppygraph:0.108
```

**Document the version requirement** in README or setup docs.

## If 0.108 Also Fails

Test earlier versions:
- 0.107
- 0.106
- 0.105
- etc.

Until we find the last working version, then pin to that.
