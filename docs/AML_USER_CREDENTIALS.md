# AML User Credentials Reference

This document lists all AML (Anti-Money Laundering) users available for testing Cerbos authorization policies.

## All Users Use Password: `user123`

## AML Users

### 1. Junior Analyst
- **Email:** `analyst.junior@pg-cerbos.com`
- **Password:** `user123`
- **Roles:** `aml_analyst`, `aml_analyst_junior`
- **Team:** Team A
- **Region:** US
- **Clearance Level:** 1 (low)
- **Department:** AML

**Access Restrictions:**
- Max query depth: 2 hops
- Cannot access: Case nodes, Alert nodes, SAR nodes
- Cannot use: FLAGS_CUSTOMER, FLAGS_ACCOUNT, FROM_ALERT relationships
- Cannot query: Team B customers, EU customers, PEP customers, transactions > $100k

**Use Case:** Demonstrates basic restrictions for junior analysts

---

### 2. Senior Analyst
- **Email:** `analyst.senior@pg-cerbos.com`
- **Password:** `user123`
- **Roles:** `aml_analyst`, `aml_analyst_senior`
- **Team:** Team B
- **Region:** EU
- **Clearance Level:** 2 (medium)
- **Department:** AML

**Access Restrictions:**
- Max query depth: 4 hops
- Cannot access: SAR nodes
- Cannot query: Team A customers, US customers, PEP customers, transactions > $500k

**Use Case:** Demonstrates extended access for senior analysts

---

### 3. Regular Analyst
- **Email:** `analyst@pg-cerbos.com`
- **Password:** `user123`
- **Roles:** `aml_analyst`
- **Team:** None (unassigned)
- **Region:** US
- **Clearance Level:** 1 (low)
- **Department:** AML

**Access Restrictions:**
- Max query depth: 2 hops
- Cannot access: Case nodes, Alert nodes, SAR nodes
- Cannot use: FLAGS_CUSTOMER, FLAGS_ACCOUNT, FROM_ALERT relationships
- Cannot query: PEP customers, transactions > $100k

**Use Case:** Demonstrates fallback access for base aml_analyst role

---

### 4. High Clearance Team A Analyst
- **Email:** `analyst.team_a.high@pg-cerbos.com`
- **Password:** `user123`
- **Roles:** `aml_analyst`, `aml_analyst_senior`
- **Team:** Team A
- **Region:** US
- **Clearance Level:** 3 (high)
- **Department:** AML

**Access Restrictions:**
- Max query depth: 4 hops
- Cannot access: SAR nodes
- Cannot query: Team B customers, EU customers

**Use Case:** Demonstrates high clearance access (can query PEP customers and high-value transactions)

---

### 5. AML Manager
- **Email:** `manager@pg-cerbos.com`
- **Password:** `user123`
- **Roles:** `aml_manager`
- **Team:** None (unrestricted)
- **Region:** None (unrestricted)
- **Clearance Level:** 4 (very high)
- **Department:** AML

**Access Restrictions:**
- None - Full access to all queries

**Use Case:** Demonstrates unrestricted manager access

---

## Quick Reference for Testing Denials

**Access Control Types:**
- **RBAC (Role-Based Access Control):** Decisions based solely on user roles (e.g., `aml_analyst_junior`, `aml_manager`)
- **ABAC (Attribute-Based Access Control):** Decisions based on user or resource attributes (e.g., `team`, `region`, `clearance_level`)
- **Both RBAC and ABAC:** Decisions that require both a specific role AND attribute checks

### Test Case Node Access Denial
**User:** `analyst.junior@pg-cerbos.com`  
**Query:**
```cypher
MATCH (c:Case)
RETURN c.case_id, c.status
LIMIT 10
```
**Expected:** Denied by Rule 4a (junior analysts cannot access Case nodes)  
**Access Control Type:** **RBAC** - Decision based solely on role (`aml_analyst_junior`)

---

### Test Alert Node Access Denial
**User:** `analyst.junior@pg-cerbos.com`  
**Query:**
```cypher
MATCH (alert:Alert)
RETURN alert.alert_id, alert.alert_type
LIMIT 10
```
**Expected:** Denied by Rule 4a (junior analysts cannot access Alert nodes)  
**Access Control Type:** **RBAC** - Decision based solely on role (`aml_analyst_junior`)

---

### Test Team Mismatch Denial
**User:** `analyst.junior@pg-cerbos.com` (Team A)  
**Query:**
```cypher
MATCH (cust:Customer {team: 'Team B'})
RETURN cust.customer_id, cust.name
LIMIT 10
```
**Expected:** Denied by Rule 7a (team mismatch)  
**Access Control Type:** **Both RBAC and ABAC** - Requires role (`aml_analyst`, `aml_analyst_junior`, or `aml_analyst_senior`) AND compares user's team attribute (Team A) with customer's team attribute (Team B)

---

### Test Region Mismatch Denial
**User:** `analyst.junior@pg-cerbos.com` (US region)  
**Query:**
```cypher
MATCH (cust:Customer {region: 'EU'})
RETURN cust.customer_id, cust.name
LIMIT 10
```
**Expected:** Denied by Rule 10a (region mismatch)  
**Access Control Type:** **Both RBAC and ABAC** - Requires role (`aml_analyst`, `aml_analyst_junior`, or `aml_analyst_senior`) AND compares user's region attribute (US) with customer's region attribute (EU)

---

### Test PEP Access Denial (Low Clearance)
**User:** `analyst.junior@pg-cerbos.com` (clearance level 1)  
**Query:**
```cypher
MATCH (cust:Customer)
WHERE cust.pep_flag = true
RETURN cust.customer_id, cust.name
LIMIT 10
```
**Expected:** Denied by Rule 8a (requires clearance >= 3)  
**Access Control Type:** **Both RBAC and ABAC** - Requires role (`aml_analyst`, `aml_analyst_junior`, or `aml_analyst_senior`) AND checks user's clearance_level attribute (1 < 3)

---

### Test High-Value Transaction Denial (Low Clearance)
**User:** `analyst.junior@pg-cerbos.com` (clearance level 1)  
**Query:**
```cypher
MATCH (txn:Transaction)
WHERE txn.amount > 100000
RETURN txn.txn_id, txn.amount
LIMIT 10
```
**Expected:** Denied by Rule 9a (requires clearance >= 2 for transactions > $100k)  
**Access Control Type:** **Both RBAC and ABAC** - Requires role (`aml_analyst`, `aml_analyst_junior`, or `aml_analyst_senior`) AND checks user's clearance_level attribute (1 < 2) against transaction amount threshold

---

### Test Query Depth Denial
**User:** `analyst.junior@pg-cerbos.com` (max depth 2)  
**Query:**
```cypher
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn1:Transaction)-[:TO_ACCOUNT]->(acc2:Account)-[:SENT_TXN]->(txn2:Transaction)-[:TO_ACCOUNT]->(acc3:Account)
RETURN c1.name, txn1.amount, txn2.amount
LIMIT 10
```
**Expected:** Denied by Rule 3 (exceeds max_depth of 2)  
**Access Control Type:** **RBAC** - Decision based on role (`aml_analyst_junior`) which has a max_depth constraint of 2 hops

---

## Verification

To verify all users are set up correctly, run:

```bash
./scripts/verify-aml-users.sh
```

Or manually check:

```bash
# Check users exist
docker compose exec postgres psql -U postgres -d policy_store -c \
  "SELECT email, first_name, is_active FROM users WHERE email LIKE '%analyst%' OR email LIKE '%manager%';"

# Test login
curl -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst.junior@pg-cerbos.com", "password": "user123"}'
```

## Notes

- All users share the same password: `user123`
- Password hash: `$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq`
- All users are active (`is_active = TRUE`)
- User attributes are stored in the `user_attributes` table
- Roles are assigned via the `user_roles` junction table
