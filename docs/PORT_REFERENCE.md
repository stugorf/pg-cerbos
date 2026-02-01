# Port Reference - UES MVP

## Service Ports

| Service | Container Port | Host Port | Purpose |
|---------|---------------|-----------|---------|
| **PostgreSQL** | 5432 | 5434 | Main database |
| **Query Results DB** | 5432 | 5433 | Query results storage |
| **MinIO** | 9000 | 9000 | S3-compatible storage |
| **MinIO Console** | 9001 | 9001 | MinIO admin UI |
| **Nessie** | 19120 | 19120 | Iceberg catalog |
| **Trino Coordinator** | 8080 | 8080 | Trino UI & direct access |
| **Policy Registry Backend** | 8080 | 8082 | API server |
| **Policy Registry Frontend** | 80 | 8083 | Web UI |
| **OPA** | 8181 | 8181 | Policy Decision Point |
| **OPA Diagnostics** | 8282 | 8282 | OPA diagnostics |
| **Cerbos** | 3593 | 3593 | Cerbos PDP (HTTP/gRPC) |
| **Cerbos Adapter** | 8080 | 3594 | Envoy-Cerbos adapter |
| **Envoy** | 8081 | 8081 | **Client entrypoint** (authorization proxy) |

## Important Notes

### Client Entry Point
- **Port 8081 (Envoy)**: This is the main entry point for clients
- All requests go through Envoy, which enforces authorization
- Envoy routes to Trino after authorization passes

### Direct Access (No Authorization)
- **Port 8080 (Trino)**: Direct access to Trino (bypasses Envoy/authorization)
- Use only for testing/debugging
- Not recommended for production use

### Authorization Services
- **Port 8181 (OPA)**: Original authorization service (still running)
- **Port 3593 (Cerbos)**: New authorization service (active)
- **Port 3594 (Adapter)**: Translates Envoy requests to Cerbos format

## Testing Endpoints

### Through Envoy (with authorization)
```bash
curl -X POST \
  -H 'x-user-id: 2' \
  -H 'x-user-email: fullaccess@pg-cerbos.com' \
  -H 'x-user-roles: full_access_user' \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8081/v1/statement
```

### Direct to Trino (no authorization)
```bash
curl -X POST \
  --data-binary 'SELECT * FROM postgres.public.person LIMIT 5' \
  http://localhost:8080/v1/statement
```

### Cerbos Health Check
```bash
curl http://localhost:3593/_cerbos/health
```

### Adapter Health Check
```bash
curl http://localhost:3594/health
```

## Port Conflicts

If you get "port already in use" errors:

```bash
# Check what's using a port
lsof -i :8081

# Or
netstat -an | grep 8081
```

## Network Flow

```
Client (localhost:8081)
    ↓
Envoy (port 8081) ← Authorization check
    ↓
Cerbos Adapter (port 3594) or OPA (port 8181)
    ↓
Authorization Decision
    ↓
Trino Coordinator (port 8080)
    ↓
Data Sources (Postgres, Iceberg)
```
