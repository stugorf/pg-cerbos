# Parser Branch Comparison

## Key Finding
The parser branch had a **working schema and validation**, which means the issue is likely environmental or version-related, not schema format.

## Differences Identified

### 1. JDBC Connection String
**Parser Branch**:
```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data"
```
- No `currentSchema` parameter
- No `searchPath` parameter

**Current Branch**:
```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data?currentSchema=aml"
```
- Added `currentSchema=aml` parameter

### 2. PuppyGraph Version
**Parser Branch**:
- Used `puppygraph/puppygraph:stable` tag
- **Likely version**: Pre-0.109 (before parallelized metadata retrieval)

**Current Branch**:
- Using `puppygraph/puppygraph:stable` tag
- **Actual version**: 0.111 (or 0.109+)
- **Issue**: Parallelized metadata retrieval introduced in 0.109

### 3. Search Path Configuration
**Parser Branch**:
- Unknown if search_path was configured
- May have worked without explicit configuration due to older PuppyGraph version

**Current Branch**:
- User-level search_path: `ALTER USER postgres SET search_path = aml, public;`
- JDBC parameter: `currentSchema=aml`

## Critical Insight

The parser branch worked because:
1. **It likely used PuppyGraph < 0.109** - Before the parallelized metadata retrieval changes
2. **The older version didn't have the metadata access bug** that affects 0.109+
3. **The `:stable` tag moved** from a working version to a broken version

## Solution Options

### Option 1: Pin to Pre-0.109 Version (Recommended)
Find and use the exact PuppyGraph version that was working in the parser branch:

```yaml
puppygraph:
  image: puppygraph/puppygraph:0.108  # or earlier
```

### Option 2: Remove currentSchema Parameter
Try reverting to the parser branch's JDBC connection string:

```json
"jdbcUri": "jdbc:postgresql://postgres14:5432/demo_data"
```

### Option 3: Test Version Progression
Test versions in reverse order to find when it broke:
- 0.108 (before parallelization)
- 0.107
- 0.106
- etc.

## Next Steps

1. **Determine parser branch PuppyGraph version** - Check git commit dates vs PuppyGraph release dates
2. **Test with PuppyGraph 0.108** - Most likely working version
3. **If 0.108 works, pin to that version** in `compose.yml`
4. **Document the version requirement** for future reference
