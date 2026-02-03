#!/bin/bash
# Validate PuppyGraph schema against PostgreSQL database

set -e

echo "=== PuppyGraph Schema Validation ==="
echo ""

# Check database connection
echo "1. Testing database connectivity..."
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Database connection successful"
else
    echo "   ❌ Database connection failed"
    exit 1
fi

echo ""
echo "2. Verifying tables exist..."
TABLES=("customer" "account" "transaction" "alert" "case" "case_note" "sar")
for table in "${TABLES[@]}"; do
    EXISTS=$(docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'aml' AND table_name = '$table';")
    if [ "$EXISTS" -gt 0 ]; then
        echo "   ✅ Table 'aml.$table' exists"
    else
        echo "   ❌ Table 'aml.$table' NOT FOUND"
    fi
done

echo ""
echo "3. Verifying edge table columns..."
echo "   Checking OWNS edge (account table)..."
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -t -c "
SELECT 
    CASE WHEN COUNT(*) = 3 THEN '✅' ELSE '❌' END as status,
    'Columns: account_id, customer_id, account_id' as expected
FROM information_schema.columns 
WHERE table_schema = 'aml' 
  AND table_name = 'account' 
  AND column_name IN ('account_id', 'customer_id');
" | xargs

echo "   Checking SENT_TXN edge (transaction table)..."
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -t -c "
SELECT 
    CASE WHEN COUNT(*) = 2 THEN '✅' ELSE '❌' END as status,
    'Columns: txn_id, from_account_id' as expected
FROM information_schema.columns 
WHERE table_schema = 'aml' 
  AND table_name = 'transaction' 
  AND column_name IN ('txn_id', 'from_account_id');
" | xargs

echo "   Checking TO_ACCOUNT edge (transaction table)..."
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -t -c "
SELECT 
    CASE WHEN COUNT(*) = 2 THEN '✅' ELSE '❌' END as status,
    'Columns: txn_id, to_account_id, account_id' as expected
FROM information_schema.columns 
WHERE table_schema = 'aml' 
  AND table_name = 'transaction' 
  AND column_name IN ('txn_id', 'to_account_id', 'account_id');
" | xargs

echo ""
echo "4. Checking for missing columns in edge mappings..."
echo "   ⚠️  TO_ACCOUNT edge references 'account_id' in transaction table"
ACCOUNT_ID_EXISTS=$(docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = 'aml' AND table_name = 'transaction' AND column_name = 'account_id';")
if [ "$ACCOUNT_ID_EXISTS" -eq 0 ]; then
    echo "   ❌ Column 'account_id' does NOT exist in transaction table!"
    echo "   💡 This is likely causing the validation error"
else
    echo "   ✅ Column exists"
fi

echo ""
echo "5. Verifying primary keys..."
for table in "${TABLES[@]}"; do
    PK=$(docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -t -c "SELECT COUNT(*) FROM information_schema.table_constraints WHERE table_schema = 'aml' AND table_name = '$table' AND constraint_type = 'PRIMARY KEY';")
    if [ "$PK" -gt 0 ]; then
        echo "   ✅ Table 'aml.$table' has primary key"
    else
        echo "   ❌ Table 'aml.$table' missing primary key"
    fi
done

echo ""
echo "6. Checking data exists..."
docker exec pg-cerbos-postgres14 psql -U postgres -d demo_data -c "
SELECT 
    'customer' as table_name, COUNT(*) as row_count FROM aml.customer
UNION ALL
SELECT 'account', COUNT(*) FROM aml.account
UNION ALL
SELECT 'transaction', COUNT(*) FROM aml.transaction
UNION ALL
SELECT 'alert', COUNT(*) FROM aml.alert
UNION ALL
SELECT 'case', COUNT(*) FROM aml.case
UNION ALL
SELECT 'case_note', COUNT(*) FROM aml.case_note
UNION ALL
SELECT 'sar', COUNT(*) FROM aml.sar;
"

echo ""
echo "=== Validation Complete ==="
