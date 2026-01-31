-- Seed data for Authentication and Authorization System
-- This file populates the auth tables with initial data for the UES MVP

-- Insert roles
INSERT INTO roles (name, description) VALUES
    ('admin', 'System administrator with full access'),
    ('full_access_user', 'User who can query all fields in both postgres and iceberg'),
    ('postgres_only_user', 'User who can query all fields in only postgres'),
    ('restricted_user', 'User who can query both postgres and iceberg but cannot retrieve ssn')
ON CONFLICT (name) DO NOTHING;

-- Insert permissions for postgres access
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
    ('postgres_full_access', 'Full access to all postgres tables and fields', 'postgres', '*', '*', 'query'),
    ('postgres_table_access', 'Access to specific postgres tables', 'postgres', 'demo_data', '*', 'query'),
    ('postgres_table_access', 'Access to specific postgres tables', 'postgres', 'policy_store', '*', 'query')
ON CONFLICT (name) DO NOTHING;

-- Insert permissions for iceberg access
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
    ('iceberg_full_access', 'Full access to all iceberg tables and fields', 'iceberg', '*', '*', 'query'),
    ('iceberg_table_access', 'Access to specific iceberg tables', 'iceberg', 'sales.orders', '*', 'query'),
    ('iceberg_table_access', 'Access to specific iceberg tables', 'iceberg', 'sales.customers', '*', 'query')
ON CONFLICT (name) DO NOTHING;

-- Insert field-level permissions (for SSN restriction)
INSERT INTO permissions (name, description, resource_type, resource_name, field_name, action) VALUES
    ('ssn_access', 'Access to SSN field in any table', 'field', '*', 'ssn', 'query'),
    ('ssn_access', 'Access to SSN field in postgres demo_data', 'field', 'demo_data', 'ssn', 'query'),
    ('ssn_access', 'Access to SSN field in iceberg customers', 'field', 'sales.customers', 'ssn', 'query')
ON CONFLICT (name) DO NOTHING;

-- Insert admin user (password: admin123)
-- Note: This hash is for 'admin123' - generated with the container's Python environment
INSERT INTO users (email, password_hash, first_name, last_name) VALUES
    ('admin@ues-mvp.com', '$2b$12$JJ458WVWdus4yt6fs8v7F.2kBN9UIz24SVOqKV.5yQ/V4oEiRqKrO', 'Admin', 'User')
ON CONFLICT (email) DO NOTHING;

-- Insert demo users (password: user123)
INSERT INTO users (email, password_hash, first_name, last_name) VALUES
    ('fullaccess@ues-mvp.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'Full', 'Access'),
    ('postgresonly@ues-mvp.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'Postgres', 'Only'),
    ('restricted@ues-mvp.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'Restricted', 'User')
ON CONFLICT (email) DO NOTHING;

-- Assign roles to users
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'admin@ues-mvp.com' AND r.name = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'fullaccess@ues-mvp.com' AND r.name = 'full_access_user'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'postgresonly@ues-mvp.com' AND r.name = 'postgres_only_user'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'restricted@ues-mvp.com' AND r.name = 'restricted_user'
ON CONFLICT DO NOTHING;

-- Assign permissions to roles
-- Admin role gets all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'admin'
ON CONFLICT DO NOTHING;

-- Full access user gets all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'full_access_user'
ON CONFLICT DO NOTHING;

-- Postgres only user gets only postgres permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'postgres_only_user' 
  AND p.resource_type = 'postgres'
ON CONFLICT DO NOTHING;

-- Restricted user gets postgres and iceberg access but no SSN
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r, permissions p
WHERE r.name = 'restricted_user' 
  AND (p.resource_type IN ('postgres', 'iceberg') OR (p.resource_type = 'field' AND p.field_name != 'ssn'))
ON CONFLICT DO NOTHING; 