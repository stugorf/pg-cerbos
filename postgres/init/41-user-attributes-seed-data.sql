-- User Attributes Seed Data
-- This file populates user_attributes table for Phase 3: Enhanced ABAC
-- Provides test data for team-based, region-based, and clearance-based access control

-- Admin user: full clearance, no team restrictions
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'admin@pg-cerbos.com'), 
     NULL, NULL, 5, 'IT')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Team A junior analyst (low clearance, Team A only)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'analyst.junior@pg-cerbos.com'), 
     'Team A', 'US', 1, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Team B senior analyst (medium clearance, Team B)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'analyst.senior@pg-cerbos.com'), 
     'Team B', 'EU', 2, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Regular analyst (low clearance, no team assignment - for testing fallback)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'analyst@pg-cerbos.com'), 
     NULL, 'US', 1, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Manager (high clearance, no team restrictions)
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'manager@pg-cerbos.com'), 
     NULL, NULL, 4, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;

-- Additional test users for comprehensive ABAC testing
-- Team A analyst with high clearance (for testing clearance-based access)
INSERT INTO users (email, password_hash, first_name, last_name, is_active) VALUES
    ('analyst.team_a.high@pg-cerbos.com', '$2b$12$PJUV7BHtKSRW.eP2CGwlUOE.mEsnmWPTrFXDzWbPWq2u89093WkAq', 'High Clearance', 'Analyst', TRUE)
ON CONFLICT (email) DO UPDATE SET is_active = TRUE;

-- Assign aml_analyst_senior role
INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst.team_a.high@pg-cerbos.com' AND r.name = 'aml_analyst_senior'
ON CONFLICT DO NOTHING;

INSERT INTO user_roles (user_id, role_id) 
SELECT u.id, r.id FROM users u, roles r 
WHERE u.email = 'analyst.team_a.high@pg-cerbos.com' AND r.name = 'aml_analyst'
ON CONFLICT DO NOTHING;

-- Add user attributes for high clearance Team A analyst
INSERT INTO user_attributes (user_id, team, region, clearance_level, department) VALUES
    ((SELECT id FROM users WHERE email = 'analyst.team_a.high@pg-cerbos.com'), 
     'Team A', 'US', 3, 'AML')
ON CONFLICT (user_id) DO UPDATE SET 
    team = EXCLUDED.team,
    region = EXCLUDED.region,
    clearance_level = EXCLUDED.clearance_level,
    department = EXCLUDED.department;
