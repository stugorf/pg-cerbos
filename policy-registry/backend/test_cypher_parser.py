"""
Unit tests for Cypher query parser.

Tests the parsing functionality to extract metadata from Cypher queries.
"""
import pytest
from cypher_parser import (
    parse_cypher_query,
    extract_node_labels,
    extract_relationship_types,
    calculate_traversal_depth,
    has_aggregation_functions,
    detect_query_pattern,
    extract_path_variables,
    extract_resource_attributes,
    has_where_clause,
    has_order_by,
    has_limit
)


class TestNodeLabelExtraction:
    """Tests for node label extraction."""
    
    def test_simple_node_label(self):
        query = "MATCH (c:Customer) RETURN c"
        labels = extract_node_labels(query)
        assert "Customer" in labels
        assert len(labels) == 1
    
    def test_multiple_node_labels(self):
        query = "MATCH (c:Customer)-[:OWNS]->(acc:Account) RETURN c, acc"
        labels = extract_node_labels(query)
        assert "Customer" in labels
        assert "Account" in labels
        assert len(labels) == 2
    
    def test_node_with_multiple_labels(self):
        query = "MATCH (n:Customer:Person) RETURN n"
        labels = extract_node_labels(query)
        assert "Customer" in labels
        assert "Person" in labels
    
    def test_node_without_label(self):
        query = "MATCH (n) RETURN n"
        labels = extract_node_labels(query)
        assert len(labels) == 0
    
    def test_complex_query_labels(self):
        query = """
        MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
        RETURN c, acc, txn
        """
        labels = extract_node_labels(query)
        assert "Customer" in labels
        assert "Account" in labels
        assert "Transaction" in labels


class TestRelationshipTypeExtraction:
    """Tests for relationship type extraction."""
    
    def test_simple_relationship(self):
        query = "MATCH (c:Customer)-[:OWNS]->(acc:Account) RETURN c, acc"
        rel_types = extract_relationship_types(query)
        assert "OWNS" in rel_types
        assert len(rel_types) == 1
    
    def test_multiple_relationships(self):
        query = "MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction) RETURN c"
        rel_types = extract_relationship_types(query)
        assert "OWNS" in rel_types
        assert "SENT_TXN" in rel_types
        assert len(rel_types) == 2
    
    def test_bidirectional_relationship(self):
        query = "MATCH (c:Customer)<-[:OWNS]-(acc:Account) RETURN c"
        rel_types = extract_relationship_types(query)
        assert "OWNS" in rel_types
    
    def test_complex_path(self):
        query = """
        MATCH (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
        RETURN c1, txn
        """
        rel_types = extract_relationship_types(query)
        assert "OWNS" in rel_types
        assert "SENT_TXN" in rel_types
        assert "TO_ACCOUNT" in rel_types


class TestTraversalDepth:
    """Tests for traversal depth calculation."""
    
    def test_depth_one(self):
        query = "MATCH (c:Customer)-[:OWNS]->(acc:Account) RETURN c"
        depth = calculate_traversal_depth(query)
        assert depth == 1
    
    def test_depth_two(self):
        query = "MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction) RETURN c"
        depth = calculate_traversal_depth(query)
        assert depth == 2
    
    def test_depth_three(self):
        query = """
        MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
        RETURN c
        """
        depth = calculate_traversal_depth(query)
        assert depth == 3
    
    def test_path_variable_depth(self):
        query = """
        MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
        RETURN path
        """
        depth = calculate_traversal_depth(query)
        assert depth == 3
    
    def test_multiple_match_clauses(self):
        query = """
        MATCH (c:Case)-[:FROM_ALERT]->(a:Alert)
        MATCH (a)-[:FLAGS_CUSTOMER]->(cust:Customer)
        RETURN c, a, cust
        """
        depth = calculate_traversal_depth(query)
        assert depth == 1  # Max depth across all clauses


class TestAggregationFunctions:
    """Tests for aggregation function detection."""
    
    def test_count_function(self):
        query = "MATCH (c:Customer) RETURN COUNT(c)"
        assert has_aggregation_functions(query) is True
    
    def test_sum_function(self):
        query = "MATCH (txn:Transaction) RETURN SUM(txn.amount)"
        assert has_aggregation_functions(query) is True
    
    def test_avg_function(self):
        query = "MATCH (txn:Transaction) RETURN AVG(txn.amount)"
        assert has_aggregation_functions(query) is True
    
    def test_with_clause_aggregation(self):
        query = """
        MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
        WITH cust, COUNT(txn) as txn_count
        RETURN cust, txn_count
        """
        assert has_aggregation_functions(query) is True
    
    def test_no_aggregation(self):
        query = "MATCH (c:Customer) RETURN c.name, c.risk_rating"
        assert has_aggregation_functions(query) is False


class TestQueryPattern:
    """Tests for query pattern detection."""
    
    def test_simple_pattern(self):
        query = "MATCH (c:Customer) RETURN c"
        pattern = detect_query_pattern(query)
        assert pattern == "simple"
    
    def test_path_pattern(self):
        query = "MATCH path = (c:Customer)-[:OWNS]->(acc:Account) RETURN path"
        pattern = detect_query_pattern(query)
        assert pattern == "path"
    
    def test_multi_match_pattern(self):
        query = """
        MATCH (c:Case)-[:FROM_ALERT]->(a:Alert)
        MATCH (a)-[:FLAGS_CUSTOMER]->(cust:Customer)
        RETURN c, a, cust
        """
        pattern = detect_query_pattern(query)
        assert pattern == "multi_match"
    
    def test_with_clause_pattern(self):
        query = """
        MATCH (cust:Customer)-[:OWNS]->(acc:Account)
        WITH cust, COUNT(acc) as acc_count
        RETURN cust, acc_count
        """
        pattern = detect_query_pattern(query)
        assert pattern == "with_clause"


class TestPathVariables:
    """Tests for path variable extraction."""
    
    def test_simple_path_variable(self):
        query = "MATCH path = (c:Customer)-[:OWNS]->(acc:Account) RETURN path"
        path_vars = extract_path_variables(query)
        assert "path" in path_vars
    
    def test_custom_path_variable(self):
        query = "MATCH p = (c:Customer)-[:OWNS]->(acc:Account) RETURN p"
        path_vars = extract_path_variables(query)
        assert "p" in path_vars


class TestResourceAttributes:
    """Tests for resource attribute extraction."""
    
    def test_risk_rating_extraction(self):
        query = "MATCH (c:Customer) WHERE c.risk_rating = 'high' RETURN c"
        attrs = extract_resource_attributes(query)
        assert attrs.get("risk_rating") == "high"
    
    def test_pep_flag_extraction(self):
        query = "MATCH (c:Customer) WHERE c.pep_flag = true RETURN c"
        attrs = extract_resource_attributes(query)
        assert attrs.get("pep_flag") is True
    
    def test_transaction_amount_extraction(self):
        query = "MATCH (txn:Transaction) WHERE txn.amount > 50000 RETURN txn"
        attrs = extract_resource_attributes(query)
        assert attrs.get("transaction_amount_min") == 50000.0
    
    def test_node_property_extraction(self):
        query = "MATCH (c:Customer {pep_flag: true}) RETURN c"
        attrs = extract_resource_attributes(query)
        assert attrs.get("pep_flag") is True
    
    def test_severity_extraction(self):
        query = "MATCH (a:Alert) WHERE a.severity = 'high' RETURN a"
        attrs = extract_resource_attributes(query)
        assert attrs.get("severity") == "high"


class TestQueryClauses:
    """Tests for query clause detection."""
    
    def test_where_clause(self):
        query = "MATCH (c:Customer) WHERE c.risk_rating = 'high' RETURN c"
        assert has_where_clause(query) is True
    
    def test_no_where_clause(self):
        query = "MATCH (c:Customer) RETURN c"
        assert has_where_clause(query) is False
    
    def test_order_by_clause(self):
        query = "MATCH (c:Customer) RETURN c ORDER BY c.name"
        assert has_order_by(query) is True
    
    def test_limit_clause(self):
        query = "MATCH (c:Customer) RETURN c LIMIT 10"
        assert has_limit(query) is True


class TestFullParse:
    """Tests for full query parsing."""
    
    def test_simple_query_parse(self):
        query = "MATCH (c:Customer) RETURN c"
        metadata = parse_cypher_query(query)
        assert "Customer" in metadata["node_labels"]
        assert metadata["max_depth"] == 0
        assert metadata["query_pattern"] == "simple"
    
    def test_complex_query_parse(self):
        query = """
        MATCH (c:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
        WHERE txn.amount > 50000
        RETURN c.name, c.risk_rating, txn.amount
        ORDER BY txn.amount DESC
        LIMIT 10
        """
        metadata = parse_cypher_query(query)
        assert "Customer" in metadata["node_labels"]
        assert "Account" in metadata["node_labels"]
        assert "Transaction" in metadata["node_labels"]
        assert "OWNS" in metadata["relationship_types"]
        assert "SENT_TXN" in metadata["relationship_types"]
        assert metadata["max_depth"] == 2
        assert metadata["has_where_clause"] is True
        assert metadata["has_order_by"] is True
        assert metadata["has_limit"] is True
    
    def test_path_query_parse(self):
        query = """
        MATCH path = (c1:Customer)-[:OWNS]->(acc1:Account)-[:SENT_TXN]->(txn:Transaction)-[:TO_ACCOUNT]->(acc2:Account)
        WHERE txn.amount > 50000
        RETURN path
        """
        metadata = parse_cypher_query(query)
        assert metadata["query_pattern"] == "path"
        assert "path" in metadata["path_variables"]
        assert metadata["max_depth"] == 3
    
    def test_aggregation_query_parse(self):
        query = """
        MATCH (cust:Customer)-[:OWNS]->(acc:Account)-[:SENT_TXN]->(txn:Transaction)
        WHERE txn.amount > 50000
        WITH cust, COUNT(txn) as high_value_count, SUM(txn.amount) as total_amount
        RETURN cust, high_value_count, total_amount
        """
        metadata = parse_cypher_query(query)
        assert metadata["has_aggregations"] is True
        assert metadata["query_pattern"] == "with_clause"
    
    def test_empty_query(self):
        metadata = parse_cypher_query("")
        assert len(metadata["node_labels"]) == 0
        assert metadata["max_depth"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
