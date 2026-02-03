# PuppyGraph Test Suite

This directory contains automated tests for PuppyGraph schema loading, validation, and query execution.

## Test Scripts

### Schema Tests

- **`test-schema-loading.sh`** - Verifies schema loads at startup via `SCHEMA_PATH`
- **`test-schema-api.sh`** - Tests schema accessibility via API endpoint
- **`test-schema-validation.sh`** - Tests schema validation in PuppyGraph
- **`test-schema-format.sh`** - Validates schema format compliance (regression test)

### Query Tests

- **`test-vertex-queries.sh`** - Tests basic vertex queries (Customer, Account, Transaction)
- **`test-edge-queries.sh`** - Tests edge traversal queries (OWNS, SENT_TXN, FROM_ALERT)
- **`test-complex-queries.sh`** - Tests complex multi-hop graph traversals

### Configuration Tests

- **`test-version-compatibility.sh`** - Verifies PuppyGraph version compatibility
- **`test-configuration-persistence.sh`** - Tests schema persistence after container restart

## Running Tests

### Individual Tests

```bash
# Test schema format (fast, no service required)
just test-puppygraph-format

# Test schema loading
just test-puppygraph-schema

# Test schema API
just test-puppygraph-api

# Test schema validation
just test-puppygraph-validation

# Test vertex queries
just test-puppygraph-vertices

# Test edge queries
just test-puppygraph-edges

# Test complex queries
just test-puppygraph-complex

# Test version compatibility
just test-puppygraph-version

# Test configuration persistence
just test-puppygraph-persistence
```

### Run All Tests

```bash
just test-puppygraph-all
```

This runs all tests in the recommended order:
1. Format validation (fastest, no service required)
2. Version compatibility check
3. Schema loading
4. Schema API
5. Schema validation
6. Vertex queries
7. Edge queries
8. Complex queries
9. Configuration persistence

## Prerequisites

- Docker and Docker Compose running
- PuppyGraph service running (`just up` or `docker compose up -d`)
- `jq` installed for JSON parsing
- `curl` installed for API testing

## Test Requirements

- PuppyGraph service must be running and healthy
- Schema file must exist at `puppygraph/aml-schema.json`
- PostgreSQL service must be running with AML schema data

## Troubleshooting

### Tests Failing

1. **Service not ready**: Ensure PuppyGraph is running
   ```bash
   docker compose ps
   just check-puppygraph
   ```

2. **Schema not loading**: Check logs
   ```bash
   docker logs pg-cerbos-puppygraph | grep -i schema
   ```

3. **Queries failing**: Verify data exists in PostgreSQL
   ```bash
   docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SELECT COUNT(*) FROM aml.customer;"
   ```

### Test Timeouts

Some tests wait up to 30-60 seconds for services to be ready. If tests consistently timeout:
- Check service health: `just check-puppygraph`
- Increase wait times in test scripts if needed
- Check Docker resource limits

## Adding New Tests

1. Create a new test script in `tests/` directory
2. Make it executable: `chmod +x tests/test-new-feature.sh`
3. Add a recipe to `Justfile`:
   ```justfile
   test-puppygraph-new-feature:
       bash tests/test-new-feature.sh
   ```
4. Add to `test-puppygraph-all` recipe if it should run in the full suite

## Test Output

Tests use standard exit codes:
- `0` = Success
- `1` = Failure

Tests output:
- ✅ for successful checks
- ❌ for failures
- ⚠️ for warnings

## Integration

These tests can be integrated into:
- Pre-commit hooks
- Local development workflow
- Manual verification before deployments
- Documentation validation

See `docs/PUPPYGRAPH_SCHEMA_RESOLUTION_AND_TESTING.md` for detailed testing strategy and examples.
