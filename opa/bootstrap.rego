package envoy.authz

import future.keywords.if

default allow = {
  "allowed": false,
  "headers": {}
}

# Minimal permissive bootstrap (deny by default).
# You'll replace/override via bundles from the registry.