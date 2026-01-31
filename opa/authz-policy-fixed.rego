package envoy.authz

import future.keywords.if
import future.keywords.in

# Default deny
default allow = {
  "allowed": false,
  "headers": {},
  "body": "Access denied: You are not authorized to perform this action."
}

# Allow admin users full access
allow = {
  "allowed": true,
  "headers": {"x-authz": "admin-access", "x-user-id": user_id, "x-user-email": user_email, "x-user-roles": user_roles}
} if {
  "admin" in user_roles
}

# Allow full access users to query both postgres and iceberg
allow = {
  "allowed": true,
  "headers": {"x-authz": "full-access", "x-user-id": user_id, "x-user-email": user_email, "x-user-roles": user_roles}
} if {
  "full_access_user" in user_roles
  input.attributes.request.http.method == "POST"
  startswith(input.attributes.request.http.path, "/v1/statement")
}

# Allow postgres-only users to query only postgres
allow = {
  "allowed": true,
  "headers": {"x-authz": "postgres-only", "x-user-id": user_id, "x-user-email": user_email, "x-user-roles": user_roles}
} if {
  "postgres_only_user" in user_roles
  input.attributes.request.http.method == "POST"
  startswith(input.attributes.request.http.path, "/v1/statement")
  not contains_iceberg_query(parsed_body)
}

# Allow restricted users to query both postgres and iceberg but not SSN fields
allow = {
  "allowed": true,
  "headers": {"x-authz": "restricted-access", "x-user-id": user_id, "x-user-email": user_email, "x-user-roles": user_roles},
  "body": "Access granted but SSN fields will be masked in results."
} if {
  "restricted_user" in user_roles
  input.attributes.request.http.method == "POST"
  startswith(input.attributes.request.http.path, "/v1/statement")
  not contains_ssn_query(parsed_body)
}

# Deny restricted users from querying SSN fields
allow = {
  "allowed": false,
  "headers": {},
  "body": "Access denied: You are not authorized to access SSN fields. Please modify your query to exclude SSN columns."
} if {
  "restricted_user" in user_roles
  input.attributes.request.http.method == "POST"
  startswith(input.attributes.request.http.path, "/v1/statement")
  contains_ssn_query(parsed_body)
}

# Helper functions
contains_iceberg_query(body) if {
  contains(body, "iceberg.")
}

contains_ssn_query(body) if {
  contains(body, "ssn")
}

contains_ssn_query(body) if {
  contains(body, "SSN")
}

contains_ssn_query(body) if {
  contains(body, "social_security")
}

contains_ssn_query(body) if {
  contains(body, "social_security_number")
}

contains_ssn_query(body) if {
  contains(body, "ssn_number")
}

# Parse request body to extract SQL query
parsed_body = input.attributes.request.http.body if {
  input.attributes.request.http.body != null
} else = ""

# Extract user information from headers
user_id = input.attributes.request.http.headers["x-user-id"] if {
  input.attributes.request.http.headers["x-user-id"] != null
} else = ""

user_email = input.attributes.request.http.headers["x-user-email"] if {
  input.attributes.request.http.headers["x-user-email"] != null
} else = ""

user_roles = split(input.attributes.request.http.headers["x-user-roles"], ",") if {
  input.attributes.request.http.headers["x-user-roles"] != null
} else = []

# Validate user authentication
user_authenticated = true if {
  user_id != null
  user_email != null
  user_roles != null
}

# Deny unauthenticated requests
allow = {
  "allowed": false,
  "headers": {},
  "body": "Access denied: Authentication required. Please provide valid user credentials."
} if {
  not user_authenticated
} 