# PuppyGraph Release Notes - Schema Validation Insights

## Current Status
- **Running Version**: 0.108
- **Issue**: Error 244 - "can not access data source table attributes:map[]"
- **Schema Format**: ✅ Now using correct `mappedTableSource` format (8 edges, 0 old format)

## Critical Release Notes Findings

### Version 0.109 (2026-01-05) - Parallelization Change
**Key Change:**
> "Parallelize table information retrieval during graph schema initialization to improve performance"

**Analysis:**
This parallelization change in 0.109 **may have introduced or exacerbated** the error 244 issue. The parallelized metadata retrieval could be:
- Causing race conditions when accessing PostgreSQL `information_schema`
- Having issues with connection pooling during parallel queries
- Not properly handling schema search paths in parallel contexts

**Relevance to Our Issue:**
- We're on 0.108 (before this change)
- Error 244 occurs during metadata access
- This suggests the issue may be **worse in 0.109+** or was introduced there

### Version 0.110+ - Validation Improvements
According to recommendations, version 0.110.0+ addressed:
- Issues where schema validation might silently accept invalid schemas
- Added detailed warnings for missing logical partition columns

**Potential**: Version 0.110+ may have improved validation logic, but we need to check if it fixes error 244.

### Version 0.105 (2025-12-09) - Schema Validation Enhancements
**Key Change:**
> "Schema validation enhancements"

**Analysis:**
This version specifically mentions schema validation improvements, which could be relevant to our issue.

### Version 0.57 (2025-02-07) - Schema Installation Fix
**Key Change:**
> "Fix an unable to install schema issue"

**Analysis:**
This suggests there have been historical issues with schema installation/validation that required fixes.

## Version Comparison Strategy

### Option 1: Test Version 0.105 (Has Validation Enhancements)
**Rationale**: Version 0.105 specifically mentions "Schema validation enhancements"

**Action**:
```yaml
# In compose.yml
image: puppygraph/puppygraph:0.105
```

**Risk**: Lower - it's a documented stable version with validation improvements

### Option 2: Test Version 0.110+ (Improved Validation)
**Rationale**: Version 0.110+ has improved validation with detailed warnings

**Action**:
```yaml
image: puppygraph/puppygraph:0.110
# or
image: puppygraph/puppygraph:0.111
# or
image: puppygraph/puppygraph:0.112
```

**Risk**: Medium - newer versions may have different behavior

### Option 3: Stay on 0.108 and Work Around
**Rationale**: 0.108 is before parallelization changes that may have introduced issues

**Action**: 
- Document validation bug
- Test if actual queries work
- Use Bolt protocol directly if needed

## Schema Format Compliance (Current Status)

Based on release notes context and our fixes:

✅ **All edges use `mappedTableSource` format** (8 edges, 0 old format)
✅ **All `metaFields` reference existing columns**
✅ **Edge IDs are string type** (per documentation requirement)
✅ **All column names match database exactly**

## Key Insights from Release Notes

### 1. Parallelization May Be the Issue
Version 0.109's parallelization of metadata retrieval could be causing error 244. Since we're on 0.108, this suggests:
- The issue exists in 0.108's validation logic
- It may be worse in 0.109+ due to parallelization
- We should test if staying on 0.108 and fixing schema format resolves it

### 2. Validation Has Been Problematic
Multiple versions (0.57, 0.105, 0.110+) have had validation-related fixes, suggesting:
- Validation logic has had ongoing issues
- Different versions may have different validation behavior
- Error 244 may be a known issue that's been partially addressed

### 3. Schema Format Matters
Release notes don't explicitly mention edge format changes, but:
- Our schema now matches official documentation format
- This should be the correct format for all versions
- Format compliance may be necessary but not sufficient to fix error 244

## Recommended Testing Strategy

### Phase 1: Verify Current Schema Format
✅ **COMPLETE** - All edges now use correct `mappedTableSource` format

### Phase 2: Test with Current Version (0.108)
1. Restart PuppyGraph with corrected schema
2. Test validation
3. If still fails, test actual queries to see if they work

### Phase 3: Test with Version 0.105 (If Needed)
If 0.108 still fails, test with 0.105 which has "Schema validation enhancements":
```yaml
image: puppygraph/puppygraph:0.105
```

### Phase 4: Test with Version 0.110+ (If Needed)
If needed, test with 0.110+ which has improved validation:
```yaml
image: puppygraph/puppygraph:0.110
```

## Conclusion

Based on release notes analysis:

1. **Schema format is now correct** - We've fixed all edge definitions to match official format
2. **Error 244 may be version-specific** - Multiple versions have had validation fixes
3. **Version 0.105 has validation enhancements** - Worth testing if 0.108 still fails
4. **Version 0.109+ introduced parallelization** - May have different behavior

**Next Step**: Test validation with the corrected schema format. If it still fails, consider testing with version 0.105 (validation enhancements) or 0.110+ (improved validation).

## References

- [PuppyGraph Releases](https://docs.puppygraph.com/releases/)
- Version 0.108 (2025-12-22) - Current version
- Version 0.105 (2025-12-09) - Schema validation enhancements
- Version 0.109 (2026-01-05) - Parallelized metadata retrieval
- Version 0.110+ - Improved validation (per recommendations)
