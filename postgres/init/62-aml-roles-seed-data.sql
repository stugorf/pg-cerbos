-- AML Roles and User Seed Data
-- This file adds AML-specific roles and users for testing Phase 2: Enhanced RBAC

-- Insert AML roles
INSERT INTO roles (name, description) VALUES
    ('aml_analyst', 'AML analyst with basic graph query access'),
    ('aml_analyst_junior', 'Junior AML analyst with limited graph query access (max 2 hops, no SAR)'),
    ('aml_analyst_senior', 'Senior AML analyst with extended graph query access (max 4 hops, no SAR)'),
    ('aml_manager', 'AML manager with full graph query access'),
    ('aml_manager_full', 'AML manager with full permissions (derived role)')
ON CONFLICT (name) DO NOTHING;

-- Insert AML demo users (password: user123)
-- Note: Password hash is for 'user123' - same as other demo users
INSERT INTO users (email, password_hash, first_name, last_name, is_active) VALUES
    ('analyst.junior@pg-cerbos.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'Junior', 'Analyst', TRUE),
    ('analyst.senior@pg-cerbos.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'Senior', 'Analyst', TRUE),
    ('analyst@pg-cerbos.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'Regular', 'Analyst', TRUE),
    ('manager@pg-cerbos.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'AML', 'Manager', TRUE)
ON CONFLICT (email) DO UPDATE SET is_active = TRUE;

-- Assign roles to users
-- Junior analyst gets aml_analyst_junior role (which inherits from aml_analyst via derived roles)
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst.junior@pg-cerbos.com' AND r.name = 'aml_analyst_junior'
ON CONFLICT DO NOTHING;

-- Also assign base aml_analyst role for derived role inheritance
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst.junior@pg-cerbos.com' AND r.name = 'aml_analyst'
ON CONFLICT DO NOTHING;

-- Senior analyst gets aml_analyst_senior role (which inherits from aml_analyst via derived roles)
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst.senior@pg-cerbos.com' AND r.name = 'aml_analyst_senior'
ON CONFLICT DO NOTHING;

-- Also assign base aml_analyst role for derived role inheritance
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst.senior@pg-cerbos.com' AND r.name = 'aml_analyst'
ON CONFLICT DO NOTHING;

-- Regular analyst gets aml_analyst role (fallback, limited to 2 hops, no SAR)
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst@pg-cerbos.com' AND r.name = 'aml_analyst'
ON CONFLICT DO NOTHING;

-- Manager gets aml_manager role (full access)
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'manager@pg-cerbos.com' AND r.name = 'aml_manager'
ON CONFLICT DO NOTHING;
