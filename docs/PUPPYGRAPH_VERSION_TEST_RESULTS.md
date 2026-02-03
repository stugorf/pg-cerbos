# PuppyGraph Version 0.109 Test Results

## Test Configuration
- **Previous Version**: 0.111 (undocumented, from `:stable` tag)
- **Test Version**: 0.109 (latest documented stable release)
- **Date**: $(date)

## Test Plan
1. Update `compose.yml` to use `puppygraph/puppygraph:0.109`
2. Remove existing PuppyGraph container and data volume
3. Pull and start PuppyGraph 0.109
4. Verify version is 0.109
5. Test vertex query (Customer)
6. Test edge query (Customer-OWNS-Account)
7. Document results

## Results

### Version Verification
- ✅ Successfully pulled and started PuppyGraph 0.109
- ✅ Confirmed version: `puppygraph-core-0.109.jar` (Jan 6 07:50)
- ✅ Container is running and healthy

### Test Results

#### Vertex Query Test
**Query**: `MATCH (c:Customer) RETURN c.name AS name LIMIT 1`
**Result**: ❌ **FAILED**
**Error**: Same error code 244 - "can not access data source table attributes:map[]"

#### Edge Query Test  
**Query**: `MATCH (c:Customer)-[r:OWNS]->(a:Account) RETURN c.name, a.account_id LIMIT 1`
**Result**: ❌ **FAILED**
**Error**: Same error code 244 - "can not access data source table attributes:map[]"

## Critical Finding

**The error persists in version 0.109**, which means:
1. ❌ **NOT a version-specific issue** - The problem exists in both 0.109 and 0.111
2. ❌ **NOT a regression in 0.111** - The issue predates 0.111
3. ✅ **Parser branch likely used an earlier version** - Possibly 0.108 or earlier that didn't have this issue
4. ✅ **The parallelization changes in 0.109 may have introduced the bug** - Since 0.109 added "parallelize table information retrieval", this could be the source

## Next Steps

1. **Test with version 0.108** (before parallelization changes) to confirm if that's when the issue was introduced
2. **Check parser branch commit history** to determine what PuppyGraph version was actually used when it worked
3. **Consider testing with version 0.107 or earlier** if 0.108 also fails
4. **Contact PuppyGraph support** with findings that the issue exists in both 0.109 and 0.111, suggesting it was introduced in 0.109's parallelization changes
