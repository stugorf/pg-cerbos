# Phase 3: CEL Evaluation Investigation - Team Mismatch DENY Rule

## Issue Summary

**Test:** "Team A analyst cannot query Team B customers"  
**Expected:** `EFFECT_DENY`  
**Actual:** `EFFECT_ALLOW`  
**Status:** Failing (1 of 16 tests)

## Test Data Analysis

### Principal: `analyst_team_a`
```yaml
id: "5"
roles: ["aml_analyst_junior"]
attr:
  email: "analyst.junior@pg-cerbos.com"
  team: "Team A"  # Explicit string value
  clearance_level: 1
  region: "US"
  is_active: true
```

### Resource: `team_b_customer_query`
```yaml
kind: "cypher_query"
id: "query-abac-002"
attr:
  query_type: "cypher"
  query: "MATCH (c:Customer {team: 'Team B'}) RETURN c"
  node_labels: ["Customer"]  # Contains "Customer"
  relationship_types: []
  max_depth: 1
  customer_team: "Team B"  # Explicit string value
```

## DENY Rule 7a Condition Analysis

### Current Condition:
```yaml
R.attr.node_labels.contains("Customer") &&
R.attr.customer_team != null &&
R.attr.customer_team != "" &&
P.attr.team != null &&
P.attr.team != "" &&
P.attr.team != R.attr.customer_team
```

### Expected Evaluation:
1. ✅ `R.attr.node_labels.contains("Customer")` → `true` (Customer is in node_labels)
2. ✅ `R.attr.customer_team != null` → `true` ("Team B" is not null)
3. ✅ `R.attr.customer_team != ""` → `true` ("Team B" is not empty)
4. ✅ `P.attr.team != null` → `true` ("Team A" is not null)
5. ✅ `P.attr.team != ""` → `true` ("Team A" is not empty)
6. ✅ `P.attr.team != R.attr.customer_team` → `true` ("Team A" != "Team B")

**Expected Result:** All conditions true → DENY rule should match → `EFFECT_DENY`

**Actual Result:** DENY rule not matching → ALLOW rule matching → `EFFECT_ALLOW`

## ALLOW Rule 3 Analysis

### Rule 3 Condition:
```yaml
R.attr.max_depth <= 2 &&
size(R.attr.node_labels.filter(l, l == "SAR")) == 0
```

### Evaluation:
1. ✅ `R.attr.max_depth <= 2` → `true` (max_depth: 1)
2. ✅ `size(R.attr.node_labels.filter(l, l == "SAR")) == 0` → `true` (no SAR nodes)

**Result:** Rule 3 matches → `EFFECT_ALLOW`

## Hypothesis: CEL String Comparison Issue

### Hypothesis 1: String Comparison Not Working
The condition `P.attr.team != R.attr.customer_team` might not be evaluating correctly in CEL.

**Test:** Try explicit string conversion:
```yaml
string(P.attr.team) != string(R.attr.customer_team)
```

### Hypothesis 2: Array Contains Issue
The condition `R.attr.node_labels.contains("Customer")` might be evaluating incorrectly.

**Test:** Try alternative syntax:
```yaml
size(R.attr.node_labels.filter(l, l == "Customer")) > 0
```

### Hypothesis 3: Short-Circuit Evaluation
CEL might be short-circuiting the condition evaluation incorrectly.

**Test:** Break condition into smaller parts or use parentheses.

### Hypothesis 4: Rule Evaluation Order
DENY rules should be evaluated first, but maybe there's an issue with how Cerbos evaluates conditions.

**Test:** Check if DENY rule is actually being evaluated.

## Investigation Plan

### Step 1: Simplify DENY Rule Condition
Test with a minimal condition to see if the rule matches at all.

### Step 2: Test Individual Condition Parts
Test each part of the condition separately to identify which part is failing.

### Step 3: Try Alternative CEL Syntax
Test alternative CEL expressions for string comparison and array operations.

### Step 4: Check Cerbos Logs
If possible, check Cerbos evaluation logs to see which rules are being evaluated.

### Step 5: Test with Direct Cerbos API
Test the condition directly via Cerbos API to see the actual evaluation.

## Potential Solutions

### Solution 1: Use Explicit String Conversion
```yaml
string(P.attr.team) != string(R.attr.customer_team)
```

### Solution 2: Use Alternative Array Check
```yaml
size(R.attr.node_labels.filter(l, l == "Customer")) > 0
```

### Solution 3: Break Condition into Smaller Parts
```yaml
R.attr.node_labels.contains("Customer") &&
R.attr.customer_team != null &&
R.attr.customer_team != "" &&
P.attr.team != null &&
P.attr.team != "" &&
!(P.attr.team == R.attr.customer_team)
```

### Solution 4: Add Explicit Type Checks
```yaml
type(R.attr.customer_team) == string &&
type(P.attr.team) == string &&
P.attr.team != R.attr.customer_team
```

### Solution 5: Make ALLOW Rule More Restrictive (Not Recommended)
Add team check to Rule 3, but this would break RBAC tests.

## Next Steps

1. Test simplified DENY rule condition
2. Test alternative CEL syntax
3. Verify rule evaluation order
4. Check if this is a known Cerbos/CEL issue
5. Consider filing a bug report if confirmed
