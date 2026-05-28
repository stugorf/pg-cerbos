"""
Graph engine adapter boundary.

The API layer should authorize analyzed graph queries, then dispatch execution
through this module instead of binding directly to one graph database client.
"""
import os
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests
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
FUSEKI_URL = os.getenv("FUSEKI_URL", "http://fuseki:3030")
FUSEKI_DATASET = os.getenv("FUSEKI_DATASET", "aml")


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
        WITH labels, collect(relationshipType) AS relationshipTypes
        CALL db.schema.nodeTypeProperties() YIELD nodeLabels, propertyName, propertyTypes
        RETURN labels, relationshipTypes,
               collect({labels: nodeLabels, property: propertyName, types: propertyTypes}) AS nodeProperties
        """
        rel_query = """
        MATCH (a)-[r]->(b)
        RETURN DISTINCT labels(a)[0] AS fromLabel, type(r) AS relType, labels(b)[0] AS toLabel
        ORDER BY relType, fromLabel, toLabel
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
                node_properties = record.get("nodeProperties") or []
                attrs_by_label: Dict[str, list] = {label: [] for label in labels}
                for prop in node_properties:
                    for label in prop.get("labels") or []:
                        property_name = prop.get("property")
                        if property_name:
                            attrs_by_label.setdefault(label, []).append({
                                "alias": property_name,
                                "field": property_name,
                                "type": _neo4j_type_to_schema_type(prop.get("types") or []),
                            })
                edge_rows = [dict(row) for row in session.run(rel_query)]
                return {
                    "graph": {
                        "vertices": [
                            {
                                "label": label,
                                "oneToOne": {
                                    "id": {"fields": [{"alias": f"{label.lower()}_id", "field": f"{label.lower()}_id", "type": "String"}]},
                                    "attributes": attrs_by_label.get(label, []),
                                },
                            }
                            for label in labels
                        ],
                        "edges": [
                            {
                                "label": row.get("relType"),
                                "fromVertex": row.get("fromLabel"),
                                "toVertex": row.get("toLabel"),
                            }
                            for row in edge_rows
                        ] or [{"label": rel_type} for rel_type in relationship_types],
                    }
                }
        finally:
            driver.close()


class FusekiEngineAdapter(GraphEngineAdapter):
    def __init__(
        self,
        base_url: str = FUSEKI_URL,
        dataset: str = FUSEKI_DATASET,
    ):
        self.base_url = base_url.rstrip("/")
        self.dataset = dataset.strip("/")

    @property
    def query_url(self) -> str:
        return urljoin(f"{self.base_url}/", f"{self.dataset}/query")

    def execute(self, language: str, query: str) -> Dict[str, Any]:
        if language != "sparql":
            raise GraphEngineExecutionError(
                f"Fuseki adapter does not execute {language} queries",
                status_code=501,
            )
        try:
            response = requests.post(
                self.query_url,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"},
                timeout=30,
            )
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            raise GraphEngineExecutionError(f"Fuseki SPARQL query failed: {exc}", status_code=502) from exc
        except ValueError as exc:
            raise GraphEngineExecutionError("Fuseki returned invalid JSON", status_code=502) from exc

        head_vars = body.get("head", {}).get("vars", [])
        bindings = body.get("results", {}).get("bindings", [])
        rows = []
        for binding in bindings:
            row = {}
            for key in head_vars:
                value = binding.get(key) or {}
                row[key] = value.get("value")
            rows.append(row)
        return {"results": rows, "columns": head_vars}

    def get_schema(self) -> Dict[str, Any]:
        class_query = """
        PREFIX aml: <urn:aml:>
        SELECT DISTINCT ?class WHERE {
          ?s a ?class .
          FILTER(STRSTARTS(STR(?class), "urn:aml:"))
        }
        ORDER BY ?class
        """
        edge_query = """
        PREFIX aml: <urn:aml:>
        SELECT DISTINCT ?fromClass ?predicate ?toClass WHERE {
          ?s a ?fromClass .
          ?s ?predicate ?o .
          ?o a ?toClass .
          FILTER(STRSTARTS(STR(?fromClass), "urn:aml:"))
          FILTER(STRSTARTS(STR(?predicate), "urn:aml:"))
          FILTER(STRSTARTS(STR(?toClass), "urn:aml:"))
        }
        ORDER BY ?predicate ?fromClass ?toClass
        """
        property_query = """
        PREFIX aml: <urn:aml:>
        SELECT DISTINCT ?class ?predicate WHERE {
          ?s a ?class .
          ?s ?predicate ?value .
          FILTER(STRSTARTS(STR(?class), "urn:aml:"))
          FILTER(STRSTARTS(STR(?predicate), "urn:aml:"))
          FILTER(!isIRI(?value))
        }
        ORDER BY ?class ?predicate
        """
        classes = self.execute("sparql", class_query).get("results", [])
        edges = self.execute("sparql", edge_query).get("results", [])
        properties = self.execute("sparql", property_query).get("results", [])

        attrs_by_label: Dict[str, list] = {}
        for prop in properties:
            label = _local_name(prop.get("class"))
            property_name = _local_name(prop.get("predicate"))
            if label and property_name:
                attrs_by_label.setdefault(label, []).append({
                    "alias": property_name,
                    "field": property_name,
                    "type": "String",
                })

        return {
            "graph": {
                "vertices": [
                    {
                        "label": _local_name(row.get("class")),
                        "oneToOne": {
                            "id": {"fields": [{"alias": "iri", "field": "iri", "type": "String"}]},
                            "attributes": attrs_by_label.get(_local_name(row.get("class")), []),
                        },
                    }
                    for row in classes
                    if _local_name(row.get("class"))
                ],
                "edges": [
                    {
                        "label": _local_name(row.get("predicate")),
                        "fromVertex": _local_name(row.get("fromClass")),
                        "toVertex": _local_name(row.get("toClass")),
                    }
                    for row in edges
                    if _local_name(row.get("predicate"))
                ],
            }
        }


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
_graph_engine_adapters: Dict[str, GraphEngineAdapter] = {}


LANGUAGE_ENGINE_ROUTES = {
    "cypher": "puppygraph",
    "gremlin": "puppygraph",
    "gql": "neo4j",
    "sparql": "fuseki",
}


def get_graph_engine_adapter(language: Optional[str] = None) -> GraphEngineAdapter:
    if language:
        engine = LANGUAGE_ENGINE_ROUTES.get(language.strip().lower())
        if engine:
            return _get_adapter_for_engine(engine)
        return UnsupportedGraphEngineAdapter(language)

    global _graph_engine_adapter
    if _graph_engine_adapter is None:
        _graph_engine_adapter = _get_adapter_for_engine(GRAPH_ENGINE)
    return _graph_engine_adapter


def _get_adapter_for_engine(engine: str) -> GraphEngineAdapter:
    engine = (engine or "").strip().lower()
    if engine not in _graph_engine_adapters:
        if engine == "puppygraph":
            _graph_engine_adapters[engine] = PuppyGraphEngineAdapter()
        elif engine == "neo4j":
            _graph_engine_adapters[engine] = Neo4jEngineAdapter()
        elif engine in {"fuseki", "rdf"}:
            _graph_engine_adapters[engine] = FusekiEngineAdapter()
        else:
            _graph_engine_adapters[engine] = UnsupportedGraphEngineAdapter(engine)
    return _graph_engine_adapters[engine]


def get_graph_route(language: str) -> Dict[str, str]:
    language_normalized = (language or "").strip().lower()
    return {
        "language": language_normalized,
        "engine": LANGUAGE_ENGINE_ROUTES.get(language_normalized, "unsupported"),
    }


def _local_name(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if "#" in text:
        return text.rsplit("#", 1)[1]
    if "/" in text:
        return text.rsplit("/", 1)[1]
    if ":" in text:
        return text.rsplit(":", 1)[1]
    return text


def _neo4j_type_to_schema_type(types: list) -> str:
    joined = " ".join(str(t).upper() for t in types)
    if any(token in joined for token in ("INTEGER", "FLOAT", "NUMBER")):
        return "Int"
    if "BOOLEAN" in joined:
        return "Boolean"
    if "DATE" in joined or "TIME" in joined:
        return "DateTime"
    return "String"
