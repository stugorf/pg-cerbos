# UES MVP Demo Scripts

This directory contains scripts for testing and demonstrating the UES MVP policy and permission system.

## 🚀 Quick Start

1. **Start the services**:
   ```bash
   docker-compose up -d
   ```

2. **Initialize all demo data** (recommended for new developers):
   ```bash
   ./scripts/init_all_data.sh
   ```

3. **Or initialize individual components**:
   ```bash
   ./scripts/init_iceberg.sh    # Iceberg tables only
   ./scripts/init.sh            # Basic setup
   ```

4. **Test the demo queries**:
   ```bash
   ./scripts/test_demo_queries.sh
   ```

## 📁 Script Files

### Core Scripts

- **`init_all_data.sh`** - **Complete data initialization** (recommended for new developers)
- **`init_iceberg.sh`** - Creates and populates Iceberg tables
- **`verify_policies.sh`** - Comprehensive policy verification
- **`test_demo_queries.sh`** - Tests user access levels

### Demo Query Files

- **`demo_queries_by_user.sql`** - Complete demo queries organized by user role
- **`demo_quick_reference.md`** - Quick reference for demo queries

## 👥 User Accounts for Testing

| User | Email | Password | Purpose |
|------|-------|----------|---------|
| **Admin** | `admin@ues-mvp.com` | `admin123` | Full system access |
| **Full Access** | `fullaccess@ues-mvp.com` | `user123` | All data access |
| **Postgres Only** | `postgresonly@ues-mvp.com` | `user123` | PostgreSQL only |
| **Restricted** | `restricted@ues-mvp.com` | `user123` | Both sources, SSN masked |

## 🧪 Testing Scenarios

### 1. **Basic Access Control**
- Verify each user can only access data according to their role
- Test that restricted users cannot access SSN fields
- Confirm postgres-only users cannot access Iceberg

### 2. **SSN Field Protection**
- Admin and Full Access users should see SSN values
- Restricted users should be blocked from SSN queries
- Column masking should hide SSN values for restricted users

### 3. **Cross-Data Source Access**
- Admin and Full Access users can query both PostgreSQL and Iceberg
- Postgres-only users should fail on Iceberg queries
- Restricted users can access both but with SSN masking

### 4. **System Administration**
- Only admin users should access system tables
- Other users should be restricted from administrative functions

## 🔍 Expected Results

| User Role | PostgreSQL | Iceberg | SSN Fields | System Tables |
|-----------|------------|---------|------------|---------------|
| **Admin** | ✅ Full | ✅ Full | ✅ Visible | ✅ Access |
| **Full Access** | ✅ Full | ✅ Full | ✅ Visible | ❌ No Access |
| **Postgres Only** | ✅ Full | ❌ No Access | ✅ Visible (PG only) | ❌ No Access |
| **Restricted** | ✅ Full (SSN masked) | ✅ Full (SSN masked) | ❌ Blocked | ❌ No Access |

## 📚 Demo Queries by User Role

### Admin User
```sql
-- Full access to everything
SELECT * FROM postgres.public.person;
SELECT * FROM iceberg.sales.person;
SELECT COUNT(*) FROM postgres.public.policies;
```

### Full Access User
```sql
-- All data access, no admin features
SELECT * FROM postgres.public.person;
SELECT * FROM iceberg.sales.person;
-- Cross-source analysis
SELECT 'PG' as source, COUNT(*) FROM postgres.public.person
UNION ALL
SELECT 'Iceberg' as source, COUNT(*) FROM iceberg.sales.person;
```

### Postgres-Only User
```sql
-- PostgreSQL only
SELECT * FROM postgres.public.person;
-- This should fail:
-- SELECT * FROM iceberg.sales.person;
```

### Restricted User
```sql
-- Both sources, SSN masked
SELECT id, first_name, last_name, job_title FROM postgres.public.person;
SELECT id, first_name, last_name, job_title FROM iceberg.sales.person;
-- This should be blocked:
-- SELECT ssn FROM postgres.public.person;
```

## 🚨 Troubleshooting

### Common Issues

1. **"Table not found" errors**:
   - Run `./scripts/init_iceberg.sh` to create Iceberg tables

2. **"Access denied" errors**:
   - Check user roles and permissions
   - Verify OPA policy configuration

3. **SSN queries not blocked**:
   - Check OPA policy is loaded
   - Verify user has restricted role

4. **Iceberg access failing**:
   - Ensure Iceberg tables are initialized
   - Check Trino access control configuration

### Debug Commands

```bash
# Check service status
docker-compose ps

# View service logs
docker-compose logs trino-coordinator
docker-compose logs policy-registry-backend
docker-compose logs opa

# Test connectivity
curl http://localhost:8082/health
curl http://localhost:8081/health
curl http://localhost:8080/health
```

## 🎯 Next Steps

1. **Run the test script**: `./scripts/test_demo_queries.sh`
2. **Access the web interface**: http://localhost:8082
3. **Test with different users**: Login and run queries
4. **Verify access control**: Ensure restrictions work correctly
5. **Check column masking**: Verify SSN fields are properly masked

## 📖 Additional Documentation

- **Policy Summary**: `../docs/policy-and-permissions-summary.md`
- **Main README**: `../README.md`
- **Developer Setup**: `../DEVELOPER_SETUP.md`

## 🔧 Customization

To add new demo scenarios:

1. **Add new users** in `../postgres/init/40-auth-seed-data.sql`
2. **Create new roles** with appropriate permissions
3. **Add demo queries** to `demo_queries_by_user.sql`
4. **Update test script** in `test_demo_queries.sh`
5. **Document changes** in this README

## 💡 Tips for Demonstrations

1. **Start with simple queries** to establish baseline access
2. **Show access restrictions** by switching between users
3. **Demonstrate SSN protection** with restricted users
4. **Highlight cross-data source** capabilities for appropriate users
5. **Use the web interface** for interactive demonstrations 