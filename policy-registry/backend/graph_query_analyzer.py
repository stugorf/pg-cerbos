"""
Graph query analysis boundary for authorization.

This module provides the stable backend contract used before Cerbos evaluation.
Production deployments should set GRAPH_QUERY_ANALYZER_URL to a parser service
that uses language-native parsers such as Neo4j/openCypher and Apache Jena ARQ.
The local Cypher analyzer exists as a development fallback and preserves the
current regex-based metadata until the sidecar is introduced.
"""
import os
import re
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

    if GRAPH_QUERY_ANALYZER_URL:
        return _analyze_with_remote_service(
            language=language_normalized,
            query=query_text,
            schema=schema,
            mode=mode,
            dialect=dialect,
        )

    if language_normalized == "cypher":
        return _analyze_cypher_locally(query_text, schema=schema, mode=mode, dialect=dialect)

    raise GraphQueryAnalysisError(
        f"{language_normalized} analysis requires GRAPH_QUERY_ANALYZER_URL",
        status_code=503,
        details={"language": language_normalized},
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
            f"Graph query analyzer unavailable: {exc}",
            status_code=503,
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise GraphQueryAnalysisError("Graph query analyzer returned invalid JSON", status_code=502) from exc

    if not response.ok:
        message = body.get("error") or body.get("detail") or "Graph query analysis failed"
        raise GraphQueryAnalysisError(message, status_code=response.status_code, details=body)

    return _validate_analysis(body)


def _analyze_cypher_locally(
    query: str,
    *,
    schema: Optional[Dict[str, Any]],
    mode: str,
    dialect: Optional[str],
) -> Dict[str, Any]:
    try:
        from cypher_parser import parse_cypher_query, extract_resource_attributes
    except ImportError as exc:
        raise GraphQueryAnalysisError("Local Cypher analyzer is not available", status_code=503) from exc

    metadata = parse_cypher_query(query)
    resource_attributes = extract_resource_attributes(query)
    node_labels = sorted(metadata.get("node_labels") or [])
    relationship_types = sorted(metadata.get("relationship_types") or [])
    limit = _extract_limit(query)
    statement_type = _detect_cypher_statement_type(query)
    has_write_operation = statement_type != "read"

    analysis = {
        "analysis_version": ANALYSIS_VERSION,
        "complete": True,
        "language": "cypher",
        "dialect": dialect or "openCypher-compatible",
        "mode": mode,
        "statement_type": statement_type,
        "is_read_only": not has_write_operation,
        "has_write_operation": has_write_operation,
        "accessed_node_labels": node_labels,
        "accessed_edge_types": relationship_types,
        "accessed_properties": [],
        "path_patterns": [],
        "max_traversal_depth": int(metadata.get("max_depth", 0) or 0),
        "has_variable_length_paths": _has_variable_length_path(query),
        "has_aggregation": bool(metadata.get("has_aggregations", False)),
        "has_subquery": _has_subquery(query),
        "has_union": metadata.get("query_pattern") == "union",
        "has_optional_match": bool(re.search(r"\bOPTIONAL\s+MATCH\b", query, re.IGNORECASE)),
        "limit": limit,
        "estimated_result_bound": limit or int(metadata.get("estimated_nodes", 0) or 0),
        "filters": resource_attributes,
        "parameters": sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", query))),
        "warnings": [
            {
                "code": "LOCAL_REGEX_ANALYZER",
                "severity": "warning",
                "security_relevant": False,
                "message": "Development fallback analyzer used; configure GRAPH_QUERY_ANALYZER_URL for production.",
            }
        ],
        # Legacy fields consumed by existing Cerbos policies.
        "query_type": "cypher",
        "query": query,
        "node_labels": node_labels,
        "relationship_types": relationship_types,
        "max_depth": int(metadata.get("max_depth", 0) or 0),
        "has_aggregations": bool(metadata.get("has_aggregations", False)),
        "query_pattern": metadata.get("query_pattern", "simple"),
        "path_variables": metadata.get("path_variables", []),
        "has_where_clause": bool(metadata.get("has_where_clause", False)),
        "has_order_by": bool(metadata.get("has_order_by", False)),
        "has_limit": bool(metadata.get("has_limit", False)),
        "estimated_nodes": int(metadata.get("estimated_nodes", 0) or 0),
        "estimated_edges": int(metadata.get("estimated_edges", 0) or 0),
        **resource_attributes,
    }
    return _validate_analysis(analysis)


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


def _detect_cypher_statement_type(query: str) -> str:
    if re.search(r"\b(CREATE|MERGE|SET|DELETE|DETACH\s+DELETE|REMOVE|DROP|LOAD\s+CSV)\b", query, re.IGNORECASE):
        return "write"
    return "read"


def _extract_limit(query: str) -> Optional[int]:
    match = re.search(r"\bLIMIT\s+(\d+)", query, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _has_variable_length_path(query: str) -> bool:
    return bool(re.search(r"-\[[^\]]*\*\s*\d*(?:\.\.\d*)?[^\]]*\]", query))


def _has_subquery(query: str) -> bool:
    return bool(re.search(r"\bCALL\s*\{", query, re.IGNORECASE))
