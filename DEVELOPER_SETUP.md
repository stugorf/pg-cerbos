# Developer Setup Guide

This guide will help you get the UES MVP project up and running on your local machine.

## Prerequisites

- **Docker & Docker Compose**: Latest version
- **Git**: For cloning the repository
- **Just**: Command runner (optional, but recommended)

### Installing Just (Optional)

```bash
# macOS
brew install just

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash

# Windows
scoop install just
```

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/stugorf/pg-cerbos.git
cd pg-cerbos
```

### 2. Environment Setup

```bash
# Copy environment configuration
cp env.example .env

# Edit .env if you need to customize settings
# (Most defaults should work for development)
```

### 3. Complete Initialization

```bash
# Make the init script executable and run it
chmod +x scripts/init.sh
./scripts/init.sh
```

**Or use Just (recommended):**

```bash
just init
```

This single command will:
- Start all Docker services
- Wait for services to be ready
- Initialize all databases
- Set up authentication and authorization
- Create demo data and policies
- Initialize Iceberg tables

### 4. Verify Setup (Optional but Recommended)

```bash
just verify
```

This will test the entire authentication system and verify that:
- All services are running correctly
- Authentication is working
- Role-based access control is functioning
- Field-level security is enforced

## What Gets Set Up

### Services
- **PostgreSQL**: Main database with demo data, policies, and auth
- **MinIO**: S3-compatible object store for Iceberg
- **Nessie**: Catalog service for Iceberg
- **Trino**: SQL query engine (coordinator + worker)
- **OPA**: Open Policy Agent for authorization
- **Envoy**: Authorization proxy
- **Policy Registry**: FastAPI backend for policy management
- **Policy UI**: Web interface for authentication and queries

### Databases
- `demo_data`: Sample user data with sensitive fields (SSN)
- `policy_store`: OPA policies and metadata
- `query_results`: Query execution history and results

### Authentication
- **Admin User**: `admin@pg-cerbos.com` / `admin123`
- **Full Access User**: `fullaccess@pg-cerbos.com` / `user123`
- **Postgres Only User**: `postgresonly@pg-cerbos.com` / `user123`
- **Restricted User**: `restricted@pg-cerbos.com` / `user123`

### Data Sources
- **PostgreSQL**: `demo_data.person` table with 10 sample records
- **Iceberg**: `sales.person` table with 10 sample records

## Accessing the System

### Web Interfaces
- **Authentication & SQL Editor**: http://localhost:8083/auth.html
- **Policy Editor**: http://localhost:8083
- **Policy Registry API**: http://localhost:8082
- **Trino UI (direct)**: http://localhost:8080
- **MinIO Console**: http://localhost:9001

### API Endpoints
- **Trino via Envoy (enforced)**: http://localhost:8081
- **OPA API**: http://localhost:8181

## Development Workflow

### 1. Start Services
```bash
just up
```

### 2. View Logs
```bash
just logs          # All services
just trino-logs    # Trino only
```

### 3. Check Status
```bash
just ps            # Container status
just trino-status  # Trino cluster info
```

### 4. Stop Services
```bash
just down
```

### 5. Rebuild a Service
```bash
just rebuild <service-name>
# Example: just rebuild trino-coordinator
```

## Testing the System

### 1. Login to Web Interface
- Open http://localhost:8083/auth.html
- Login with any demo user
- Try executing SQL queries

### 2. Test Role-Based Access
- **Admin**: Can access everything
- **Full Access**: Can query all data sources and fields
- **Postgres Only**: Can only query PostgreSQL data
- **Restricted**: Can query both sources but SSN fields are blocked

### 3. Sample Queries

#### Full Access User
```sql
-- Query PostgreSQL
SELECT * FROM postgres.public.demo_data LIMIT 5;

-- Query Iceberg
SELECT * FROM iceberg.sales.person LIMIT 5;
```

#### Postgres Only User
```sql
-- This works
SELECT * FROM postgres.public.demo_data LIMIT 5;

-- This will be denied
SELECT * FROM iceberg.sales.person LIMIT 5;
```

#### Restricted User
```sql
-- This works (no SSN)
SELECT first_name, last_name, job_title FROM postgres.public.demo_data LIMIT 5;

-- This will be denied (contains SSN)
SELECT * FROM postgres.public.demo_data LIMIT 5;
```

## Troubleshooting

### Common Issues

#### Services Not Starting
```bash
# Check Docker status
docker info

# Check service logs
just logs

# Restart services
just down
just up
```

#### Database Connection Issues
```bash
# Check PostgreSQL health
docker exec pg-cerbos-postgres pg_isready -U postgres

# Check database existence
docker exec pg-cerbos-postgres psql -U postgres -l
```

#### Policy Issues
```bash
# Check OPA health
curl http://localhost:8181/health

# Check policy registry
curl http://localhost:8082/health
```

#### Port Conflicts
If you get port conflicts, check what's using the ports:
```bash
# Check port usage
lsof -i :8080  # Trino
lsof -i :8081  # Envoy
lsof -i :8082  # Policy Registry
lsof -i :8083  # Policy UI
lsof -i :5434  # PostgreSQL
```

### Reset Everything
```bash
# Stop and remove everything
just down

# Remove all volumes (WARNING: This deletes all data)
docker volume prune -f

# Start fresh
just init
```

### Troubleshooting Authorization Issues

If you encounter "HTTP 403: Access denied by policy" errors:

1. **Check if OPA has policies loaded:**
   ```bash
   curl http://localhost:8181/v1/policies
   ```

2. **If no policies are loaded, clean up and recreate:**
   ```bash
   just cleanup-policies
   bash scripts/create_exact_rego_policy.sh
   ```

3. **Check OPA logs for syntax errors:**
   ```bash
   docker logs pg-cerbos-opa --tail 10
   ```

4. **Verify policy registry has working policies:**
   ```bash
   # Login first, then check policies
   curl -H "Authorization: Bearer <token>" http://localhost:8082/policies
   ```

## Development Notes

### Architecture Overview
- **Envoy** acts as the entry point and enforces authorization
- **OPA** evaluates policies and makes authorization decisions
- **Trino** executes SQL queries with field-level security
- **PostgreSQL** stores policies, auth data, and demo data
- **Iceberg** provides additional data source with S3 storage

### Key Files
- `compose.yml`: Service definitions and dependencies
- `scripts/init.sh`: Complete initialization script
- `postgres/init/`: Database initialization scripts
- `opa/`: OPA policy files
- `envoy/envoy.yaml`: Envoy configuration
- `trino/`: Trino configuration files

### Adding New Features
1. **New Data Sources**: Add to Trino catalog configuration
2. **New Policies**: Modify OPA policies in `opa/` directory
3. **New Users/Roles**: Add to auth seed data in `postgres/init/`
4. **New Services**: Add to `compose.yml` and update init scripts

## Support

If you encounter issues:
1. Check the logs: `just logs`
2. Verify service health: `just ps`
3. Check this guide and the main README.md
4. Review the troubleshooting section above

## Next Steps

After successful setup:
1. Explore the web interface
2. Try different user roles and permissions
3. Execute sample queries
4. Modify policies to see how authorization works
5. Add your own data sources or policies 