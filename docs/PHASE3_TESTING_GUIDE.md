# Phase 3: Enhanced ABAC Testing Guide

## Testing Status

✅ **Database Schema**: Created and populated
✅ **Test Suite**: Fixed format and ready to run
✅ **Implementation**: All code complete

## What Was Done

1. ✅ Created `user_attributes` table in database
2. ✅ Populated seed data with test users
3. ✅ Fixed ABAC test suite format to match existing test format
4. ✅ All implementation files are in place

## Running Tests

### Prerequisites

Ensure services are running:
```bash
just up
```

### Test Commands

```bash
# 1. Verify database schema exists
docker compose exec postgres psql -U postgres -d postgres -c "\d user_attributes"

# 2. Verify seed data exists
docker compose exec postgres psql -U postgres -d postgres -c "SELECT user_id, team, region, clearance_level FROM user_attributes;"

# 3. Compile Cerbos policies (verify syntax)
# If Cerbos CLI is installed:
cerbos compile cerbos/policies

# Or via Docker:
docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest compile /policies

# 4. Run ABAC test suite
# If Cerbos CLI is installed:
cerbos test cerbos/policies/tests/cypher_query_abac_test_suite.yaml

# Or via Docker:
docker run --rm -v $(pwd)/cerbos/policies:/policies ghcr.io/cerbos/cerbos:latest test /policies/tests/cypher_query_abac_test_suite.yaml

# 5. Run comprehensive verification
just verify-phase3-abac
```

## Manual API Testing

### Test 1: User Attributes API

```bash
# Get admin token
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "admin@pg-cerbos.com", "password": "admin123"}' \
    | jq -r '.access_token')

# Get user attributes for junior analyst (user_id: 5)
curl -X GET http://localhost:8082/users/5/attributes \
    -H "Authorization: Bearer $TOKEN" | jq
```

Expected response:
```json
{
  "user_id": 5,
  "team": "Team A",
  "region": "US",
  "clearance_level": 1,
  "department": "AML"
}
```

### Test 2: Team-Based Access Control

```bash
# Get junior analyst token (Team A, clearance 1)
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "analyst.junior@pg-cerbos.com", "password": "user123"}' \
    | jq -r '.access_token')

# Query Team A customers (should succeed)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (c:Customer {team: \"Team A\"}) RETURN c LIMIT 5"
    }' | jq

# Query Team B customers (should fail - team mismatch)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (c:Customer {team: \"Team B\"}) RETURN c LIMIT 5"
    }' | jq
```

Expected:
- Team A query: `{"success": true, ...}`
- Team B query: `{"detail": "Not authorized..."}` (403 error)

### Test 3: Clearance-Based PEP Access

```bash
# Get junior analyst token (clearance 1)
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "analyst.junior@pg-cerbos.com", "password": "user123"}' \
    | jq -r '.access_token')

# Query PEP customers (should fail - clearance too low)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (c:Customer {pep_flag: true}) RETURN c LIMIT 5"
    }' | jq

# Get high clearance analyst token (clearance 3)
TOKEN_HIGH=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "analyst.team_a.high@pg-cerbos.com", "password": "user123"}' \
    | jq -r '.access_token')

# Query PEP customers (should succeed - clearance >= 3)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN_HIGH" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (c:Customer {pep_flag: true}) RETURN c LIMIT 5"
    }' | jq
```

Expected:
- Low clearance: `{"detail": "Not authorized..."}` (403 error)
- High clearance: `{"success": true, ...}`

### Test 4: Clearance-Based Transaction Amount

```bash
# Get junior analyst token (clearance 1)
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "analyst.junior@pg-cerbos.com", "password": "user123"}' \
    | jq -r '.access_token')

# Query high-value transactions (should fail - amount > $100k, clearance < 2)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (t:Transaction) WHERE t.amount > 200000 RETURN t LIMIT 5"
    }' | jq

# Get senior analyst token (clearance 2)
TOKEN_SENIOR=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "analyst.senior@pg-cerbos.com", "password": "user123"}' \
    | jq -r '.access_token')

# Query medium-value transactions (should succeed - amount <= $500k, clearance >= 2)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN_SENIOR" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (t:Transaction) WHERE t.amount > 150000 RETURN t LIMIT 5"
    }' | jq
```

### Test 5: Region-Based Access

```bash
# Get US analyst token
TOKEN=$(curl -s -X POST http://localhost:8082/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email": "analyst.junior@pg-cerbos.com", "password": "user123"}' \
    | jq -r '.access_token')

# Query US customers (should succeed)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (c:Customer {region: \"US\"}) RETURN c LIMIT 5"
    }' | jq

# Query EU customers (should fail - region mismatch)
curl -X POST http://localhost:8082/query/graph \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
      "type": "cypher",
      "query": "MATCH (c:Customer {region: \"EU\"}) RETURN c LIMIT 5"
    }' | jq
```

## Test Results Summary

After running all tests, you should see:

✅ **Database**: user_attributes table exists with 9 rows
✅ **API**: User attributes endpoints return correct data
✅ **Policies**: Cerbos policies compile successfully
✅ **Test Suite**: 16 ABAC test cases pass
✅ **Team-Based**: Team A analyst can query Team A, cannot query Team B
✅ **Clearance-Based PEP**: Low clearance denied, high clearance allowed
✅ **Clearance-Based Amount**: Amount thresholds enforced correctly
✅ **Region-Based**: Region restrictions enforced correctly

## Troubleshooting

### Issue: user_attributes table doesn't exist
**Solution**: Run the migration manually:
```bash
docker compose exec -T postgres psql -U postgres -d postgres < postgres/init/31-user-attributes-schema.sql
docker compose exec -T postgres psql -U postgres -d postgres < postgres/init/41-user-attributes-seed-data.sql
```

### Issue: Test suite format error
**Solution**: The test suite has been fixed to match the existing format. If you see errors, verify the file format matches `cypher_query_test_suite_test.yaml`.

### Issue: API returns 404 for user attributes
**Solution**: 
1. Verify the backend service is running: `docker compose ps policy-registry-backend`
2. Check backend logs: `docker compose logs policy-registry-backend`
3. Verify the endpoint is registered in `app.py`

### Issue: Policies don't compile
**Solution**:
1. Check for syntax errors in `cypher_query.yaml`
2. Verify schema files exist and are valid JSON
3. Check Cerbos logs: `docker compose logs cerbos`

## Next Steps After Testing

1. ✅ Verify all tests pass
2. Document any issues found
3. Fix any bugs discovered
4. Proceed to Phase 4: Query Complexity Analysis
