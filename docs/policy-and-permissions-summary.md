# UES MVP Policy and Permissions Summary

## Overview

The UES MVP implements a comprehensive Role-Based Access Control (RBAC) system that demonstrates various data access capabilities across both PostgreSQL and Iceberg data sources. The system enforces fine-grained permissions at the table, field, and query level.

## User Roles and Capabilities

### 1. Admin User (`admin@ues-mvp.com`)
- **Password**: `admin123`
- **Capabilities**: Full system access
- **Data Access**: 
  - ✅ PostgreSQL: All tables and fields
  - ✅ Iceberg: All tables and fields
  - ✅ SSN fields: Unrestricted access
  - ✅ System administration: User, role, and permission management

### 2. Full Access User (`fullaccess@ues-mvp.com`)
- **Password**: `user123`
- **Capabilities**: Full data access without admin privileges
- **Data Access**:
  - ✅ PostgreSQL: All tables and fields
  - ✅ Iceberg: All tables and fields
  - ✅ SSN fields: Unrestricted access
  - ❌ System administration: No access

### 3. Postgres-Only User (`postgresonly@ues-mvp.com`)
- **Password**: `user123`
- **Capabilities**: Limited to PostgreSQL data only
- **Data Access**:
  - ✅ PostgreSQL: All tables and fields
  - ❌ Iceberg: No access
  - ✅ SSN fields: Unrestricted access (within PostgreSQL)
  - ❌ System administration: No access

### 4. Restricted User (`restricted@ues-mvp.com`)
- **Password**: `user123`
- **Capabilities**: Access to both systems with SSN field restrictions
- **Data Access**:
  - ✅ PostgreSQL: All tables and fields (SSN masked)
  - ✅ Iceberg: All tables and fields (SSN masked)
  - ❌ SSN fields: Access denied, fields are masked
  - ❌ System administration: No access

## Permission Structure

### Resource Types
- **`postgres`**: PostgreSQL database access
- **`iceberg`**: Iceberg table access
- **`field`**: Field-level access control

### Actions
- **`query`**: Execute SQL queries
- **`read`**: Read data (future use)
- **`write`**: Write/modify data (future use)

### Permission Examples

#### PostgreSQL Access
```sql
-- Full access to all PostgreSQL tables
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
('postgres_full_access', 'Full access to all postgres tables and fields', 'postgres', '*', '*', 'query');

-- Access to specific PostgreSQL tables
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
('postgres_table_access', 'Access to specific postgres tables', 'postgres', 'demo_data', '*', 'query');
```

#### Iceberg Access
```sql
-- Full access to all Iceberg tables
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
('iceberg_full_access', 'Full access to all iceberg tables and fields', 'iceberg', '*', '*', 'query');

-- Access to specific Iceberg tables
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
('iceberg_table_access', 'Access to specific iceberg tables', 'iceberg', 'sales.orders', '*', 'query');
```

#### Field-Level Access Control
```sql
-- SSN field access control
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
('ssn_access', 'Access to SSN field in any table', 'field', '*', 'ssn', 'query');
```

## Data Sources and Tables

### PostgreSQL (`postgres.public.*`)
- **`person`**: Demo person data with SSN, name, job title, gender
- **`policies`**: Policy registry data
- **`users`**: User authentication data
- **`roles`**: Role definitions
- **`permissions`**: Permission definitions
- **`queries`**: Query execution history
- **`query_results`**: Query result storage

### Iceberg (`iceberg.sales.*`)
- **`person`**: Demo person data with SSN, name, job title, gender, age
- **Location**: `s3a://warehouse/sales/`

## Access Control Implementation

### 1. Backend Authentication (FastAPI)
- JWT-based authentication
- Role-based permission checking
- User session management

### 2. OPA Policy Enforcement
- **File**: `opa/authz-policy-fixed.rego`
- **Enforcement Point**: Envoy proxy
- **Rules**:
  - Admin users: Full access
  - Full access users: Both data sources
  - Postgres-only users: PostgreSQL only
  - Restricted users: Both sources, no SSN

### 3. Trino Access Control
- **File**: `trino/coordinator/etc/access-control.properties`
- **Type**: File-based access control
- **Enforcement**: Schema, table, and column level

### 4. Column Masking
- **File**: `trino/coordinator/column-masks.properties`
- **Purpose**: Mask sensitive fields (SSN) for restricted users
- **Implementation**: Pattern-based masking with configurable formats

## Security Features

### 1. SSN Field Protection
- **Detection**: Multiple variations (ssn, SSN, social_security, etc.)
- **Enforcement**: OPA policy blocks queries containing SSN references
- **Masking**: Trino column masks hide SSN values for restricted users

### 2. Query Content Validation
- **Method**: OPA policy analyzes SQL query content
- **Checks**: 
  - Data source access (PostgreSQL vs Iceberg)
  - Sensitive field references
  - User role permissions

### 3. Multi-Layer Security
- **Authentication**: JWT tokens with expiration
- **Authorization**: Role-based access control
- **Data Protection**: Field-level masking
- **Audit Trail**: Query execution logging

## Testing and Verification

### 1. Automated Testing
```bash
# Run comprehensive policy verification
./scripts/verify_policies.sh

# Initialize Iceberg tables
./scripts/init_iceberg.sh
```

### 2. Manual Testing
- **Web Interface**: http://localhost:8082
- **Test Users**: Use different accounts to verify permissions
- **Query Examples**: Test various SQL queries across data sources

### 3. Test Queries
```sql
-- PostgreSQL access test
SELECT * FROM postgres.public.person LIMIT 3;

-- Iceberg access test
SELECT * FROM iceberg.sales.person LIMIT 3;

-- SSN field test (should be blocked for restricted users)
SELECT ssn FROM postgres.public.person LIMIT 1;
```

## Current Status and Recommendations

### ✅ **Working Well**
- Comprehensive RBAC system
- Multi-data source support
- Field-level access control
- SSN field protection
- Query content validation
- Column masking implementation

### ⚠️ **Areas for Improvement**
- Trino access control needs proper configuration
- Iceberg tables may need initialization
- Additional field variations for SSN detection
- Enhanced audit logging

### 🔧 **Immediate Actions**
1. **Run Iceberg initialization**: `./scripts/init_iceberg.sh`
2. **Verify policies**: `./scripts/verify_policies.sh`
3. **Test with different users**: Verify permission enforcement
4. **Check column masking**: Ensure SSN fields are properly masked

### 🚀 **Future Enhancements**
1. **Dynamic policy updates**: Real-time policy modification
2. **Advanced masking**: Hash-based, partial, or custom masking
3. **Audit dashboard**: Comprehensive access logging
4. **Policy templates**: Reusable permission patterns
5. **Integration testing**: Automated policy validation

## Troubleshooting

### Common Issues
1. **Iceberg tables not found**: Run `./scripts/init_iceberg.sh`
2. **Permission denied**: Check user roles and permissions
3. **SSN queries blocked**: Verify user role restrictions
4. **Services not responding**: Check Docker container status

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

## Conclusion

The UES MVP provides a robust foundation for demonstrating various data access control scenarios. The system successfully implements:

- **Role-based access control** across multiple data sources
- **Field-level security** for sensitive data
- **Multi-layer enforcement** (backend, OPA, Trino)
- **Comprehensive testing** and verification tools

This implementation serves as an excellent example of how to build secure, multi-tenant data access systems with fine-grained permission controls. 