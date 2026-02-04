-- User Attributes Schema
-- This file creates the user_attributes table for Phase 3: Enhanced ABAC
-- Stores team, region, clearance_level, and department attributes for users

-- Create user_attributes table
CREATE TABLE IF NOT EXISTS user_attributes (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    team VARCHAR(100),
    region VARCHAR(100),
    clearance_level INTEGER DEFAULT 1,
    department VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_attributes_team ON user_attributes(team);
CREATE INDEX IF NOT EXISTS idx_user_attributes_region ON user_attributes(region);
CREATE INDEX IF NOT EXISTS idx_user_attributes_clearance ON user_attributes(clearance_level);

-- Create trigger for updated_at timestamp
CREATE TRIGGER update_user_attributes_updated_at 
    BEFORE UPDATE ON user_attributes 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();
