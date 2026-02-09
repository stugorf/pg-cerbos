"""
Unit tests for natural language to Cypher conversion.

Tests schema parsing, NL analysis, Cypher generation, and validation
against the PuppyGraph AML schema. The nl_to_cypher pipeline is LLM-only;
pipeline tests that require valid Cypher are skipped when OPENAI_API_KEY is not set.
"""
import json
import os
import pytest

# Skip pipeline tests that need LLM when OPENAI_API_KEY is not set
requires_llm = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY", "").strip(),
    reason="OPENAI_API_KEY required for LLM-only nl_to_cypher pipeline",
)

from nl_to_cypher import (
    get_vertex_labels,
    get_edges_by_label,
    get_vertex_attributes,
    analyze_natural_language,
    generate_cypher,
    validate_cypher_against_schema,
    validate_cypher_full,
    nl_to_cypher,
    _normalize_cypher,
    _redact_schema_for_llm,
)


# Minimal AML-like schema for tests (matches puppygraph/aml-schema.json structure)
def _load_aml_schema() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "..", "puppygraph", "aml-schema.json")
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    # Inline minimal schema if file not present
    return {
        "graph": {
            "vertices": [
                {"label": "Customer", "oneToOne": {"attributes": [{"alias": "name"}, {"alias": "risk_rating"}]}},
                {"label": "Account", "oneToOne": {"attributes": [{"alias": "customer_id"}, {"alias": "type"}]}},
                {"label": "Transaction", "oneToOne": {"attributes": [{"alias": "amount"}, {"alias": "timestamp"}]}},
                {"label": "Alert", "oneToOne": {"attributes": [{"alias": "alert_type"}]}},
            ],
            "edges": [
                {"label": "OWNS", "fromVertex": "Customer", "toVertex": "Account"},
                {"label": "SENT_TXN", "fromVertex": "Account", "toVertex": "Transaction"},
                {"label": "TO_ACCOUNT", "fromVertex": "Transaction", "toVertex": "Account"},
                {"label": "FLAGS_CUSTOMER", "fromVertex": "Alert", "toVertex": "Customer"},
            ],
        }
    }


@pytest.fixture
def schema():
    return _load_aml_schema()


class TestSchemaHelpers:
    """Tests for schema extraction helpers."""

    def test_redact_schema_removes_credentials(self, schema):
        """Credentials (password, username, jdbcUri, etc.) must be redacted before sending to LLM."""
        redacted = _redact_schema_for_llm(schema)
        # Original schema may have catalogs with jdbc
        catalogs = redacted.get("catalogs") or []
        for cat in catalogs:
            jdbc = cat.get("jdbc") or {}
            for key in ("password", "username", "jdbcUri"):
                if key in jdbc:
                    assert jdbc[key] == "[REDACTED]", f"{key} should be redacted"
        # Graph structure preserved
        assert "graph" in redacted
        assert "vertices" in redacted["graph"]
        assert any(v.get("label") == "Customer" for v in redacted["graph"]["vertices"])

    def test_get_vertex_labels(self, schema):
        labels = get_vertex_labels(schema)
        assert "Customer" in labels
        assert "Account" in labels
        assert "Transaction" in labels
        assert "Alert" in labels

    def test_get_edges_by_label(self, schema):
        edges = get_edges_by_label(schema)
        assert "OWNS" in edges
        assert edges["OWNS"]["fromVertex"] == "Customer"
        assert edges["OWNS"]["toVertex"] == "Account"
        assert "SENT_TXN" in edges
        assert edges["SENT_TXN"]["fromVertex"] == "Account"
        assert edges["SENT_TXN"]["toVertex"] == "Transaction"

    def test_get_vertex_attributes(self, schema):
        attrs = get_vertex_attributes(schema)
        assert "Customer" in attrs
        assert "name" in attrs["Customer"]


class TestAnalyzeNaturalLanguage:
    """Tests for NL analysis."""

    def test_entities_customers(self, schema):
        analysis = analyze_natural_language("Show me all customers", schema)
        assert "Customer" in analysis["entities"]

    def test_entities_transactions(self, schema):
        analysis = analyze_natural_language("List transactions", schema)
        assert "Transaction" in analysis["entities"]

    def test_relationships_owns(self, schema):
        analysis = analyze_natural_language("Customers who own accounts", schema)
        assert "OWNS" in analysis["relationships"] or "Customer" in analysis["entities"]

    def test_amount_filter(self, schema):
        analysis = analyze_natural_language("Transactions over 50000", schema)
        assert analysis.get("amount_filter") is not None or "Transaction" in analysis["entities"]

    def test_limit(self, schema):
        analysis = analyze_natural_language("First 10 customers", schema)
        assert analysis.get("limit") == 10


class TestGenerateCypher:
    """Tests for Cypher generation."""

    def test_single_vertex(self, schema):
        analysis = {"entities": ["Customer"], "relationships": [], "amount_filter": None, "limit": 10}
        cypher = generate_cypher(analysis, schema)
        assert "MATCH" in cypher
        assert "Customer" in cypher
        assert "RETURN" in cypher
        assert "LIMIT" in cypher

    def test_path_customer_account(self, schema):
        analysis = {"entities": ["Customer", "Account"], "relationships": ["OWNS"], "amount_filter": None, "limit": 10}
        cypher = generate_cypher(analysis, schema)
        assert "OWNS" in cypher
        assert "Customer" in cypher
        assert "Account" in cypher


class TestValidateCypher:
    """Tests for schema validation of Cypher."""

    def test_valid_cypher(self, schema):
        cypher = "MATCH (c:Customer)-[:OWNS]->(a:Account) RETURN c.name, a LIMIT 10"
        valid, errors = validate_cypher_against_schema(cypher, schema)
        assert valid is True
        assert len(errors) == 0

    def test_invalid_label(self, schema):
        cypher = "MATCH (x:NonExistentVertex) RETURN x"
        valid, errors = validate_cypher_against_schema(cypher, schema)
        assert valid is False
        assert any("NonExistentVertex" in e for e in errors)

    def test_invalid_relationship(self, schema):
        cypher = "MATCH (c:Customer)-[:INVALID_EDGE]->(a:Account) RETURN c"
        valid, errors = validate_cypher_against_schema(cypher, schema)
        assert valid is False
        assert any("INVALID_EDGE" in e for e in errors)

    def test_order_by_case_passes_validation(self, schema):
        """ORDER BY with CASE for risk_rating (case-insensitive) must pass property validation."""
        cypher = (
            "MATCH (c:Customer) WHERE c.risk_rating IS NOT NULL "
            "RETURN c.name, c.risk_rating ORDER BY "
            "CASE toUpper(trim(toString(c.risk_rating))) WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'MED' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END DESC LIMIT 25"
        )
        valid, errors = validate_cypher_full(cypher, schema)
        assert valid is True, errors


class TestNlToCypherPipeline:
    """Full pipeline tests."""

    def test_empty_query(self, schema):
        result = nl_to_cypher("", schema)
        assert result["valid"] is False
        assert "Empty" in str(result.get("validation_errors", []))
        assert result["source"] == "llm"

    def test_no_api_key_returns_error(self, schema):
        """Without OPENAI_API_KEY, pipeline returns valid=False and required message."""
        key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            result = nl_to_cypher("Show me customers", schema)
            assert result["valid"] is False
            assert result["source"] == "llm"
            assert "OPENAI_API_KEY" in str(result.get("validation_errors", []))
        finally:
            if key is not None:
                os.environ["OPENAI_API_KEY"] = key

    @requires_llm
    def test_customers_query(self, schema):
        result = nl_to_cypher("Show me customers", schema)
        assert result["cypher"]
        assert "Customer" in result["cypher"]
        assert result["valid"] is True
        assert result["source"] == "llm"

    @requires_llm
    def test_transactions_over_amount(self, schema):
        result = nl_to_cypher("Transactions over 50000", schema)
        assert result["cypher"]
        assert "Transaction" in result["cypher"]
        assert "50000" in result["cypher"] or "amount" in result["cypher"].lower()
        assert result["valid"] is True

    @requires_llm
    def test_multi_hop_customer_account_transaction(self, schema):
        result = nl_to_cypher("Customers who own accounts that sent transactions over 50000", schema)
        assert result["valid"] is True
        cypher = result["cypher"]
        assert "Customer" in cypher and "OWNS" in cypher and "Account" in cypher
        assert "SENT_TXN" in cypher and "Transaction" in cypher
        assert "50000" in cypher or "amount" in cypher.lower()
        assert "MATCH " in cypher
        assert cypher.count("MATCH ") == 1

    @requires_llm
    def test_order_by_risk_desc(self, schema):
        result = nl_to_cypher("Show me the top 10 customers by risk and order in decreasing order, please.", schema)
        assert result["valid"] is True
        cypher = result["cypher"]
        assert "ORDER BY" in cypher
        assert "risk_rating" in cypher
        assert "DESC" in cypher
        assert "LIMIT 10" in cypher

    @requires_llm
    def test_top_customers_by_risk_highest_to_lowest(self, schema):
        result = nl_to_cypher("Please show me the top customers by risk, ordered from highest to lowest.", schema)
        assert result["valid"] is True
        cypher = result["cypher"]
        assert "ORDER BY" in cypher
        assert "risk_rating" in cypher
        assert "DESC" in cypher

    @requires_llm
    def test_top_10_customers_by_risk_descending(self, schema):
        """User query: top 10 customers by risk ordered in descending order."""
        result = nl_to_cypher("Please show me the top 10 customers by risk ordered in descending order.", schema)
        assert result["valid"] is True, result.get("validation_errors")
        cypher = result["cypher"]
        assert "ORDER BY" in cypher
        assert "risk_rating" in cypher
        assert "DESC" in cypher
        assert "LIMIT 10" in cypher

    @requires_llm
    def test_customers_and_their_accounts(self, schema):
        result = nl_to_cypher("Show me all customers and their accounts", schema)
        assert result["valid"] is True
        cypher = result["cypher"]
        assert "OWNS" in cypher
        assert "Customer" in cypher and "Account" in cypher
        assert "RETURN" in cypher
        assert "customer_id" in cypher or "name" in cypher
        assert "account_id" in cypher


class TestNormalizeCypher:
    """Tests for Cypher normalization."""

    def test_normalize_space_after_colon(self):
        assert _normalize_cypher("(c: Customer)") == "(c:Customer)"
        assert _normalize_cypher("(c: Customer)-[: OWNS]->(a: Account)") == "(c:Customer)-[:OWNS]->(a:Account)"

    def test_normalize_no_change_when_correct(self):
        q = "MATCH (c:Customer) RETURN c LIMIT 5"
        assert _normalize_cypher(q) == q
