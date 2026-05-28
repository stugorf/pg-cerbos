import pytest

from graph_engine_adapter import (
    GraphEngineExecutionError,
    Neo4jEngineAdapter,
    PuppyGraphEngineAdapter,
    UnsupportedGraphEngineAdapter,
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
