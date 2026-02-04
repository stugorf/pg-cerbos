# Quick Start Guide

## For New Developers

### Prerequisites
- Docker and Docker Compose installed
- Ports 8080-8083, 5434, 3593, 9000-9001, 19120 available
- `just` command runner (optional but recommended)

### 1. Start the Services

```bash
docker compose up -d
```

### 2. Initialize the Complete System

```bash
just init
```

This single command ensures everything is properly set up:
- ✅ **PostgreSQL**: Demo data, policy store, and authentication tables
- ✅ **Iceberg**: Demo schema and sample tables  
- ✅ **Authentication**: Users, roles, and permissions configured
- ✅ **Policies**: Cerbos policies loaded and validated
- ✅ **Trino**: Health check and cleanup of hanging queries

### 3. Access the System

- **Main Dashboard**: http://localhost:8083/auth.html
  - **SQL Query Tab**: Execute SQL queries with Cerbos authorization
  - **Policy Management Tab**: Create, edit, and manage Cerbos YAML policies
  - **Cerbos Logs Tab**: View real-time authorization decisions and audit logs
  - **User/Role/Permission Management Tabs**: Admin functions for access control
- **Trino UI**: http://localhost:8080 (direct Trino access)
- **MinIO Console**: http://localhost:9001 (S3 storage for Iceberg)
- **PuppyGraph Web UI**: http://localhost:8081 (graph database)

### 4. Test Queries

```sql
-- PostgreSQL demo data (10 records with names, SSNs, job titles)
SELECT * FROM postgres.public.person LIMIT 3;

-- Iceberg demo data (1 test record)
SELECT * FROM iceberg.demo.employee_performance ORDER BY performance_score DESC;
```

**Note**: All demo queries work immediately without semicolons (Trino requirement).

---

## Demo Users

| Email | Password | Role | Access Level |
|-------|----------|------|--------------|
| `admin@pg-cerbos.com` | `admin123` | Admin | Full system access |
| `fullaccess@pg-cerbos.com` | `user123` | Full Access | All data, all fields |
| `postgresonly@pg-cerbos.com` | `user123` | Postgres Only | Postgres only, all fields |
| `restricted@pg-cerbos.com` | `user123` | Restricted | All data, no SSN fields |

---

## Common Tasks

### Start Services
```bash
just up
```

### Stop Services
```bash
just down
```

### View Logs
```bash
just logs
```

### Check Service Status
```bash
just ps
```

### Validate Cerbos Policies
```bash
just validate-cerbos-policies
```

### Test Cerbos Policies
```bash
just test-cerbos-policies
```

---

## Troubleshooting

### Services Not Starting
```bash
# Check Docker status
docker info

# Check service logs
just logs

# Restart services
just down
just up
```

### Database Connection Issues
```bash
# Check PostgreSQL health
docker exec pg-cerbos-postgres pg_isready -U postgres

# Check database existence
docker exec pg-cerbos-postgres psql -U postgres -l
```

### Cerbos Policy Issues
```bash
# Check Cerbos health
just check-cerbos

# Validate policies
just validate-cerbos-policies

# Check Cerbos logs
just cerbos-logs
```

### Port Conflicts
If you get port conflicts, check what's using the ports:
```bash
# Check port usage
lsof -i :8080  # Trino
lsof -i :8081  # Envoy/PuppyGraph
lsof -i :8082  # Policy Registry
lsof -i :8083  # Policy UI
lsof -i :5434  # PostgreSQL
```

---

## Next Steps

1. **Explore the Web Interface** - Access http://localhost:8083/auth.html
2. **Try Different User Roles** - Test with different demo users
3. **Execute Sample Queries** - See the README for query examples
4. **Modify Policies** - Use the Policy Management tab to edit Cerbos policies
5. **View Authorization Logs** - Check the Cerbos Logs tab for authorization decisions

---

## Additional Resources

- [README.md](../README.md) - Complete system documentation
- [Developer Setup Guide](./DEVELOPER_SETUP.md) - Detailed setup instructions
- [Cerbos Quick Start](./CERBOS_QUICKSTART.md) - Cerbos-specific setup
- [AML PoC Quick Start](./AML_POC_QUICKSTART.md) - AML proof of concept setup
- [Port Reference](./PORT_REFERENCE.md) - Service port mappings
- [Postman Setup](./POSTMAN_SETUP.md) - API testing with Postman
