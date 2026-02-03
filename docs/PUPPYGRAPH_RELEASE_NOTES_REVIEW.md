# PuppyGraph Release Notes Review

## Current Version
- **Running Version**: 0.111
- **Image Tag**: `puppygraph/puppygraph:stable`
- **Image Created**: 2026-01-14T20:44:44.014938019Z

## Release Notes Availability

### Official Documentation
- **Release Notes URL**: https://docs.puppygraph.com/releases
- **Latest Documented Version**: 0.109 (2026-01-05)
- **Version 0.111 Status**: **NOT DOCUMENTED** in public release notes

### Key Findings from Documented Releases (0.99-0.109)

#### Version 0.109 (2026-01-05) - Most Recent Documented
- **Parallelize table information retrieval** during graph schema initialization to improve performance
- Raise schema JSON size cap to 120 MB
- Various Cypher and Gremlin query fixes

#### Version 0.108 (2025-12-22)
- Fix bugs in credential vending
- Fix parallel graph traversal terminating early in some cases

#### Version 0.107 (2025-12-18)
- Fix empty catalog name error

#### Version 0.106 (2025-12-14)
- Fix Schema Builder duplicate attribute names on ClickHouse data sources
- Fix schema upload failures with long table names

#### Version 0.105 (2025-12-09)
- Improve query profile and health check endpoint stability
- Schema validation enhancements

#### Version 0.102 (2025-11-21)
- Fix timeout issue during schema uploads
- Improved JSON schema file size limit enforcement

#### Version 0.101 (2025-11-15)
- Increase schema JSON file size limit from 1MB to 100MB

## Critical Observations

### Version 0.111 is Undocumented
- Version 0.111 is **newer than the latest documented release** (0.109)
- No public release notes available for 0.111
- This suggests it may be:
  1. A very recent/unreleased development version
  2. A version with release notes not yet published
  3. A version with breaking changes or issues

### Relevant to Our Issue

**Error Code 244**: "can not access data source table attributes:map[]"
- **NOT mentioned** in any documented release notes (0.99-0.109)
- This error occurs during query execution when PuppyGraph attempts to access PostgreSQL table metadata

**Version 0.109 Improvements**:
- **Parallelized table information retrieval** - This change in 0.109 could be related to our metadata access issue
- If 0.111 introduced changes to this parallelization, it could explain the regression

## Critical Finding: Version 0.109 Metadata Fix

**Version 0.109 (2026-01-05)** includes a fix that is highly relevant to our issue:
- **"Parallelize table information retrieval during graph schema initialization to improve performance"**

This change modified how PuppyGraph retrieves table metadata. If version 0.111 introduced a regression or breaking change to this parallelization, it could explain why:
1. The parser branch (likely using an earlier version) worked
2. The current setup (0.111) fails with metadata access errors

## Recommendations

1. **Test with Version 0.109**: Since 0.109 is the latest documented stable release and includes metadata retrieval improvements, test if downgrading resolves the issue:
   ```yaml
   image: puppygraph/puppygraph:0.109
   ```

2. **Check for Version-Specific Issues**: Since 0.111 is undocumented, it may contain:
   - Breaking changes to the parallelized metadata retrieval
   - Regressions in metadata access
   - Unstable features or development code

3. **Contact PuppyGraph Support**: Report:
   - Version: 0.111 (undocumented)
   - Error Code: 244
   - Error Message: "can not access data source table attributes:map[]"
   - That the same schema works on an earlier version (parser branch)
   - That version 0.109 introduced parallelized metadata retrieval which may have regressed in 0.111

4. **Pin to Specific Version**: Instead of using `:stable`, pin to a known working version:
   ```yaml
   image: puppygraph/puppygraph:0.109  # Latest documented stable version
   ```

## Next Steps

1. Test with PuppyGraph 0.109 to see if the issue is version-specific
2. Check PuppyGraph GitHub repository for any issues or discussions about version 0.111
3. Document findings if downgrading resolves the issue
4. Consider pinning to a specific version rather than using the `:stable` tag
