package envoy.field_security

import future.keywords.if
import future.keywords.in

# Field-level access control for sensitive data

# SSN field access control
ssn_access_allowed(user_roles) if {
  "admin" in user_roles
}

ssn_access_allowed(user_roles) if {
  "full_access_user" in user_roles
}

ssn_access_allowed(user_roles) if {
  "postgres_only_user" in user_roles
}

# Default deny for SSN access
default ssn_access_allowed(user_roles) = false

# Field masking rules
field_mask(field_name, user_roles) = "****-**-****" if {
  field_name == "ssn"
  not ssn_access_allowed(user_roles)
}

field_mask(field_name, user_roles) = field_name if {
  ssn_access_allowed(user_roles)
}

# Resource access control
resource_access_allowed(resource_type, user_roles) if {
  resource_type == "postgres"
}

resource_access_allowed(resource_type, user_roles) if {
  resource_type == "iceberg"
  "admin" in user_roles
}

resource_access_allowed(resource_type, user_roles) if {
  resource_type == "iceberg"
  "full_access_user" in user_roles
}

resource_access_allowed(resource_type, user_roles) if {
  resource_type == "iceberg"
  "restricted_user" in user_roles
}

# Postgres-only users cannot access iceberg
resource_access_allowed(resource_type, user_roles) = false if {
  resource_type == "iceberg"
  "postgres_only_user" in user_roles
} 