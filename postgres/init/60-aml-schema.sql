-- AML PoC Schema
-- Creates tables for Anti-Money Laundering use case:
-- Customer, Account, Transaction, Alert, Case, CaseNote, SAR

\c demo_data;

CREATE SCHEMA IF NOT EXISTS aml;

-- ============================================================================
-- Core Domain Objects
-- ============================================================================

-- Customer table
CREATE TABLE IF NOT EXISTS aml.customer (
    customer_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    risk_rating TEXT NOT NULL CHECK (risk_rating IN ('low', 'med', 'high')),
    pep_flag BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Account table
CREATE TABLE IF NOT EXISTS aml.account (
    account_id SERIAL PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES aml.customer(customer_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Transaction table
CREATE TABLE IF NOT EXISTS aml.transaction (
    txn_id SERIAL PRIMARY KEY,
    from_account_id INTEGER NOT NULL REFERENCES aml.account(account_id) ON DELETE CASCADE,
    to_account_id INTEGER NOT NULL REFERENCES aml.account(account_id) ON DELETE CASCADE,
    amount DECIMAL(15, 2) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    channel TEXT,
    country TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Investigation Objects
-- ============================================================================

-- Alert table
CREATE TABLE IF NOT EXISTS aml.alert (
    alert_id SERIAL PRIMARY KEY,
    alert_type TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status TEXT NOT NULL CHECK (status IN ('new', 'triaged', 'escalated', 'closed')) DEFAULT 'new',
    primary_customer_id INTEGER REFERENCES aml.customer(customer_id) ON DELETE SET NULL,
    primary_account_id INTEGER REFERENCES aml.account(account_id) ON DELETE SET NULL,
    CONSTRAINT alert_has_primary CHECK (
        primary_customer_id IS NOT NULL OR primary_account_id IS NOT NULL
    )
);

-- Case table
CREATE TABLE IF NOT EXISTS aml.case (
    case_id SERIAL PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
    priority TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    owner_user_id TEXT,  -- References user ID from auth system
    team TEXT,
    source_alert_id INTEGER REFERENCES aml.alert(alert_id) ON DELETE SET NULL
);

-- CaseNote table
CREATE TABLE IF NOT EXISTS aml.case_note (
    note_id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES aml.case(case_id) ON DELETE CASCADE,
    author_user_id TEXT NOT NULL,  -- References user ID from auth system
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    text TEXT NOT NULL
);

-- SAR (Suspicious Activity Report) table
CREATE TABLE IF NOT EXISTS aml.sar (
    sar_id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES aml.case(case_id) ON DELETE CASCADE,
    status TEXT NOT NULL CHECK (status IN ('draft', 'submitted')) DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TIMESTAMP WITH TIME ZONE
);

-- ============================================================================
-- Indexes for Performance
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_account_customer_id ON aml.account(customer_id);
CREATE INDEX IF NOT EXISTS idx_transaction_from_account ON aml.transaction(from_account_id);
CREATE INDEX IF NOT EXISTS idx_transaction_to_account ON aml.transaction(to_account_id);
CREATE INDEX IF NOT EXISTS idx_transaction_timestamp ON aml.transaction(timestamp);
CREATE INDEX IF NOT EXISTS idx_alert_primary_customer ON aml.alert(primary_customer_id);
CREATE INDEX IF NOT EXISTS idx_alert_primary_account ON aml.alert(primary_account_id);
CREATE INDEX IF NOT EXISTS idx_alert_status ON aml.alert(status);
CREATE INDEX IF NOT EXISTS idx_case_owner_user_id ON aml.case(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_case_status ON aml.case(status);
CREATE INDEX IF NOT EXISTS idx_case_source_alert ON aml.case(source_alert_id);
CREATE INDEX IF NOT EXISTS idx_case_note_case_id ON aml.case_note(case_id);
CREATE INDEX IF NOT EXISTS idx_sar_case_id ON aml.sar(case_id);

-- ============================================================================
-- Comments for Documentation
-- ============================================================================

COMMENT ON TABLE aml.customer IS 'Customer entities with risk ratings and PEP flags';
COMMENT ON TABLE aml.account IS 'Financial accounts owned by customers';
COMMENT ON TABLE aml.transaction IS 'Financial transactions between accounts';
COMMENT ON TABLE aml.alert IS 'AML alerts generated by monitoring systems';
COMMENT ON TABLE aml.case IS 'Investigation cases opened from alerts';
COMMENT ON TABLE aml.case_note IS 'Notes added by analysts during case investigation';
COMMENT ON TABLE aml.sar IS 'Suspicious Activity Reports submitted for regulatory compliance';
