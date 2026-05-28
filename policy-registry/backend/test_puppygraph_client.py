from neo4j.graph import Graph, Node

from puppygraph_client import _sanitize_record


def test_sanitize_record_serializes_neo4j_node():
    graph = Graph()
    node = Node(graph, "customer-1", 1, ["Customer"], {"name": "Alice", "risk_rating": "high"})

    sanitized = _sanitize_record({"c": node})

    assert sanitized["c"] == {
        "_type": "node",
        "id": "customer-1",
        "labels": ["Customer"],
        "properties": {"name": "Alice", "risk_rating": "high"},
    }


def test_sanitize_record_recurses_into_collections():
    graph = Graph()
    node = Node(graph, "account-1", 10, ["Account"], {"account_id": 10})

    sanitized = _sanitize_record({"items": [{"node": node}]})

    assert sanitized["items"][0]["node"]["_type"] == "node"
    assert sanitized["items"][0]["node"]["properties"]["account_id"] == 10
