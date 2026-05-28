"""
Graph engine adapter boundary.

The API layer should authorize analyzed graph queries, then dispatch execution
through this module instead of binding directly to one graph database client.
"""
import os
from typing import Any, Dict

from puppygraph_client import get_puppygraph_client

try:
    from neo4j import GraphDatabase
    from puppygraph_client import _sanitize_record
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    _sanitize_record = None
    NEO4J_AVAILABLE = False


GRAPH_ENGINE = os.getenv("GRAPH_ENGINE", "puppygraph").strip().lower()
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "neo4j-password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "").strip() or None


class GraphEngineExecutionError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class GraphEngineAdapter:
    def execute(self, language: str, query: str) -> Dict[str, Any]:
        raise NotImplementedError

    def get_schema(self) -> Dict[str, Any]:
        raise NotImplementedError


class PuppyGraphEngineAdapter(GraphEngineAdapter):
    def __init__(self):
        self.client = get_puppygraph_client()

    def execute(self, language: str, query: str) -> Dict[str, Any]:
        if language == "cypher":
            return self.client.execute_cypher(query)
        if language == "gremlin":
            return self.client.execute_gremlin(query)
        raise GraphEngineExecutionError(
            f"PuppyGraph adapter does not execute {language} queries",
            status_code=501,
        )

    def get_schema(self) -> Dict[str, Any]:
        return self.client.get_schema()


class Neo4jEngineAdapter(GraphEngineAdapter):
    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
        database: str | None = NEO4J_DATABASE,
    ):
        if not NEO4J_AVAILABLE:
            raise GraphEngineExecutionError("Neo4j driver is not available", status_code=503)
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database

    def execute(self, language: str, query: str) -> Dict[str, Any]:
        if language not in {"cypher", "gql"}:
            raise GraphEngineExecutionError(
                f"Neo4j adapter does not execute {language} queries",
                status_code=501,
            )
        driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        try:
            session_kwargs = {"database": self.database} if self.database else {}
            with driver.session(**session_kwargs) as session:
                result = session.run(query)
                records = [_sanitize_record(dict(record)) for record in result]
                return {"results": records, "columns": list(records[0].keys()) if records else []}
        finally:
            driver.close()

    def get_schema(self) -> Dict[str, Any]:
        query = """
        CALL db.labels() YIELD label
        WITH collect(label) AS labels
        CALL db.relationshipTypes() YIELD relationshipType
        RETURN labels, collect(relationshipType) AS relationshipTypes
        """
        driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
        try:
            session_kwargs = {"database": self.database} if self.database else {}
            with driver.session(**session_kwargs) as session:
                record = session.run(query).single()
                if not record:
                    return {"graph": {"vertices": [], "edges": []}}
                labels = record.get("labels") or []
                relationship_types = record.get("relationshipTypes") or []
                return {
                    "graph": {
                        "vertices": [{"label": label} for label in labels],
                        "edges": [{"label": rel_type} for rel_type in relationship_types],
                    }
                }
        finally:
            driver.close()


class UnsupportedGraphEngineAdapter(GraphEngineAdapter):
    def __init__(self, engine: str):
        self.engine = engine

    def execute(self, language: str, query: str) -> Dict[str, Any]:
        raise GraphEngineExecutionError(
            f"Graph engine '{self.engine}' is not configured",
            status_code=501,
        )

    def get_schema(self) -> Dict[str, Any]:
        raise GraphEngineExecutionError(
            f"Graph engine '{self.engine}' schema retrieval is not configured",
            status_code=501,
        )


_graph_engine_adapter: GraphEngineAdapter | None = None


def get_graph_engine_adapter() -> GraphEngineAdapter:
    global _graph_engine_adapter
    if _graph_engine_adapter is None:
        if GRAPH_ENGINE == "puppygraph":
            _graph_engine_adapter = PuppyGraphEngineAdapter()
        elif GRAPH_ENGINE == "neo4j":
            _graph_engine_adapter = Neo4jEngineAdapter()
        else:
            _graph_engine_adapter = UnsupportedGraphEngineAdapter(GRAPH_ENGINE)
    return _graph_engine_adapter
