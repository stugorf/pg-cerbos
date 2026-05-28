import pytest

import graph_query_analyzer
from graph_query_analyzer import GraphQueryAnalysisError, analyze_graph_query


def test_local_cypher_analysis_returns_normalized_and_legacy_fields(monkeypatch):
    monkeypatch.setattr(graph_query_analyzer, "GRAPH_QUERY_ANALYZER_URL", "")

    analysis = analyze_graph_query(
        language="cypher",
        query="MATCH (c:Customer {team: 'Team A'})-[:OWNS]->(a:Account) RETURN c, a LIMIT 10",
    )

    assert analysis["analysis_version"] == "graph-query-analysis/v1"
    assert analysis["complete"] is True
    assert analysis["language"] == "cypher"
    assert analysis["is_read_only"] is True
    assert analysis["has_write_operation"] is False
    assert analysis["accessed_node_labels"] == ["Account", "Customer"]
    assert analysis["accessed_edge_types"] == ["OWNS"]
    assert analysis["max_traversal_depth"] == 1
    assert analysis["limit"] == 10
    assert analysis["customer_team"] == "Team A"
    assert analysis["node_labels"] == ["Account", "Customer"]
    assert analysis["relationship_types"] == ["OWNS"]
    assert analysis["max_depth"] == 1


def test_local_cypher_analysis_marks_write_operations(monkeypatch):
    monkeypatch.setattr(graph_query_analyzer, "GRAPH_QUERY_ANALYZER_URL", "")

    analysis = analyze_graph_query(
        language="cypher",
        query="MATCH (c:Customer) SET c.reviewed = true RETURN c",
    )

    assert analysis["statement_type"] == "write"
    assert analysis["is_read_only"] is False
    assert analysis["has_write_operation"] is True


def test_unsupported_language_requires_remote_analyzer(monkeypatch):
    monkeypatch.setattr(graph_query_analyzer, "GRAPH_QUERY_ANALYZER_URL", "")

    with pytest.raises(GraphQueryAnalysisError) as exc:
        analyze_graph_query(
            language="sparql",
            query="SELECT * WHERE { ?s ?p ?o } LIMIT 10",
        )

    assert exc.value.status_code == 503
    assert "requires GRAPH_QUERY_ANALYZER_URL" in str(exc.value)


def test_remote_analyzer_incomplete_response_fails_closed(monkeypatch):
    class Response:
        ok = True
        status_code = 200

        def json(self):
            return {
                "analysis_version": "graph-query-analysis/v1",
                "language": "cypher",
                "query_type": "cypher",
                "query": "MATCH (c:Customer) RETURN c",
                "complete": False,
            }

    monkeypatch.setattr(graph_query_analyzer, "GRAPH_QUERY_ANALYZER_URL", "http://analyzer")
    monkeypatch.setattr(graph_query_analyzer.requests, "post", lambda *args, **kwargs: Response())

    with pytest.raises(GraphQueryAnalysisError) as exc:
        analyze_graph_query(language="cypher", query="MATCH (c:Customer) RETURN c")

    assert exc.value.status_code == 422
    assert "incomplete" in str(exc.value)
