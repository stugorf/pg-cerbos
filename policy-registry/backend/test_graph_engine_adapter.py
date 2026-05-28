import pytest

from graph_engine_adapter import (
    FusekiEngineAdapter,
    GraphEngineExecutionError,
    Neo4jEngineAdapter,
    PuppyGraphEngineAdapter,
    UnsupportedGraphEngineAdapter,
    get_graph_route,
)


class StubPuppyGraphClient:
    def execute_cypher(self, query):
        return {"engine": "puppygraph", "language": "cypher", "query": query}

    def execute_gremlin(self, query):
        return {"engine": "puppygraph", "language": "gremlin", "query": query}

    def get_schema(self):
        return {"graph": {"vertices": [{"label": "Customer"}], "edges": []}}


def test_puppygraph_adapter_routes_cypher_and_gremlin():
    adapter = PuppyGraphEngineAdapter()
    adapter.client = StubPuppyGraphClient()

    assert adapter.execute("cypher", "MATCH (n) RETURN n")["language"] == "cypher"
    assert adapter.execute("gremlin", "g.V().limit(1)")["language"] == "gremlin"


def test_puppygraph_adapter_rejects_sparql():
    adapter = PuppyGraphEngineAdapter()
    adapter.client = StubPuppyGraphClient()

    with pytest.raises(GraphEngineExecutionError) as exc:
        adapter.execute("sparql", "SELECT * WHERE { ?s ?p ?o }")

    assert exc.value.status_code == 501


def test_neo4j_adapter_rejects_non_cypher_languages_before_connecting():
    adapter = Neo4jEngineAdapter(uri="bolt://example.invalid:7687", user="neo4j", password="password")

    with pytest.raises(GraphEngineExecutionError) as exc:
        adapter.execute("sparql", "SELECT * WHERE { ?s ?p ?o }")

    assert exc.value.status_code == 501


def test_unsupported_adapter_fails_with_501():
    adapter = UnsupportedGraphEngineAdapter("unknown")

    with pytest.raises(GraphEngineExecutionError) as exc:
        adapter.execute("cypher", "MATCH (n) RETURN n")

    assert exc.value.status_code == 501


def test_language_routes_select_demo_backends():
    assert get_graph_route("cypher") == {"language": "cypher", "engine": "puppygraph"}
    assert get_graph_route("gremlin") == {"language": "gremlin", "engine": "puppygraph"}
    assert get_graph_route("gql") == {"language": "gql", "engine": "neo4j"}
    assert get_graph_route("sparql") == {"language": "sparql", "engine": "fuseki"}


def test_fuseki_adapter_rejects_non_sparql():
    adapter = FusekiEngineAdapter(base_url="http://example.invalid", dataset="aml")

    with pytest.raises(GraphEngineExecutionError) as exc:
        adapter.execute("cypher", "MATCH (n) RETURN n")

    assert exc.value.status_code == 501


def test_fuseki_adapter_normalizes_sparql_results(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "head": {"vars": ["customer", "name"]},
                "results": {
                    "bindings": [
                        {
                            "customer": {"type": "uri", "value": "urn:aml:customer/1"},
                            "name": {"type": "literal", "value": "John Smith"},
                        }
                    ]
                },
            }

    def fake_post(*args, **kwargs):
        return Response()

    monkeypatch.setattr("graph_engine_adapter.requests.post", fake_post)
    adapter = FusekiEngineAdapter(base_url="http://fuseki:3030", dataset="aml")

    result = adapter.execute("sparql", "SELECT * WHERE { ?s ?p ?o }")

    assert result["columns"] == ["customer", "name"]
    assert result["results"] == [{"customer": "urn:aml:customer/1", "name": "John Smith"}]
