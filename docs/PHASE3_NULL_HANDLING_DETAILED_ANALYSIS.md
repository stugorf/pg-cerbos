# Phase 3: Null Handling Edge Cases - Detailed Analysis

## Executive Summary

**Issue:** 3 out of 16 ABAC tests are failing due to null handling inconsistencies between:
1. **Test YAML files** (explicitly set `team: null`)
2. **Runtime behavior** (Python code excludes `None` values)
3. **CEL expression evaluation** (how Cerbos handles missing vs. null attributes)

**Root Cause:** Mismatch between how null values are represented in test data vs. how they're handled at runtime, combined with CEL's behavior when checking for null/missing attributes.

**RBAC Status:** RBAC tests don't use null values, so this issue didn't appear in Phase 2.

---

## The Three Failing Tests

### Test 1: "Team A analyst cannot query Team B customers"
**Expected:** `EFFECT_DENY`  
**Actual:** `EFFECT_ALLOW`  
**Test Data:**
```yaml
analyst_team_a:
  attr:
    team: "Team A"  # Explicit string value

team_b_customer_query:
  attr:
    customer_team: "Team B"  # Explicit string value
```

**Problem:** The DENY rule (Rule 7a) should match when `P.attr.team != R.attr.customer_team`, but it's not matching. An ALLOW rule (likely Rule 3 for junior analysts) is matching first.

**DENY Rule Condition:**
```yaml
R.attr.node_labels.contains("Customer") &&
type(R.attr.customer_team) == string &&
R.attr.customer_team != "" &&
type(P.attr.team) == string &&
P.attr.team != "" &&
P.attr.team != R.attr.customer_team
```

**Analysis:** All conditions should be true:
- ✅ `R.attr.node_labels.contains("Customer")` - true (Customer in labels)
- ✅ `type(R.attr.customer_team) == string` - true ("Team B" is a string)
- ✅ `R.attr.customer_team != ""` - true ("Team B" is not empty)
- ✅ `type(P.attr.team) == string` - true ("Team A" is a string)
- ✅ `P.attr.team != ""` - true ("Team A" is not empty)
- ✅ `P.attr.team != R.attr.customer_team` - true ("Team A" != "Team B")

**Why it's failing:** The DENY rule should match, but an ALLOW rule (Rule 3: Junior Analyst basic allow) is matching first because it doesn't check for team restrictions. Rule 3 only checks:
```yaml
R.attr.max_depth <= 2 &&
size(R.attr.node_labels.filter(l, l == "SAR")) == 0
```

Since the query has `max_depth: 1` and no SAR nodes, Rule 3 matches and allows the query **before** the DENY rule can take effect.

**Note:** In Cerbos, DENY rules are evaluated first, but if a DENY rule's condition doesn't match (returns false), Cerbos continues to ALLOW rules. The issue is that Rule 7a's condition might not be matching correctly, or there's a logic error.

---

### Test 2: "User with no team can query any team's customers"
**Expected:** `EFFECT_ALLOW`  
**Actual:** `EFFECT_DENY`  
**Test Data:**
```yaml
analyst_no_team:
  attr:
    team: null  # Explicitly set to null in YAML

team_a_customer_query:
  attr:
    customer_team: "Team A"  # Explicit string value
```

**Problem:** The DENY rule (Rule 7a) is matching when it shouldn't. When `P.attr.team` is `null`, the DENY rule should not match because the condition checks `type(P.attr.team) == string`, which should be false for null.

**DENY Rule Condition:**
```yaml
type(P.attr.team) == string &&  # Should be FALSE when team is null
```

**Analysis:** 
- In test YAML: `team: null` is explicitly set
- In CEL: `type(null) == string` should return `false`
- Therefore: The DENY rule condition should be false (short-circuit), and the rule shouldn't match

**Why it's failing:** There are two possibilities:

1. **CEL type() behavior with null:** The `type()` function might not work as expected with null values. In CEL, `type(null)` might return a different type than expected, or the comparison might behave unexpectedly.

2. **Test YAML vs Runtime mismatch:** 
   - In test YAML: `team: null` is explicitly set
   - At runtime: Python code skips `None` values, so the attribute is **missing** (not null)
   - CEL might handle missing attributes differently than null attributes
   - `type(P.attr.team)` on a missing attribute might throw an error or return an unexpected value

**Expected Behavior:**
- When `team: null` in YAML → DENY rule should NOT match → ALLOW rule should match → `EFFECT_ALLOW`
- ALLOW Rule 7 condition: `(R.attr.customer_team == null || P.attr.team == null || P.attr.team == R.attr.customer_team)`
- Since `P.attr.team == null` is true, the ALLOW rule should match

---

### Test 3: "User with no region can query any region's customers"
**Expected:** `EFFECT_ALLOW`  
**Actual:** `EFFECT_DENY`  
**Test Data:**
```yaml
analyst_no_region:
  attr:
    region: null  # Explicitly set to null in YAML

eu_customer_query:
  attr:
    customer_region: "EU"  # Explicit string value
```

**Problem:** Same as Test 2, but for region instead of team. The DENY rule (Rule 10a) is matching when it shouldn't.

**DENY Rule Condition:**
```yaml
type(P.attr.region) == string &&  # Should be FALSE when region is null
```

**Analysis:** Same root cause as Test 2 - `type(null) == string` should be false, but the DENY rule is still matching.

---

## Root Cause Analysis

### 1. Test YAML vs Runtime Behavior Mismatch

**In Test YAML:**
```yaml
analyst_no_team:
  attr:
    team: null  # Explicitly set to null
```

**At Runtime (Python code):**
```python
if val is None:
    continue  # Skip None values - attribute is MISSING, not null
```

**Impact:**
- Test YAML: Attribute exists with value `null`
- Runtime: Attribute doesn't exist (missing)
- CEL might handle these differently:
  - `P.attr.team == null` when attribute is missing → might be true or might error
  - `type(P.attr.team)` when attribute is missing → might error or return unexpected type

### 2. CEL Null Handling Behavior

CEL (Common Expression Language) has specific behavior for null values:

1. **Missing attributes:** When an attribute doesn't exist, accessing it might:
   - Return `null`
   - Throw an error
   - Return an undefined value

2. **Explicit null:** When an attribute is explicitly set to `null`:
   - `P.attr.team == null` → `true`
   - `type(P.attr.team)` → might return `null_type` or error

3. **Type checking with null:**
   - `type(null) == string` → should be `false`
   - But CEL might have edge cases

### 3. Rule Evaluation Order

In Cerbos:
1. **DENY rules are evaluated first**
2. If a DENY rule's condition matches → `EFFECT_DENY` (immediate return)
3. If no DENY rules match → evaluate ALLOW rules
4. If an ALLOW rule matches → `EFFECT_ALLOW`
5. If no rules match → `EFFECT_DENY` (default deny)

**The Problem:**
- Rule 7a (DENY) condition might not be matching correctly due to null handling
- Rule 3 (ALLOW for junior analysts) doesn't check team restrictions
- Rule 3 matches → `EFFECT_ALLOW` (even though teams don't match)

---

## Was Null Handling Fixed in RBAC Work?

### Short Answer: **No, because RBAC didn't use null values**

### Detailed Answer:

**Phase 2 (RBAC) Tests:**
- ✅ All 16 RBAC tests pass
- ✅ RBAC tests don't use null values
- ✅ RBAC tests only use explicit string values for attributes

**Example from RBAC test suite:**
```yaml
analyst_junior:
  attr:
    email: "analyst.junior@pg-cerbos.com"
    is_active: true
    # No team, region, or clearance_level attributes
```

**RBAC DENY Rules:**
```yaml
# Rule 4a: DENY Case/Alert nodes
size(R.attr.node_labels.filter(l, l == "Case")) > 0 ||
size(R.attr.node_labels.filter(l, l == "Alert")) > 0

# Rule 4b: DENY sensitive relationships
size(R.attr.relationship_types.filter(r, r == "FLAGS_CUSTOMER")) > 0 ||
...
```

**Key Differences:**
1. **RBAC rules don't check for null:** They only check for presence of specific values (node labels, relationship types)
2. **RBAC tests don't set null:** All attributes are either present with values or completely absent
3. **RBAC doesn't have "allow if null" logic:** No rules check `P.attr.team == null` to allow access

**Why ABAC is Different:**
1. **ABAC needs null handling:** Rules like "allow if user has no team" require checking for null
2. **ABAC tests use explicit null:** Test suite sets `team: null` to test edge cases
3. **ABAC has "allow if null" logic:** Rule 7 allows access when `P.attr.team == null`

---

## Current Understanding

### What We Know

1. **Python code fix is correct:** Skipping `None` values at runtime is the right approach
   - This ensures consistent behavior: missing attributes are treated as null
   - Allows CEL to properly evaluate `P.attr.team == null`

2. **Test YAML uses explicit null:** This creates a mismatch
   - Test: `team: null` (attribute exists, value is null)
   - Runtime: attribute missing (attribute doesn't exist)
   - CEL might handle these differently

3. **DENY rule logic is sound:** The condition should work
   - `type(P.attr.team) == string` should be false when team is null
   - But it might not be working as expected

4. **ALLOW rule logic is correct:** Rule 7 should allow when team is null
   - `P.attr.team == null` should be true
   - But DENY rule might be blocking it first

### What We Don't Know

1. **How CEL handles `type(null)`:**
   - Does `type(null) == string` return `false`?
   - Does it throw an error?
   - Does it return a different type?

2. **How CEL handles missing attributes:**
   - Does `P.attr.team` return `null` when missing?
   - Does `type(P.attr.team)` work on missing attributes?
   - Is there a difference between missing and null?

3. **Why DENY rule isn't matching in Test 1:**
   - All conditions should be true
   - But the rule isn't matching
   - Is there a CEL evaluation issue?

### Hypotheses

1. **Hypothesis 1: CEL type() function issue**
   - `type(null)` might not work as expected
   - Might need to use `P.attr.team != null` instead of `type(P.attr.team) == string`

2. **Hypothesis 2: Test YAML null vs Runtime missing**
   - Test YAML: `team: null` (explicit null)
   - Runtime: attribute missing
   - CEL might handle these differently
   - Solution: Update test YAML to omit the attribute instead of setting it to null

3. **Hypothesis 3: Rule evaluation order**
   - DENY rule condition might be evaluating incorrectly
   - ALLOW rule might be matching first
   - Solution: Make ALLOW rules more restrictive (but this breaks RBAC tests)

---

## Potential Solutions

### Solution 1: Update Test YAML to Match Runtime Behavior
**Change:**
```yaml
# Instead of:
analyst_no_team:
  attr:
    team: null

# Use:
analyst_no_team:
  attr:
    # team attribute omitted (missing, not null)
```

**Pros:**
- Matches runtime behavior
- Tests actual production behavior

**Cons:**
- Might not test explicit null values
- YAML might require all attributes to be present

### Solution 2: Update Python Code to Include Null Values
**Change:**
```python
# Instead of skipping None:
if val is None:
    continue

# Include null explicitly:
if val is None:
    principal_attr[key] = Value(null_value=...)  # If Cerbos supports this
```

**Pros:**
- Matches test YAML behavior
- Tests explicit null handling

**Cons:**
- Cerbos protobuf might not support explicit null values
- Might require different handling

### Solution 3: Fix DENY Rule Conditions
**Change:**
```yaml
# Instead of:
type(P.attr.team) == string &&

# Use:
P.attr.team != null &&
P.attr.team != "" &&
```

**Pros:**
- Simpler condition
- More explicit null checking

**Cons:**
- Might not work if attribute is missing (not null)
- Need to handle missing vs null

### Solution 4: Use CEL has() Function (If Available)
**Change:**
```yaml
# Use:
has(P.attr.team) &&
P.attr.team != null &&
P.attr.team != "" &&
```

**Pros:**
- Explicitly checks for attribute existence
- Handles both missing and null

**Cons:**
- `has()` might not be available in CEL
- Need to verify Cerbos/CEL version support

---

## Recommendations

### Immediate Actions

1. **Document the issue clearly** ✅ (Done)
2. **Test with actual Cerbos API** to verify behavior
3. **Check Cerbos/CEL documentation** for null handling best practices
4. **Consider updating test YAML** to omit attributes instead of setting null

### Long-term Actions

1. **Monitor Cerbos updates** for better null handling
2. **Consider application-level validation** for edge cases
3. **Update documentation** with null handling patterns
4. **Create integration tests** that match runtime behavior

---

## References

- [Cerbos CEL Documentation](https://docs.cerbos.dev/cerbos/latest/policies/conditions.html)
- [CEL Language Definition](https://github.com/google/cel-spec)
- [Phase 3 Testing Status](./PHASE3_TESTING_STATUS.md)
- [Phase 3 Null Handling Issues](./PHASE3_NULL_HANDLING_ISSUES.md)
