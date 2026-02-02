# AML Cypher Query Examples

Example openCypher queries for the AML PoC using PuppyGraph.

## Basic Queries

### 1. Find All High-Value Transactions

```cypher
MATCH (txn:Transaction)
WHERE txn.amount > 50000
RETURN txn.txn_id, txn.amount, txn.timestamp, txn.channel
ORDER BY txn.amount DESC
LIMIT 10
```

### 2. Find Customers with High Risk Rating

```cypher
MATCH (cust:Customer)
WHERE cust.risk_rating = 'high'
RETURN cust.customer_id, cust.name, cust.risk_rating, cust.pep_flag
```

### 3. Find All PEP (Politically Exposed Persons)

```cypher
MATCH (cust:Customer)
WHERE cust.pep_flag = true
RETURN cust.customer_id, cust.name, cust.risk_rating
```

## Transaction Network Queries

### 4. Find Transaction Network for a Customer

```cypher
MATCH (cust:Customer {customer_id: 1})-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
RETURN cust.name, acc.account_id, txn.txn_id, txn.amount, txn.timestamp
ORDER BY txn.timestamp DESC
```

### 5. Find All Transactions Between Two Customers

```cypher
MATCH (c1:Customer {customer_id: 1})-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)<-[:OWNS]-(c2:Customer {customer_id: 2})
RETURN c1.name as from_customer, c2.name as to_customer, txn.amount, txn.timestamp
```

### 6. Find High-Value Transaction Paths (2 hops)

```cypher
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn1:Transaction)-[:TO_ACCOUNT]->(acc2:Account)-[:SENT_TXN]->(txn2:Transaction)
WHERE txn1.amount > 50000 AND txn2.amount > 50000
RETURN c1.name, txn1.amount as first_txn, txn2.amount as second_txn
LIMIT 20
```

## Alert and Case Queries

### 7. Find All Alerts for a Customer

```cypher
MATCH (alert:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer {customer_id: 1})
RETURN alert.alert_id, alert.alert_type, alert.severity, alert.status, alert.created_at
ORDER BY alert.created_at DESC
```

### 8. Trace Alert to Case to SAR

```cypher
MATCH (alert:Alert {alert_id: 1})-[:FROM_ALERT]-(c:Case)-[:RESULTED_IN]->(sar:SAR)
RETURN alert.alert_id, alert.alert_type, c.case_id, c.status, sar.sar_id, sar.status
```

### 9. Find All Cases with Their Investigation Notes

```cypher
MATCH (c:Case {case_id: 1})-[:HAS_NOTE]->(note:CaseNote)
RETURN c.case_id, note.note_id, note.author_user_id, note.created_at, note.text
ORDER BY note.created_at ASC
```

## Complex Investigation Queries

### 10. Expand Transaction Network from a Case

```cypher
MATCH (c:Case {case_id: 1})-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
MATCH (cust)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
RETURN c.case_id, a.alert_id, cust.name, acc.account_id, txn.txn_id, txn.amount, acc2.account_id
ORDER BY txn.amount DESC
```

### 11. Find All Customers Connected to High-Value Transactions

```cypher
MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.amount > 50000
WITH cust, COUNT(txn) as high_value_count, SUM(txn.amount) as total_amount
WHERE high_value_count >= 2
RETURN cust.customer_id, cust.name, cust.risk_rating, high_value_count, total_amount
ORDER BY total_amount DESC
```

### 12. Find Transaction Chains (3+ hops)

```cypher
MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn1:Transaction)-[:TO_ACCOUNT]->(acc2:Account)-[:SENT_TXN]->(txn2:Transaction)-[:TO_ACCOUNT]->(acc3:Account)-[:SENT_TXN]->(txn3:Transaction)
WHERE txn1.amount > 30000 AND txn2.amount > 30000 AND txn3.amount > 30000
RETURN c1.name as start_customer, 
       txn1.amount as first_txn, 
       txn2.amount as second_txn, 
       txn3.amount as third_txn,
       (txn1.amount + txn2.amount + txn3.amount) as total_chain_amount
LIMIT 10
```

### 13. Find Customers with Multiple Accounts and High Activity

```cypher
MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WITH cust, COUNT(DISTINCT acc) as account_count, COUNT(txn) as transaction_count, SUM(txn.amount) as total_volume
WHERE account_count >= 2 AND transaction_count >= 5
RETURN cust.customer_id, cust.name, cust.risk_rating, account_count, transaction_count, total_volume
ORDER BY total_volume DESC
```

### 14. Find Cross-Border Transactions

```cypher
MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WHERE txn.country IS NOT NULL AND txn.country != 'US'
RETURN cust.name, txn.txn_id, txn.amount, txn.country, txn.timestamp
ORDER BY txn.amount DESC
```

### 15. Find Alert-to-Transaction Network (Full Investigation Path)

```cypher
MATCH (alert:Alert {alert_id: 1})-[:FLAGS_CUSTOMER]->(cust:Customer)
MATCH (cust)-[:OWNS]->(acc:Account)
MATCH (acc)-[:SENT_TXN]->(txn:Transaction)
MATCH (txn)-[:TO_ACCOUNT]->(acc2:Account)<-[:OWNS]-(cust2:Customer)
RETURN alert.alert_id, 
       cust.name as flagged_customer,
       txn.txn_id, 
       txn.amount,
       cust2.name as connected_customer,
       txn.timestamp
ORDER BY txn.amount DESC
```

## Aggregation Queries

### 16. Transaction Volume by Customer

```cypher
MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
WITH cust, SUM(txn.amount) as total_volume, COUNT(txn) as transaction_count
RETURN cust.customer_id, cust.name, cust.risk_rating, total_volume, transaction_count
ORDER BY total_volume DESC
```

### 17. Alert Statistics by Type

```cypher
MATCH (alert:Alert)
RETURN alert.alert_type, 
       COUNT(*) as count,
       COUNT(CASE WHEN alert.status = 'new' THEN 1 END) as new_count,
       COUNT(CASE WHEN alert.severity = 'high' THEN 1 END) as high_severity_count
ORDER BY count DESC
```

### 18. Case Investigation Timeline

```cypher
MATCH (c:Case {case_id: 1})-[:FROM_ALERT]->(a:Alert)
MATCH (c)-[:HAS_NOTE]->(note:CaseNote)
OPTIONAL MATCH (c)-[:RESULTED_IN]->(sar:SAR)
RETURN c.case_id,
       a.alert_id,
       a.alert_type,
       COUNT(note) as note_count,
       CASE WHEN sar IS NOT NULL THEN 'Yes' ELSE 'No' END as has_sar
```

## Pattern Matching Queries

### 19. Find Circular Transaction Patterns

```cypher
MATCH (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn1:Transaction)-[:TO_ACCOUNT]->(acc2:Account)<-[:OWNS]-(c2:Customer)
MATCH (c2)-[:OWNS]->(acc2)-[:SENT_TXN]->(txn2:Transaction)-[:TO_ACCOUNT]->(acc1)
WHERE c1.customer_id <> c2.customer_id
RETURN c1.name as customer1, c2.name as customer2, txn1.amount as amount1, txn2.amount as amount2
```

### 20. Find Customers Connected Through Multiple Transactions

```cypher
MATCH (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)<-[:OWNS]-(c2:Customer)
WHERE c1.customer_id < c2.customer_id
WITH c1, c2, COUNT(txn) as connection_count, SUM(txn.amount) as total_flow
WHERE connection_count >= 3
RETURN c1.name as customer1, c2.name as customer2, connection_count, total_flow
ORDER BY total_flow DESC
```

## Using in the UI

1. Navigate to **Graph Query** tab
2. Select **openCypher** from the dropdown
3. Paste one of the queries above
4. Click **Execute Graph Query**
5. View results in the results area

## Notes

- All queries are authorized via Cerbos before execution
- Queries access PostgreSQL data through PuppyGraph's graph mapping
- Results are returned in JSON format
- Execution time is displayed for each query
- See `puppygraph/aml-schema.json` for the complete graph schema
