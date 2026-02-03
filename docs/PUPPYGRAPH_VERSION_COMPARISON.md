# PuppyGraph Version Comparison

## Current Setup
- **Docker Image**: `puppygraph/puppygraph:stable`
- **Actual Version**: `0.111` (confirmed via `puppygraph-core-0.111.jar` in container)
- **Image Digest**: `sha256:fbc3c16928ad1d5b3c441a4dd5db634c97b4453ac85a1d9c9a414b0f9b1661ae`
- **Image Created**: `2026-01-14T20:44:44.014938019Z`

## Parser Branch
- **Docker Image**: `puppygraph/puppygraph:stable` (same tag)
- **Version**: Unknown (needs verification)

## Critical Finding

**Both branches use the `:stable` tag**, which is a **floating tag** that can point to different versions over time. This means:

1. **The parser branch may have been using a different version** when it was working
2. **The `:stable` tag may have been updated** between when the parser branch worked and now
3. **The current `:stable` tag points to version 0.111** (confirmed)

## Recommendation

Since the `:stable` tag is a moving target, we should:

1. **Check if the parser branch has any version-specific configuration** or documentation
2. **Consider pinning to a specific version** instead of using `:stable`
3. **Test with the exact version that was working** on the parser branch (if we can determine it)
4. **Check PuppyGraph release notes** for version 0.111 to see if there are known issues with PostgreSQL metadata access

## Next Steps

1. Check git history to see if there were any version changes
2. Look for any version-specific configuration in the parser branch
3. Consider testing with a different PuppyGraph version to see if the issue is version-specific
4. Contact PuppyGraph support with version information if needed
