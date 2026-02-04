# Phase 2 Schema Validation Fix - Investigation and Resolution

## Issue Summary

When schema validation was enabled in the `cypher_query.yaml` policy, 10 tests were failing with `EFFECT_DENY` instead of `EFFECT_ALLOW`, even for admin and manager roles that had no conditions.

## Root Cause

The validation error was: `[P.attr[/]: missing properties: 'id', 'roles']`

**Problem**: The `aml_principal.json` schema incorrectly included `id` and `roles` as required properties in the schema. However, in Cerbos:
- `id` and `roles` are **top-level principal fields**, not attributes
- The `principalSchema` validates the `P.attr` object (attributes), not the entire principal
- Therefore, `id` and `roles` should NOT be in the schema

## Solution

Updated `aml_principal.json` to:
1. Remove `id` and `roles` from the schema (they're validated separately by Cerbos)
2. Only validate the `attr` object properties: `email`, `team`, `is_active`
3. Add `additionalProperties: true` to allow other attributes

## Verification

After fixing the schema:
- ✅ All 16 tests pass with schema validation enabled
- ✅ Schema validation now correctly validates only the `attr` object
- ✅ Test resources match the schema requirements

## Test Coverage Analysis

### All 16 Tests Are Necessary

The test suite covers:

1. **Admin Tests (2 tests)** - Verify full access
   - Simple customer query
   - SAR query (sensitive data)

2. **Manager Tests (1 test)** - Verify full access
   - Simple customer query

3. **Junior Analyst Tests (8 tests)** - Verify restricted access
   - ✅ Can execute simple customer query
   - ✅ Can execute 2-hop query
   - ❌ Cannot execute 3-hop query (depth limit)
   - ❌ Cannot execute SAR query (sensitive node)
   - ❌ Cannot execute Case query (restricted node)
   - ❌ Cannot execute FLAGS_CUSTOMER relationship (restricted relationship)
   - ❌ Cannot execute FROM_ALERT relationship (restricted relationship)

4. **Senior Analyst Tests (5 tests)** - Verify extended access
   - ✅ Can execute 2-hop query (inherits from junior)
   - ✅ Can execute 4-hop query (senior limit)
   - ❌ Cannot execute SAR query (still restricted)
   - ✅ Can execute Case query (allowed for senior)
   - ✅ Can execute FLAGS_CUSTOMER relationship (allowed for senior)
   - ✅ Can execute FROM_ALERT relationship (allowed for senior)

### Rule Necessity

All rules in the policy are necessary:

1. **Rule 1: Admin ALLOW** - Required for admin full access
2. **Rule 2: Manager ALLOW** - Required for manager full access
3. **Rule 4a: DENY Case/Alert for junior** - Required to block Case/Alert nodes for junior analysts
4. **Rule 4b: DENY sensitive relationships for junior** - Required to block FLAGS_CUSTOMER, FLAGS_ACCOUNT, FROM_ALERT for junior analysts
5. **Rule 3: Junior Analyst ALLOW** - Required for junior analyst basic access (with constraints)
6. **Rule 5: Senior Analyst ALLOW** - Required for senior analyst extended access
7. **Rule 6: Base Analyst ALLOW** - Required as fallback for `aml_analyst` role without derived roles

## Key Findings

1. **Schema Validation Issue**: The principal schema was incorrectly structured - it should only validate `P.attr`, not top-level fields like `id` and `roles`.

2. **Test Resources Match Schema**: After fixing the schema, all test resources correctly match the schema requirements. The resources were always correct; the schema was wrong.

3. **All Tests and Rules Are Necessary**: The 16 tests provide comprehensive coverage of:
   - Role-based access (admin, manager, junior, senior)
   - Depth restrictions (2 hops for junior, 4 hops for senior)
   - Node restrictions (SAR blocked for all analysts, Case/Alert blocked for junior)
   - Relationship restrictions (sensitive relationships blocked for junior)

4. **Schema Validation Should Be Enabled**: With the corrected schema, validation works correctly and provides valuable type checking and validation of attributes.

## Recommendation

✅ **Enable schema validation** - It now works correctly and provides valuable validation
✅ **Keep all 16 tests** - They provide comprehensive coverage
✅ **Keep all 7 rules** - Each rule serves a specific purpose in the authorization model
