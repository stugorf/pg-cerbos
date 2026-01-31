# UES MVP Demo Queries - Quick Reference

## 🚀 Quick Start
1. **Start Services**: `docker-compose up -d`
2. **Initialize Iceberg**: `./scripts/init_iceberg.sh`
3. **Access Web UI**: http://localhost:8082

## 👥 User Accounts & Passwords

| User | Email | Password | Access Level |
|------|-------|----------|--------------|
| **Admin** | `admin@ues-mvp.com` | `admin123` | Full system access |
| **Full Access** | `fullaccess@ues-mvp.com` | `user123` | All data, no admin |
| **Postgres Only** | `postgresonly@ues-mvp.com` | `user123` | PostgreSQL only |
| **Restricted** | `restricted@ues-mvp.com` | `user123` | Both sources, SSN masked |

---

## 🔐 ADMIN USER - Full System Access

### Basic Data Access
```sql
-- PostgreSQL count
SELECT COUNT(*) FROM postgres.public.person;

-- PostgreSQL with SSN (visible)
SELECT id, first_name, last_name, ssn FROM postgres.public.person LIMIT 3;

-- Iceberg count
SELECT COUNT(*) FROM iceberg.sales.person;

-- Iceberg with SSN (visible)
SELECT id, first_name, last_name, ssn, age FROM iceberg.sales.person LIMIT 3;
```

### System Administration
```sql
-- View policies
SELECT COUNT(*) FROM postgres.public.policies;

-- View users
SELECT COUNT(*) FROM postgres.public.users;
```

---

## 📊 FULL ACCESS USER - All Data Access

### Cross-Data Source Analysis
```sql
-- Compare both data sources
SELECT 
    'PostgreSQL' as source, COUNT(*) as count
FROM postgres.public.person
UNION ALL
SELECT 
    'Iceberg' as source, COUNT(*) as count
FROM iceberg.sales.person;

-- Job title analysis across sources
SELECT 
    job_title,
    COUNT(*) as total_count
FROM (
    SELECT job_title FROM postgres.public.person
    UNION ALL
    SELECT job_title FROM iceberg.sales.person
) combined
GROUP BY job_title
ORDER BY total_count DESC;
```

### SSN Field Access (Unrestricted)
```sql
-- SSN analysis
SELECT 
    LEFT(ssn, 3) as ssn_prefix,
    COUNT(*) as count
FROM postgres.public.person
GROUP BY LEFT(ssn, 3)
ORDER BY count DESC;
```

---

## 🗄️ POSTGRES-ONLY USER - PostgreSQL Access

### PostgreSQL Queries
```sql
-- Basic count
SELECT COUNT(*) FROM postgres.public.person;

-- With SSN (visible)
SELECT first_name, last_name, job_title, ssn 
FROM postgres.public.person 
WHERE job_title LIKE '%Engineer%';

-- Job analysis
SELECT 
    job_title,
    COUNT(*) as count
FROM postgres.public.person
GROUP BY job_title
ORDER BY count DESC;
```

### ❌ Iceberg Access (Should Fail)
```sql
-- This should fail for postgres-only users
SELECT COUNT(*) FROM iceberg.sales.person;
```

---

## 🚫 RESTRICTED USER - Restricted Access

### Accessible Queries (No SSN)
```sql
-- PostgreSQL without SSN
SELECT id, first_name, last_name, job_title, gender 
FROM postgres.public.person 
ORDER BY id;

-- Iceberg without SSN
SELECT id, first_name, last_name, job_title, gender, age 
FROM iceberg.sales.person 
ORDER BY id;

-- Cross-source analysis (SSN masked)
SELECT 
    job_title,
    COUNT(*) as total_count
FROM (
    SELECT job_title FROM postgres.public.person
    UNION ALL
    SELECT job_title FROM iceberg.sales.person
) combined
GROUP BY job_title;
```

### ❌ SSN Queries (Should Fail)
```sql
-- These should be blocked for restricted users
SELECT ssn FROM postgres.public.person LIMIT 1;
SELECT ssn FROM iceberg.sales.person LIMIT 1;
SELECT id, first_name, ssn FROM postgres.public.person;
```

---

## 🧪 Testing Scenarios

### 1. **Basic Access Test**
- **Admin/Full Access**: Should see all data with SSN
- **Postgres Only**: Should see PostgreSQL data only
- **Restricted**: Should see both sources, SSN masked

### 2. **SSN Field Protection Test**
- **Admin/Full Access**: Can query SSN fields
- **Restricted**: SSN queries should be blocked by OPA policy

### 3. **Cross-Data Source Test**
- **Admin/Full Access**: Can join/compare both sources
- **Postgres Only**: Iceberg queries should fail
- **Restricted**: Can access both but SSN masked

### 4. **Column Masking Test**
- **Restricted User**: SSN values should appear as `****-**-****`
- **Admin/Full Access**: SSN values should be visible

---

## 🔍 Expected Results Summary

| User Role | PostgreSQL | Iceberg | SSN Fields | System Tables |
|-----------|------------|---------|------------|---------------|
| **Admin** | ✅ Full | ✅ Full | ✅ Visible | ✅ Access |
| **Full Access** | ✅ Full | ✅ Full | ✅ Visible | ❌ No Access |
| **Postgres Only** | ✅ Full | ❌ No Access | ✅ Visible (PG only) | ❌ No Access |
| **Restricted** | ✅ Full (SSN masked) | ✅ Full (SSN masked) | ❌ Blocked | ❌ No Access |

---

## 🚨 Troubleshooting

### Common Issues
1. **"Table not found"**: Run `./scripts/init_iceberg.sh`
2. **"Access denied"**: Check user role and permissions
3. **"SSN queries blocked"**: Expected for restricted users
4. **"Iceberg access failed"**: Expected for postgres-only users

### Debug Commands
```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs trino-coordinator
docker-compose logs policy-registry-backend

# Test connectivity
curl http://localhost:8082/health
curl http://localhost:8081/health
```

---

## 📚 Full Demo Scripts

For comprehensive testing, use the full demo script:
```bash
./scripts/demo_queries_by_user.sql
```

This contains all queries organized by user role with detailed explanations. 