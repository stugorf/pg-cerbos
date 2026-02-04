#!/bin/bash

# Script to verify and create AML users if they don't exist
# This ensures analyst.junior@pg-cerbos.com and other AML users are available

set -e

echo "🔍 Verifying AML users in database..."

# Check if user exists
USER_EXISTS=$(docker compose exec -T postgres psql -U postgres -d policy_store -t -c \
  "SELECT COUNT(*) FROM users WHERE email = 'analyst.junior@pg-cerbos.com';" 2>/dev/null | tr -d ' ' || echo "0")

if [ "$USER_EXISTS" = "0" ] || [ -z "$USER_EXISTS" ]; then
    echo "⚠️  User analyst.junior@pg-cerbos.com not found. Creating AML users..."
    
    # Run the AML seed data script
    docker compose exec -T postgres psql -U postgres -d policy_store < postgres/init/62-aml-roles-seed-data.sql
    
    # Also ensure user attributes are set
    docker compose exec -T postgres psql -U postgres -d policy_store < postgres/init/41-user-attributes-seed-data.sql
    
    echo "✅ AML users created!"
else
    echo "✅ User analyst.junior@pg-cerbos.com exists"
fi

# Verify the user and show details
echo ""
echo "📋 User Details:"
docker compose exec -T postgres psql -U postgres -d policy_store -c "
SELECT 
    u.email, 
    u.first_name, 
    u.last_name, 
    u.is_active,
    STRING_AGG(r.name, ', ') as roles
FROM users u
LEFT JOIN user_roles ur ON u.id = ur.user_id
LEFT JOIN roles r ON ur.role_id = r.id
WHERE u.email = 'analyst.junior@pg-cerbos.com'
GROUP BY u.id, u.email, u.first_name, u.last_name, u.is_active;
"

echo ""
echo "📋 User Attributes:"
docker compose exec -T postgres psql -U postgres -d policy_store -c "
SELECT 
    u.email,
    ua.team,
    ua.region,
    ua.clearance_level,
    ua.department
FROM users u
LEFT JOIN user_attributes ua ON u.id = ua.user_id
WHERE u.email = 'analyst.junior@pg-cerbos.com';
"

echo ""
echo "🧪 Testing login..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8082/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "analyst.junior@pg-cerbos.com", "password": "user123"}')

if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    echo "✅ Login successful!"
    TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    echo "   Token: ${TOKEN:0:30}..."
else
    echo "❌ Login failed"
    echo "   Response: $LOGIN_RESPONSE"
    echo ""
    echo "💡 Troubleshooting:"
    echo "   1. Check if password hash is correct"
    echo "   2. Verify user is_active = true"
    echo "   3. Check policy-registry-backend logs: docker compose logs policy-registry-backend"
fi
