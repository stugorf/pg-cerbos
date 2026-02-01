# Postman Setup Guide

## Quick Setup

### Request Configuration

**Method:** `POST`

**URL:** `http://localhost:8081/v1/statement`

**Headers:**
```
x-user-id: 2
x-user-email: fullaccess@pg-cerbos.com
x-user-roles: full_access_user
```

**Body:** 
- Select **raw** and **Text**
- Enter your SQL query:
```
SELECT * FROM postgres.public.person LIMIT 5
```

## Example Requests

### Full Access User (Allowed)
- **Method:** POST
- **URL:** `http://localhost:8081/v1/statement`
- **Headers:**
  - `x-user-id`: `2`
  - `x-user-email`: `fullaccess@pg-cerbos.com`
  - `x-user-roles`: `full_access_user`
- **Body:** `SELECT * FROM postgres.public.person LIMIT 5`

### Restricted User - SSN Query (Denied)
- **Method:** POST
- **URL:** `http://localhost:8081/v1/statement`
- **Headers:**
  - `x-user-id`: `4`
  - `x-user-email`: `restricted@pg-cerbos.com`
  - `x-user-roles`: `restricted_user`
- **Body:** `SELECT ssn FROM postgres.public.person LIMIT 5`

### Postgres-Only User - Iceberg Query (Denied)
- **Method:** POST
- **URL:** `http://localhost:8081/v1/statement`
- **Headers:**
  - `x-user-id`: `3`
  - `x-user-email`: `postgresonly@pg-cerbos.com`
  - `x-user-roles`: `postgres_only_user`
- **Body:** `SELECT * FROM iceberg.demo.employee_performance LIMIT 5`

## Troubleshooting

### Error: `{"detail": "Not Found"}`

This usually means:
1. **Wrong URL** - Make sure you're using `/v1/statement` not `/check` or `/health`
2. **Wrong Method** - Must be `POST`, not `GET`
3. **Missing Headers** - All three headers (`x-user-id`, `x-user-email`, `x-user-roles`) are required

### Error: Connection Refused

- Check if Envoy is running: `docker compose ps envoy`
- Start Envoy if needed: `docker compose up -d envoy`

### Error: Authorization Denied

- Check your user role matches the policy
- Verify headers are spelled correctly (case-sensitive)
- Check Cerbos logs: `docker compose logs cerbos`

## Testing Direct Endpoints

### Health Check (Adapter)
- **Method:** GET
- **URL:** `http://localhost:3594/health`
- **Expected:** `{"status": "healthy", "service": "cerbos-adapter"}`

### Cerbos Health
- **Method:** GET
- **URL:** `http://localhost:3593/_cerbos/health`
- **Expected:** `SERVING`

### Trino Info (Direct - No Auth)
- **Method:** GET
- **URL:** `http://localhost:8080/v1/info`
- **Note:** This bypasses authorization

## Port Reference

- **8081**: Envoy (use this for authorized requests)
- **8080**: Trino (direct access, no auth)
- **3594**: Cerbos Adapter (internal service)
- **3593**: Cerbos (internal service)
