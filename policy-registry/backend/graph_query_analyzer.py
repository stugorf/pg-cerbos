"""
Graph query analysis boundary for authorization.

This module provides the stable backend contract used before Cerbos evaluation.
Production deployments should set GRAPH_QUERY_ANALYZER_URL to a parser service
that uses language-native parsers such as Neo4j/openCypher and Apache Jena ARQ.
Analyzer failures are fail-closed; the backend rejects graph execution when the
sidecar is unavailable or misconfigured.
"""
import os
from typing import Any, Dict, Optional

import requests


ANALYSIS_VERSION = "graph-query-analysis/v1"
GRAPH_QUERY_ANALYZER_URL = os.getenv("GRAPH_QUERY_ANALYZER_URL", "").strip()
GRAPH_QUERY_ANALYZER_TIMEOUT_SECONDS = float(os.getenv("GRAPH_QUERY_ANALYZER_TIMEOUT_SECONDS", "2.5"))


class GraphQueryAnalysisError(RuntimeError):
    """Raised when a graph query cannot be analyzed safely."""

    def __init__(self, message: str, *, status_code: int = 400, details: Optional[dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details or {}


def analyze_graph_query(
    *,
    language: str,
    query: str,
    schema: Optional[Dict[str, Any]] = None,
    mode: str = "read",
    dialect: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Analyze a graph query and return normalized authorization metadata.

    The returned object intentionally contains both normalized v1 fields and the
    legacy Cerbos fields consumed by current policies. This allows policies to
    migrate without weakening enforcement.
    """
    language_normalized = (language or "").strip().lower()
    query_text = (query or "").strip()
    if not query_text:
        raise GraphQueryAnalysisError("Query is required", status_code=400)
    if language_normalized not in {"cypher", "sparql", "gremlin", "gql"}:
        raise GraphQueryAnalysisError(f"Unsupported graph query language: {language}", status_code=400)

    if not GRAPH_QUERY_ANALYZER_URL:
        raise GraphQueryAnalysisError(
            "Graph query analyzer sidecar is not configured. Set GRAPH_QUERY_ANALYZER_URL and ensure the analyzer service is running before executing graph queries.",
            status_code=503,
            details={
                "code": "GRAPH_QUERY_ANALYZER_NOT_CONFIGURED",
                "language": language_normalized,
            },
        )

    return _analyze_with_remote_service(
        language=language_normalized,
        query=query_text,
        schema=schema,
        mode=mode,
        dialect=dialect,
    )


def _analyze_with_remote_service(
    *,
    language: str,
    query: str,
    schema: Optional[Dict[str, Any]],
    mode: str,
    dialect: Optional[str],
) -> Dict[str, Any]:
    payload = {
        "language": language,
        "dialect": dialect,
        "query": query,
        "schema": schema or {},
        "mode": mode,
    }
    try:
        response = requests.post(
            f"{GRAPH_QUERY_ANALYZER_URL.rstrip('/')}/analyze",
            json=payload,
            timeout=GRAPH_QUERY_ANALYZER_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise GraphQueryAnalysisError(
            f"Graph query analyzer sidecar is unavailable or timed out. Confirm GRAPH_QUERY_ANALYZER_URL points to the running analyzer service. Details: {exc}",
            status_code=503,
            details={
                "code": "GRAPH_QUERY_ANALYZER_UNAVAILABLE",
                "analyzer_url": GRAPH_QUERY_ANALYZER_URL,
            },
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise GraphQueryAnalysisError("Graph query analyzer returned invalid JSON", status_code=502) from exc

    if not response.ok:
        if isinstance(body, dict):
            message = body.get("error") or body.get("detail") or "Graph query analysis failed"
            details = body
        else:
            message = "Graph query analyzer returned an error response"
            details = {"response": body}
        raise GraphQueryAnalysisError(message, status_code=response.status_code, details=details)

    return _validate_analysis(body)


def _validate_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(analysis, dict):
        raise GraphQueryAnalysisError("Graph query analyzer returned a non-object response", status_code=502)
    if analysis.get("complete") is False:
        raise GraphQueryAnalysisError(
            "Graph query analysis was incomplete",
            status_code=422,
            details=analysis,
        )
    required = ["analysis_version", "language", "query_type", "query"]
    missing = [field for field in required if field not in analysis]
    if missing:
        raise GraphQueryAnalysisError(
            f"Graph query analysis missing required fields: {', '.join(missing)}",
            status_code=502,
            details=analysis,
        )
    analysis.setdefault("node_labels", list(analysis.get("accessed_node_labels") or []))
    analysis.setdefault("relationship_types", list(analysis.get("accessed_edge_types") or []))
    analysis.setdefault("max_depth", int(analysis.get("max_traversal_depth") or 0))
    analysis.setdefault("has_aggregations", bool(analysis.get("has_aggregation", False)))
    analysis.setdefault("query_pattern", "simple")
    analysis.setdefault("path_variables", [])
    analysis.setdefault("has_where_clause", False)
    analysis.setdefault("has_order_by", False)
    analysis.setdefault("has_limit", analysis.get("limit") is not None)
    analysis.setdefault("estimated_nodes", int(analysis.get("estimated_result_bound") or 0))
    analysis.setdefault("estimated_edges", 0)
    return analysis
