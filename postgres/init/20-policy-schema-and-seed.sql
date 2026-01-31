\c policy_store;

CREATE TABLE IF NOT EXISTS policies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,            -- bundle path, e.g. 'envoy/authz.rego'
    rego_text TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    published BOOLEAN NOT NULL DEFAULT false,
    bundle_name TEXT NOT NULL DEFAULT 'main',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT DEFAULT 'seed'
);

-- Seed a basic envoy/authz policy that:
-- 1) extracts role from header 'x-role'
-- 2) extracts SQL from body and detects catalog via regex
-- 3) allows analyst_eu to query 'postgres' and sales_ops to query 'iceberg'
INSERT INTO policies (name, path, rego_text, published)
VALUES (
    'envoy_authz_base',
    'envoy/authz.rego',
    $REGO$
package envoy.authz

import future.keywords.if

default allow = {"allowed": false, "headers": {}}

# Read role from header (set it via client or a future IdP)
role := lower(input.attributes.request.http.headers["x-role"])

# Extract first 8KiB body (Envoy forwards it); for Trino SQL POST /v1/statement
sql := base64.decode(input.attributes.request.http.body)  # packed as bytes

# naive catalog detection
catalog := regex.find_string_submatch("(?i)\\bfrom\\s+([a-z0-9_]+)\\.", sql)[1] if {
    re_match("(?i)\\bfrom\\s+[a-z0-9_]+\\.", sql)
}

# Policy: map roles to allowed catalogs
allowed_catalogs_for_role(r) := ac if {
    some ac
    ac := {"analyst_eu": ["postgres"], "sales_ops": ["iceberg"]}[r]
}

allow := {
    "allowed": true,
    "headers": { "x-authz": "opa", "x-role": role }
} if {
    lower(input.attributes.request.http.method) == "post"
    startswith(input.parsed_path, ["v1","statement"])
    role != ""
    catalog != ""
    allowed := allowed_catalogs_for_role(role)
    catalog in allowed
}
$REGO$,
    true
);

-- Create trigger to automatically update updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_policies_updated_at 
    BEFORE UPDATE ON policies 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();