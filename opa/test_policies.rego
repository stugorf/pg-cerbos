package test

import future.keywords.if
import future.keywords.in

# Test rules for the authz policy
test_admin_access_allowed if {
  test_input := {
    "user_roles": ["admin"],
    "attributes": {
      "request": {
        "http": {
          "method": "POST",
          "path": "/v1/statement",
          "headers": {
            "x-user-id": "1",
            "x-user-email": "admin@example.com",
            "x-user-roles": "admin"
          }
        }
      }
    }
  }
  
  data.envoy.authz.allow.allowed == true with input as test_input
}

test_restricted_user_ssn_denied if {
  test_input := {
    "user_roles": ["restricted_user"],
    "attributes": {
      "request": {
        "http": {
          "method": "POST",
          "path": "/v1/statement",
          "body": "SELECT ssn FROM person"
        }
      }
    }
  }
  
  data.envoy.authz.allow.allow.allowed == false with input as test_input
}

# Test rules for field security (commented out until policies are loaded together)
# test_ssn_access_admin if {
#   data.envoy.field_security.ssn_access_allowed(["admin"]) == true
# }

# test_ssn_access_restricted if {
#   data.envoy.field_security.ssn_access_allowed(["restricted_user"]) == false
# }

# test_field_mask_ssn_restricted if {
#   data.envoy.field_security.field_mask("ssn", ["restricted_user"]) == "****-**-****"
# }

# test_resource_access_postgres if {
#   data.envoy.field_security.resource_access_allowed("postgres", ["postgres_only_user"]) == true
# }

# test_resource_access_iceberg_postgres_only if {
#   data.envoy.field_security.resource_access_allowed("iceberg", ["postgres_only_user"]) == false
# } 