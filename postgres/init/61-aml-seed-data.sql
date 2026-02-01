-- AML PoC Seed Data
-- Creates demo data for the AML use case workflow:
-- Alert → Case → Transaction expansion → Notes → SAR

\c demo_data;

-- ============================================================================
-- Seed Customers
-- ============================================================================

INSERT INTO aml.customer (customer_id, name, risk_rating, pep_flag) VALUES
(1, 'John Smith', 'high', TRUE),
(2, 'Jane Doe', 'med', FALSE),
(3, 'Robert Johnson', 'low', FALSE),
(4, 'Maria Garcia', 'high', FALSE),
(5, 'David Lee', 'med', TRUE)
ON CONFLICT (customer_id) DO NOTHING;

-- ============================================================================
-- Seed Accounts
-- ============================================================================

INSERT INTO aml.account (account_id, customer_id, type, status) VALUES
(101, 1, 'checking', 'active'),
(102, 1, 'savings', 'active'),
(201, 2, 'checking', 'active'),
(202, 2, 'savings', 'active'),
(301, 3, 'checking', 'active'),
(401, 4, 'checking', 'active'),
(402, 4, 'savings', 'active'),
(501, 5, 'checking', 'active')
ON CONFLICT (account_id) DO NOTHING;

-- ============================================================================
-- Seed Transactions
-- ============================================================================

INSERT INTO aml.transaction (txn_id, from_account_id, to_account_id, amount, timestamp, channel, country) VALUES
-- High-value transactions for John Smith (customer 1)
(1001, 101, 201, 50000.00, '2024-01-15 10:30:00+00', 'wire', 'US'),
(1002, 101, 301, 75000.00, '2024-01-16 14:20:00+00', 'wire', 'US'),
(1003, 102, 401, 100000.00, '2024-01-17 09:15:00+00', 'wire', 'US'),
-- Normal transactions
(1004, 201, 301, 500.00, '2024-01-18 11:00:00+00', 'ach', 'US'),
(1005, 301, 401, 1200.00, '2024-01-19 15:30:00+00', 'ach', 'US'),
-- More high-value for Maria Garcia (customer 4)
(1006, 401, 501, 60000.00, '2024-01-20 08:45:00+00', 'wire', 'US'),
(1007, 402, 101, 80000.00, '2024-01-21 13:20:00+00', 'wire', 'US'),
-- Cross-border transaction
(1008, 101, 201, 45000.00, '2024-01-22 10:00:00+00', 'wire', 'MX')
ON CONFLICT (txn_id) DO NOTHING;

-- ============================================================================
-- Seed Alerts
-- ============================================================================

INSERT INTO aml.alert (alert_id, alert_type, created_at, severity, status, primary_customer_id, primary_account_id) VALUES
(1, 'high_value_transaction', '2024-01-15 11:00:00+00', 'high', 'new', 1, 101),
(2, 'pep_transaction', '2024-01-16 15:00:00+00', 'medium', 'triaged', 1, 101),
(3, 'rapid_movement', '2024-01-17 10:00:00+00', 'high', 'escalated', 1, 102),
(4, 'high_value_transaction', '2024-01-20 09:00:00+00', 'high', 'new', 4, 401),
(5, 'cross_border', '2024-01-22 11:00:00+00', 'medium', 'new', 1, 101)
ON CONFLICT (alert_id) DO NOTHING;

-- ============================================================================
-- Seed Cases
-- ============================================================================

INSERT INTO aml.case (case_id, status, priority, created_at, owner_user_id, team, source_alert_id) VALUES
(1, 'open', 'high', '2024-01-17 10:30:00+00', 'analyst1', 'Team A', 3),
(2, 'open', 'medium', '2024-01-20 09:30:00+00', 'analyst2', 'Team B', 4),
(3, 'closed', 'low', '2024-01-16 16:00:00+00', 'analyst1', 'Team A', 2)
ON CONFLICT (case_id) DO NOTHING;

-- ============================================================================
-- Seed Case Notes
-- ============================================================================

INSERT INTO aml.case_note (note_id, case_id, author_user_id, created_at, text) VALUES
(1, 1, 'analyst1', '2024-01-17 10:35:00+00', 'Initial review: Multiple high-value transactions detected. Expanding transaction network.'),
(2, 1, 'analyst1', '2024-01-17 11:00:00+00', 'Found connections to accounts 201, 301, 401. Customer is PEP.'),
(3, 1, 'analyst1', '2024-01-17 14:00:00+00', 'Escalating to manager for SAR decision. Total suspicious activity: $300,000.'),
(4, 2, 'analyst2', '2024-01-20 09:35:00+00', 'Reviewing high-value transaction from customer 4.'),
(5, 3, 'analyst1', '2024-01-16 16:05:00+00', 'False positive - PEP transaction was legitimate business activity.')
ON CONFLICT (note_id) DO NOTHING;

-- ============================================================================
-- Seed SARs
-- ============================================================================

INSERT INTO aml.sar (sar_id, case_id, status, created_at, submitted_at) VALUES
(1, 1, 'draft', '2024-01-17 14:30:00+00', NULL)
ON CONFLICT (sar_id) DO NOTHING;
