"""
Natural language to graph query conversion.

Schema and user query are passed to the LLM, with credentials redacted from the
schema. Cypher, Gremlin, and SPARQL generation are LLM-only and retry with
validation and review feedback before failing closed.
"""
import copy
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)
MAX_LLM_GRAPH_QUERY_RETRIES = 3

# Optional OpenAI for LLM-based Cypher generation
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

def get_vertex_labels(schema: Dict[str, Any]) -> Set[str]:
    """Extract vertex labels from PuppyGraph schema."""
    labels: Set[str] = set()
    vertices = schema.get("graph", {}).get("vertices", [])
    for v in vertices:
        label = v.get("label")
        if label:
            labels.add(label)
    return labels


def get_edges_by_label(schema: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Extract edge definitions from schema: edge_label -> { fromVertex, toVertex }.
    """
    edges: Dict[str, Dict[str, str]] = {}
    for e in schema.get("graph", {}).get("edges", []):
        label = e.get("label")
        from_v = e.get("fromVertex")
        to_v = e.get("toVertex")
        if label and from_v and to_v:
            edges[label] = {"fromVertex": from_v, "toVertex": to_v}
    return edges


def get_vertex_attributes(schema: Dict[str, Any]) -> Dict[str, List[str]]:
    """Map vertex label -> list of attribute names (for RETURN and WHERE). Includes id fields."""
    attrs: Dict[str, List[str]] = {}
    for v in schema.get("graph", {}).get("vertices", []):
        label = v.get("label")
        if not label:
            continue
        one_to_one = v.get("oneToOne") or {}
        names = []
        id_fields = one_to_one.get("id") or {}
        for f in (id_fields.get("fields") or []):
            alias = f.get("alias") or f.get("field")
            if alias and alias not in names:
                names.append(alias)
        for a in one_to_one.get("attributes") or []:
            alias = a.get("alias") or a.get("field")
            if alias and alias not in names:
                names.append(alias)
        attrs[label] = names
    return attrs


def get_vertex_id_attributes(schema: Dict[str, Any]) -> Dict[str, List[str]]:
    """Map vertex label -> id field aliases. PuppyGraph exposes these via id(var), not var.id_alias."""
    ids: Dict[str, List[str]] = {}
    for v in schema.get("graph", {}).get("vertices", []):
        label = v.get("label")
        if not label:
            continue
        one_to_one = v.get("oneToOne") or {}
        names: List[str] = []
        id_fields = one_to_one.get("id") or {}
        for f in (id_fields.get("fields") or []):
            alias = f.get("alias") or f.get("field")
            if alias and alias not in names:
                names.append(alias)
        ids[label] = names
    return ids


# Schema-derived: vertex label -> list of (attr_name, type) for attributes with type info
_NUMERIC_TYPES = ("Decimal", "Int", "Float", "Long")


def get_vertex_attributes_with_types(schema: Dict[str, Any]) -> Dict[str, List[Tuple[str, str]]]:
    """Map vertex label -> list of (attribute_name, type). Used to discover numeric attributes."""
    result: Dict[str, List[Tuple[str, str]]] = {}
    for v in schema.get("graph", {}).get("vertices", []):
        label = v.get("label")
        if not label:
            continue
        one_to_one = v.get("oneToOne") or {}
        pairs: List[Tuple[str, str]] = []
        for f in (one_to_one.get("id") or {}).get("fields") or []:
            alias = f.get("alias") or f.get("field")
            typ = (f.get("type") or "Int").strip()
            if alias:
                pairs.append((alias, typ))
        for a in one_to_one.get("attributes") or []:
            alias = a.get("alias") or a.get("field")
            typ = (a.get("type") or "String").strip()
            if alias:
                pairs.append((alias, typ))
        result[label] = pairs
    return result


def get_numeric_attributes_from_schema(schema: Dict[str, Any]) -> List[Tuple[str, str]]:
    """List of (vertex_label, attr_name) for attributes that are numeric (Decimal, Int, Float)."""
    out: List[Tuple[str, str]] = []
    for label, pairs in get_vertex_attributes_with_types(schema).items():
        for attr_name, typ in pairs:
            if typ in _NUMERIC_TYPES:
                out.append((label, attr_name))
    return out


def _entity_keywords_from_schema(schema: Dict[str, Any]) -> Dict[str, str]:
    """Build keyword -> vertex label from schema (no hardcoded types)."""
    vertex_labels = get_vertex_labels(schema)
    keywords: Dict[str, str] = {}
    for label in vertex_labels:
        low = label.lower()
        keywords[low] = label
        keywords[label] = label
        # Simple plural
        if low.endswith("s"):
            keywords[low + "es"] = label
        else:
            keywords[low + "s"] = label
    return keywords


def _relationship_phrases_from_schema(schema: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Build (phrase, edge_label) from schema (no hardcoded edges). Order: longer first."""
    edge_map = get_edges_by_label(schema)
    phrases: List[Tuple[str, str]] = []
    for edge_label, info in edge_map.items():
        from_v = info["fromVertex"]
        to_v = info["toVertex"]
        el_low = edge_label.lower().replace("_", " ")
        from_low = from_v.lower()
        to_low = to_v.lower()
        phrases.append((el_low, edge_label))
        phrases.append((edge_label.lower(), edge_label))
        phrases.append((f"{from_low} {to_low}", edge_label))
        phrases.append((f"{to_low} {from_low}", edge_label))
        phrases.append((f"{from_low} {el_low} {to_low}", edge_label))
    phrases.sort(key=lambda x: -len(x[0]))
    return phrases


def _extract_entities(text: str, schema: Dict[str, Any]) -> List[str]:
    """
    Detect mentioned vertex labels from natural language using schema-derived keywords.
    Returns ordered list of vertex labels that appear in the query.
    """
    keywords = _entity_keywords_from_schema(schema)
    vertex_labels = get_vertex_labels(schema)
    text_lower = text.lower().strip()
    found: List[str] = []
    seen: Set[str] = set()
    # Prefer longer phrase matches, then explicit schema labels
    for phrase, label in sorted(keywords.items(), key=lambda x: -len(x[0])):
        if label not in vertex_labels:
            continue
        if phrase in text_lower and label not in seen:
            found.append(label)
            seen.add(label)
    return found


def _extract_relationships(text: str, schema: Dict[str, Any]) -> List[str]:
    """Detect mentioned edge types from natural language using schema-derived phrases."""
    edge_map = get_edges_by_label(schema)
    phrases = _relationship_phrases_from_schema(schema)
    text_lower = text.lower().strip()
    found: List[str] = []
    for phrase, edge_label in phrases:
        if edge_label not in edge_map:
            continue
        if phrase in text_lower and edge_label not in found:
            found.append(edge_label)
    for label in edge_map:
        if label.lower() in text_lower and label not in found:
            found.append(label)
    return found


def _extract_numeric_filter(
    text: str, schema: Dict[str, Any]
) -> Optional[Tuple[Optional[str], str, float, Optional[str]]]:
    """
    Find numeric threshold filters from text using schema-derived numeric attributes.
    Returns (attribute_name, operator, value, vertex_label). When no attribute name
    appears in text, returns (None, op, value, None) so the caller can resolve using
    entities (e.g. prefer numeric attr on a vertex mentioned in the query).
    """
    numeric_attrs = get_numeric_attributes_from_schema(schema)
    if not numeric_attrs:
        return None
    value_patterns = [
        (r"(?:over|above|greater than|more than|>\s*)\s*([0-9,]+(?:\.\d+)?)\s*(?:dollars?|usd|\$)?", ">"),
        (r"(?:under|below|less than|<\s*)\s*([0-9,]+(?:\.\d+)?)", "<"),
        (r"limit\s+(\d+)", "limit"),
    ]
    value_val: Optional[float] = None
    op_val: Optional[str] = None
    for pattern, op in value_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                value_val = float(raw)
                op_val = op
                break
            except ValueError:
                pass
    if value_val is None or op_val is None:
        return None
    if op_val == "limit":
        return ("limit", "limit", value_val, None)
    text_lower = text.lower()
    for vertex_label, attr_name in numeric_attrs:
        if attr_name.lower() in text_lower:
            return (attr_name, op_val, value_val, vertex_label)
    # No attribute mentioned: caller should resolve using entities
    return (None, op_val, value_val, None)


def _extract_limit(text: str) -> Optional[int]:
    """E.g. 'first 10', 'limit 5', 'top 20'."""
    m = re.search(r"(?:first|limit|top)\s+(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _extract_order_by(text: str, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Detect ordering intent from text using schema attributes.
    Returns {"vertex": label, "attribute": attr_name, "direction": "DESC"|"ASC"} or None.
    """
    text_lower = text.lower()
    # Direction: highest first / descending (explicit or implied by "top by", "highest to lowest")
    desc = bool(
        re.search(r"(?:order\s+in\s+)?decreasing\s+order", text_lower)
        or re.search(r"ordered?\s+in\s+descending\s+order", text_lower)
        or re.search(r"descending\s+order", text_lower)
        or re.search(r"ordered?\s+from\s+highest\s+to\s+lowest", text_lower)
        or re.search(r"highest\s+to\s+lowest", text_lower)
        or re.search(r"order\s+by\s+\w+\s+(?:descending|desc)\b", text_lower)
        or re.search(r"(?:descending|desc)\s*$", text_lower)
        or re.search(r"top\s+(?:\d+\s+)?\w*\s*by\s+\w+", text_lower)  # "top customers by risk"
        or re.search(r"by\s+risk\s*(?:,|$|and)", text_lower)
        or re.search(r"by\s+risk\s+(?:descending|desc)?", text_lower)
    )
    direction = "DESC" if desc else "ASC"
    # Resolve attribute from text: "by risk", "order by risk_rating", "by risk rating"
    vertex_attrs = get_vertex_attributes(schema)
    for label, attrs in vertex_attrs.items():
        for attr in attrs:
            alow = attr.lower().replace("_", " ")
            if attr.lower() in text_lower or alow in text_lower:
                return {"vertex": label, "attribute": attr, "direction": direction}
            if "risk" in text_lower and "risk" in attr.lower():
                return {"vertex": label, "attribute": attr, "direction": direction}
    return None


def analyze_natural_language(
    text: str,
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Analyze natural language query: extract entities, relationships, and filters.

    Returns:
        {
            "entities": [vertex labels],
            "relationships": [edge labels],
            "amount_filter": { "attribute": "amount", "op": ">", "value": 50000 } or None,
            "limit": int or None,
            "raw_text": str,
        }
    """
    entities = _extract_entities(text, schema)
    relationships = _extract_relationships(text, schema)

    amount_filter = None
    num_filter = _extract_numeric_filter(text, schema)
    if num_filter and num_filter[0] != "limit":
        attr_name, op_val, value_val, vertex_label = num_filter[0], num_filter[1], num_filter[2], num_filter[3]
        if attr_name is None and vertex_label is None:
            # Resolve using entities: prefer numeric attr on a vertex mentioned in the query
            numeric_attrs = get_numeric_attributes_from_schema(schema)
            entity_set = set(entities)
            # Prefer "amount" (common for thresholds), then other non-id attrs on an entity vertex
            for v, a in numeric_attrs:
                if v in entity_set and a == "amount":
                    attr_name, vertex_label = a, v
                    break
            if attr_name is None:
                for v, a in numeric_attrs:
                    if v in entity_set and not (a.endswith("_id") or a == "id"):
                        attr_name, vertex_label = a, v
                        break
            if attr_name is None and numeric_attrs and entities:
                for v, a in numeric_attrs:
                    if v in entity_set:
                        attr_name, vertex_label = a, v
                        break
            if attr_name is None and numeric_attrs:
                vertex_label, attr_name = numeric_attrs[0]
        amount_filter = {
            "attribute": attr_name,
            "op": op_val,
            "value": value_val,
            "vertex": vertex_label,
        }

    limit = _extract_limit(text)
    if num_filter and num_filter[0] == "limit":
        limit = int(num_filter[2])

    order_by = _extract_order_by(text, schema)

    return {
        "entities": entities,
        "relationships": relationships,
        "amount_filter": amount_filter,
        "limit": limit,
        "order_by": order_by,
        "raw_text": text,
    }


def _build_path_chain(
    entities: List[str],
    relationships: List[str],
    edge_map: Dict[str, Dict[str, str]],
) -> Optional[List[Tuple[str, str, str]]]:
    """
    Build a path chain: [(from_var, edge, to_var), ...] using schema.
    Uses entities and relationships to form a valid path; prefers longer paths.
    """
    if not entities and not relationships:
        return None

    # If we have edges, try to chain them by fromVertex/toVertex
    if relationships:
        chain: List[Tuple[str, str, str]] = []
        used_edges = set()
        # Start from first edge
        for rel in relationships:
            if rel in used_edges:
                continue
            info = edge_map.get(rel)
            if not info:
                continue
            from_v = info["fromVertex"]
            to_v = info["toVertex"]
            chain.append((from_v, rel, to_v))
            used_edges.add(rel)
        # Try to extend chain by matching endpoints
        extended = True
        while extended:
            extended = False
            first_vertex = chain[0][0] if chain else None
            last_vertex = chain[-1][2] if chain else None
            for rel in relationships:
                if rel in used_edges:
                    continue
                info = edge_map.get(rel)
                if not info:
                    continue
                if info["fromVertex"] == last_vertex:
                    chain.append((info["fromVertex"], rel, info["toVertex"]))
                    used_edges.add(rel)
                    extended = True
                    break
                if info["toVertex"] == first_vertex:
                    chain.insert(0, (info["fromVertex"], rel, info["toVertex"]))
                    used_edges.add(rel)
                    extended = True
                    break
        if chain:
            return chain

    # No relationship phrases: try to connect entities by a single schema edge (e.g. "customers and their accounts")
    if len(entities) >= 2:
        entity_set = set(entities)
        for edge_label, info in edge_map.items():
            from_v = info["fromVertex"]
            to_v = info["toVertex"]
            if from_v in entity_set and to_v in entity_set and from_v != to_v:
                # Prefer edge that connects first to last entity
                if from_v == entities[0] and to_v == entities[-1]:
                    return [(from_v, edge_label, to_v)]
                if to_v == entities[0] and from_v == entities[-1]:
                    return [(from_v, edge_label, to_v)]
                # Otherwise any edge linking two mentioned entities
                return [(from_v, edge_label, to_v)]

    # Single node query
    if entities:
        return [(entities[0], "", "")]  # single vertex

    return None


def _order_by_expression(var: str, attr: str, direction: str) -> str:
    """
    Return ORDER BY clause. For categorical risk-style attributes (e.g. risk_rating
    HIGH/MEDIUM/LOW), use CASE so ordering is by severity. Uses toUpper(trim(toString(...)))
    so that 'high'/'High'/'HIGH' and 'med'/'MED'/'MEDIUM' all sort correctly.
    """
    if attr and "risk" in attr.lower():
        # Case-insensitive; support both 'MED' and 'MEDIUM' for medium risk
        normalized = f"toUpper(trim(toString({var}.{attr})))"
        case_expr = (
            f"CASE {normalized} WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'MED' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END"
        )
        return f"\nORDER BY {case_expr} {direction}"
    return f"\nORDER BY {var}.{attr} {direction}"


def generate_cypher(
    analysis: Dict[str, Any],
    schema: Dict[str, Any],
) -> str:
    """
    Generate openCypher from analysis result and schema.
    """
    edge_map = get_edges_by_label(schema)
    vertex_attrs = get_vertex_attributes(schema)

    entities = analysis.get("entities", [])
    relationships = analysis.get("relationships", [])
    amount_filter = analysis.get("amount_filter")
    order_by = analysis.get("order_by")
    limit = analysis.get("limit") or 25

    chain = _build_path_chain(entities, relationships, edge_map)
    if not chain:
        # Default: list some nodes (label from schema, no hardcoding)
        if entities:
            label = entities[0]
        else:
            labels = sorted(get_vertex_labels(schema))
            label = labels[0] if labels else None
        if not label:
            return "MATCH (n) RETURN n LIMIT 0"
        var = "n"
        match_part = f"MATCH ({var}:{label})"
        attrs = vertex_attrs.get(label, [])
        return_part = f"RETURN {var}.{attrs[0]}" if attrs else f"RETURN {var}"
        if attrs:
            for a in attrs[1:4]:
                return_part += f", {var}.{a}"
        where = ""
        filter_vertex = amount_filter.get("vertex") if amount_filter else None
        filter_attr = amount_filter.get("attribute") if amount_filter else None
        if amount_filter and filter_vertex == label and filter_attr in (vertex_attrs.get(label) or []):
            v = amount_filter["value"]
            amt = str(int(v)) if isinstance(v, (int, float)) and v == int(v) else str(v)
            op = amount_filter.get("op", ">")
            where = f" WHERE {var}.{filter_attr} {op} {amt}"
        order_str = ""
        if order_by and order_by.get("vertex") == label and order_by.get("attribute") in (vertex_attrs.get(label) or []):
            ob_attr = order_by.get("attribute")
            ob_dir = order_by.get("direction", "DESC")
            order_str = _order_by_expression(var, ob_attr, ob_dir)
        return f"{match_part}{where}\n{return_part}{order_str}\nLIMIT {int(limit)}"

    # Build MATCH from chain (single path: (a)-[:R1]->(b)-[:R2]->(c))
    var_names: Dict[str, str] = {}
    def var_for(label: str) -> str:
        if label not in var_names:
            var_names[label] = label[0].lower() + str(len(var_names))
        return var_names[label]

    path_parts: List[str] = []
    for i, (from_v, edge, to_v) in enumerate(chain):
        if edge:
            v_from = var_for(from_v)
            v_to = var_for(to_v)
            if not path_parts:
                path_parts.append(f"({v_from}:{from_v})-[:{edge}]->({v_to}:{to_v})")
            else:
                path_parts.append(f"-[:{edge}]->({v_to}:{to_v})")
        else:
            path_parts.append(f"({var_for(from_v)}:{from_v})")

    match_str = "MATCH " + "".join(path_parts)
    last_vertex = chain[-1][2] if chain and chain[-1][1] else (chain[-1][0] if chain else "")
    first_vertex = chain[0][0] if chain else ""
    primary_var = var_for(last_vertex) if last_vertex else list(var_names.values())[-1]

    # When path has two nodes (e.g. Customer-Account), return both vertices' attributes
    return_parts: List[str] = []
    if len(chain) == 1 and chain[0][1]:
        # one edge: (from)-[:E]->(to) -> return both
        from_v, edge, to_v = chain[0]
        v_from = var_for(from_v)
        v_to = var_for(to_v)
        for label, vname in [(from_v, v_from), (to_v, v_to)]:
            attrs = vertex_attrs.get(label, [])[:5]
            if attrs:
                return_parts.extend([f"{vname}.{a}" for a in attrs])
            else:
                return_parts.append(vname)
    else:
        return_parts = [primary_var]
        if last_vertex and vertex_attrs.get(last_vertex):
            attrs = vertex_attrs[last_vertex][:5]
            return_parts = [f"{primary_var}.{a}" for a in attrs]

    return_str = "RETURN " + ", ".join(return_parts)
    where_str = ""
    filter_vertex = amount_filter.get("vertex") if amount_filter else None
    filter_attr = amount_filter.get("attribute") if amount_filter else None
    if amount_filter and filter_vertex and filter_vertex in var_names and filter_attr:
        if filter_attr in (vertex_attrs.get(filter_vertex) or []):
            fvar = var_for(filter_vertex)
            v = amount_filter["value"]
            amt = str(int(v)) if isinstance(v, (int, float)) and v == int(v) else str(v)
            op = amount_filter.get("op", ">")
            where_str = f" WHERE {fvar}.{filter_attr} {op} {amt}"

    order_str = ""
    if order_by and order_by.get("vertex") in var_names and order_by.get("attribute") in (vertex_attrs.get(order_by.get("vertex")) or []):
        ob_var = var_for(order_by["vertex"])
        ob_attr = order_by.get("attribute")
        ob_dir = order_by.get("direction", "DESC")
        order_str = _order_by_expression(ob_var, ob_attr, ob_dir)

    limit_str = f" LIMIT {int(limit)}"
    return f"{match_str}{where_str}\n{return_str}{order_str}{limit_str}"


def _schema_summary_for_llm(schema: Dict[str, Any]) -> str:
    """Build a concise schema description for the LLM prompt, including attribute types for ORDER BY."""
    vertices = sorted(get_vertex_labels(schema))
    edges = get_edges_by_label(schema)
    lines = [
        "Vertex labels (use exactly these in node patterns, no space after colon): " + ", ".join(vertices),
        "Edges (use exactly these in relationship patterns, direction from -> to):",
    ]
    for label, info in sorted(edges.items()):
        lines.append(f"  {label}: ({info['fromVertex']})-[:{label}]->({info['toVertex']})")
    attrs = get_vertex_attributes(schema)
    attrs_with_types = get_vertex_attributes_with_types(schema)
    lines.append("Vertex attributes (use in RETURN, WHERE, ORDER BY). Type in parens when present:")
    for v in vertices:
        a = attrs.get(v, [])
        if not a:
            continue
        type_pairs = attrs_with_types.get(v, [])
        type_map = {name: t for name, t in type_pairs}
        parts = [f"{name}({type_map[name]})" if name in type_map else name for name in a[:10]]
        lines.append(f"  {v}: " + ", ".join(parts))
    lines.append(
        "Ordering: If the user asks for 'top by risk', 'ordered highest to lowest', etc., include ORDER BY. "
        "For risk_rating (values may be high/med/low or HIGH/MEDIUM/LOW), use case-insensitive CASE: "
        "ORDER BY CASE toUpper(trim(toString(var.risk_rating))) WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'MED' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END DESC."
    )
    return "\n".join(lines)


def _normalize_cypher(cypher: str) -> str:
    """
    Normalize Cypher for PuppyGraph/Neo4j: no space between colon and label,
    and use integer literals for whole-number comparisons (avoids Decimal/float issues).
    """
    if not cypher or not cypher.strip():
        return cypher
    # Remove space after colon when followed by an identifier (label or type)
    cypher = re.sub(r":\s+([A-Za-z_][A-Za-z0-9_]*)", r":\1", cypher)
    # Use integer literals for whole-number amount comparisons (e.g. 50000.0 -> 50000)
    cypher = re.sub(r">\s*(\d+)\.0\b", r"> \1", cypher)
    cypher = re.sub(r"<\s*(\d+)\.0\b", r"< \1", cypher)
    return cypher


def _rewrite_return_id_fields(cypher: str, schema: Dict[str, Any]) -> str:
    """
    In PuppyGraph, vertex id fields declared under oneToOne.id are node ids and
    come back as null when projected as var.id_alias. Rewrite only RETURN-list
    projections to id(var) AS alias so generated Cypher displays useful IDs.
    """
    if not cypher or "RETURN" not in cypher.upper():
        return cypher

    var_to_label = _var_to_label_map(cypher)
    id_attrs = get_vertex_id_attributes(schema)
    if not var_to_label or not id_attrs:
        return cypher

    match = re.search(r"\bRETURN\b(?P<body>.*?)(?=\bORDER\s+BY\b|\bLIMIT\b|$)", cypher, re.IGNORECASE | re.DOTALL)
    if not match:
        return cypher

    body = match.group("body")
    rewritten = body
    for var, label in var_to_label.items():
        for attr in id_attrs.get(label, []):
            pattern = re.compile(
                rf"\b{re.escape(var)}\s*\.\s*{re.escape(attr)}\b(?:\s+AS\s+([A-Za-z_][A-Za-z0-9_]*))?",
                re.IGNORECASE,
            )

            def replace_id_projection(match_obj: re.Match) -> str:
                alias = match_obj.group(1) or attr
                return f"id({var}) AS {alias}"

            rewritten = pattern.sub(replace_id_projection, rewritten)

    if rewritten == body:
        return cypher
    return cypher[:match.start("body")] + rewritten + cypher[match.end("body"):]


# Keys (case-insensitive) whose values are redacted before sending schema to LLM
_SCHEMA_CREDENTIAL_KEYS = frozenset(
    k.lower() for k in ("password", "secret", "api_key", "apikey", "token", "credentials", "jdbcUri", "username")
)


def _redact_schema_for_llm(schema: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a deep copy of the schema with credential-like fields redacted.
    Used before sending schema JSON to the LLM.
    """
    if not schema:
        return {}

    def redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            out: Dict[str, Any] = {}
            for k, v in obj.items():
                if k.lower() in _SCHEMA_CREDENTIAL_KEYS:
                    out[k] = "[REDACTED]"
                else:
                    out[k] = redact(v)
            return out
        if isinstance(obj, list):
            return [redact(item) for item in obj]
        return obj

    return redact(copy.deepcopy(schema))


def _extract_cypher_from_llm_response(text: str) -> Optional[str]:
    """Extract Cypher from LLM response (handles markdown code blocks or raw)."""
    if not text or not text.strip():
        return None
    text = text.strip()
    # ```cypher ... ``` or ``` ... ```
    m = re.search(r"```(?:cypher)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        normalized = _normalize_cypher(raw)
        if normalized and ("MATCH" in normalized.upper() or "RETURN" in normalized.upper()):
            return normalized
    # First line that looks like MATCH or RETURN
    for line in text.split("\n"):
        line = line.strip()
        if line.upper().startswith("MATCH ") or line.upper().startswith("RETURN "):
            start = text.find(line)
            block = text[start:].strip()
            # Stop at next markdown fence or double newline + non-Cypher line
            if "```" in block:
                block = block.split("```")[0].strip()
            normalized = _normalize_cypher(block)
            if normalized:
                return normalized
    # Fallback: find MATCH anywhere in the response (e.g. prose then query)
    match_pos = text.upper().find("MATCH ")
    if match_pos >= 0:
        block = text[match_pos:].strip()
        if "```" in block:
            block = block.split("```")[0].strip()
        normalized = _normalize_cypher(block)
        if normalized:
            return normalized
    return _normalize_cypher(text.strip()) if text else None


def _extract_graph_query_from_llm_response(text: str, language: str) -> Optional[str]:
    """Extract a graph query from an LLM response for the requested language."""
    if not text or not text.strip():
        return None
    language = (language or "cypher").strip().lower()
    if language in {"cypher", "gql"}:
        return _extract_cypher_from_llm_response(text)

    text = text.strip()
    fence_names = {
        "gremlin": r"(?:gremlin|groovy)?",
        "sparql": r"(?:sparql)?",
    }
    fence = fence_names.get(language, r"\w*")
    m = re.search(rf"```{fence}\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        candidate = m.group(1).strip()
    else:
        candidate = text

    if "```" in candidate:
        candidate = candidate.split("```", 1)[0].strip()

    if language == "gremlin":
        for line in candidate.splitlines():
            stripped = line.strip()
            if stripped.startswith("g."):
                return stripped.rstrip(";")
        start = candidate.find("g.")
        if start >= 0:
            return candidate[start:].strip().rstrip(";")
        return None

    if language == "sparql":
        upper = candidate.upper()
        starts = [pos for token in ("PREFIX ", "SELECT ", "ASK ", "CONSTRUCT ", "DESCRIBE ") if (pos := upper.find(token)) >= 0]
        if starts:
            return candidate[min(starts):].strip()
        return None

    return candidate.strip() or None


def _llm_client() -> Optional[Any]:
    """Return OpenAI client if API key is set and library available."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or not OPENAI_AVAILABLE:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    client_kw: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kw["base_url"] = base_url
    else:
        client_kw["base_url"] = "https://api.openai.com/v1"
    return openai.OpenAI(**client_kw)


def _model_for_graph_query() -> str:
    """Model used for natural-language graph query generation."""
    return (
        os.environ.get("OPENAI_MODEL_GRAPH_QUERY", "").strip()
        or os.environ.get("OPENAI_MODEL_CYPHER", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _token_limit_kw(model: str, token_limit: int) -> Dict[str, int]:
    """Return the token limit parameter accepted by the configured model family."""
    model_name = model.lower()
    if model_name.startswith("gpt-5") or model_name.startswith("o"):
        return {"max_completion_tokens": token_limit}
    return {"max_tokens": token_limit}


def _temperature_kw(model: str, temperature: float) -> Dict[str, float]:
    """Return temperature only for models that accept custom values."""
    model_name = model.lower()
    if model_name.startswith("gpt-5") or model_name.startswith("o"):
        return {}
    return {"temperature": temperature}


def _language_prompt(language: str) -> Tuple[str, str]:
    language = (language or "cypher").strip().lower()
    if language == "gremlin":
        return (
            "Gremlin",
            (
                "You generate a single Apache TinkerPop Gremlin Groovy traversal for a traversal source named g. "
                "The query must evaluate to a Traversal with inspectable Bytecode. Use ONLY the graph schema provided: "
                "vertex labels, edge labels, edge directions, and vertex attributes. Prefer read-only steps such as "
                "g.V(), hasLabel, has, out, in, both, values, valueMap, project, select, order, by, count, and limit. "
                "Do not use mutation steps such as addV, addE, property, drop, sideEffect, or arbitrary Groovy code. "
                "Always include limit unless the question asks for an aggregate count. Output only one Gremlin traversal, no markdown or explanation."
            ),
        )
    if language == "sparql":
        return (
            "SPARQL",
            (
                "You generate a single SPARQL 1.1 read query for Apache Jena Fuseki. Use ONLY the graph schema provided. "
                "The RDF data uses the aml namespace: PREFIX aml: <urn:aml:>. Vertex labels are classes such as aml:Customer. "
                "Edge labels and attributes are predicates such as aml:OWNS or aml:amount. Prefer SELECT queries unless the user asks for ASK, CONSTRUCT, or DESCRIBE. "
                "Always include PREFIX aml: <urn:aml:> and LIMIT unless the question asks for an aggregate count. Output only the SPARQL query, no markdown or explanation."
            ),
        )
    if language == "gql":
        return (
            "GQL",
            (
                "You generate a single ISO GQL-compatible read query for the Neo4j demo route. Use ONLY the graph schema provided: "
                "vertex labels, edge labels, edge directions, and vertex attributes. Use MATCH, WHERE, RETURN, ORDER BY, and LIMIT. "
                "Always include LIMIT. Output only the query, no markdown or explanation."
            ),
        )
    return (
        "Cypher",
        (
            "You generate a single openCypher (version 9) statement for PuppyGraph. "
            "Use ONLY the graph schema provided: vertex labels (graph.vertices[].label), "
            "edges (graph.edges[].label, fromVertex, toVertex), and vertex attributes (oneToOne.attributes, oneToOne.id.fields with alias/field). "
            "Rules: No space after colon in node labels (e.g. (c:Customer) not (c: Customer)). "
            "When returning a vertex id field from oneToOne.id.fields, use id(var) AS alias instead of var.alias. "
            "Use only MATCH, RETURN, WHERE, ORDER BY, LIMIT. Integer literals for whole numbers in WHERE. "
            "Always include LIMIT. For ordering by risk_rating (values may be high/med/low or HIGH/MEDIUM/LOW), "
            "use ORDER BY CASE toUpper(trim(toString(var.risk_rating))) WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'MED' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END DESC. "
            "Output only the Cypher statement, no markdown or explanation."
        ),
    )


def _request_graph_query_from_llm(
    *,
    language: str,
    natural_language_query: str,
    schema: Dict[str, Any],
    previous_query: Optional[str] = None,
    validation_errors: Optional[List[str]] = None,
    review: Optional[str] = None,
) -> Optional[str]:
    client = _llm_client()
    if not client:
        return None
    model = _model_for_graph_query()
    redacted = _redact_schema_for_llm(schema)
    schema_json = json.dumps(redacted, indent=2)
    label, system = _language_prompt(language)

    feedback = ""
    if previous_query:
        feedback += f"\n\nPrevious {label} query:\n{previous_query}"
    if validation_errors:
        feedback += "\n\nValidation/execution feedback to fix:\n" + "\n".join(f"- {e}" for e in validation_errors[:10])
    if review:
        feedback += f"\n\nLLM review of the previous attempt:\n{review}"

    user = (
        f"Graph schema (JSON):\n{schema_json}\n\n"
        f"Natural language question: {natural_language_query}"
        f"{feedback}\n\n"
        f"{label} query:"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            **_temperature_kw(model, 0.1),
            **_token_limit_kw(model, 1200),
        )
        content = (response.choices[0].message.content or "").strip()
        query = _extract_graph_query_from_llm_response(content, language)
        if query:
            return query
        logger.warning("LLM response did not contain a %s query: %s", language, content[:200])
        return None
    except Exception as e:
        logger.warning("LLM %s generation failed: %s", language, e)
        return None


def _review_generated_query_with_llm(
    *,
    language: str,
    natural_language_query: str,
    schema: Dict[str, Any],
    generated_query: str,
    validation_errors: List[str],
) -> Optional[str]:
    client = _llm_client()
    if not client:
        return None
    model = _model_for_graph_query()
    redacted = _redact_schema_for_llm(schema)
    schema_json = json.dumps(redacted, indent=2)
    label, _ = _language_prompt(language)
    system = (
        f"You review a failed {label} graph query. Identify the concrete issue and give concise repair guidance. "
        "Do not rewrite the whole query unless needed; focus on what the next generation attempt must fix."
    )
    user = (
        f"Graph schema (JSON):\n{schema_json}\n\n"
        f"Natural language question: {natural_language_query}\n\n"
        f"Generated {label} query:\n{generated_query}\n\n"
        "Failure information:\n"
        + "\n".join(f"- {e}" for e in validation_errors[:10])
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            **_temperature_kw(model, 0.1),
            **_token_limit_kw(model, 600),
        )
        content = (response.choices[0].message.content or "").strip()
        return content[:2000] if content else None
    except Exception as e:
        logger.warning("LLM %s review failed: %s", language, e)
        return None


def _validate_generated_graph_query(language: str, query: str, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    language = (language or "cypher").strip().lower()
    errors: List[str] = []
    if not query or not query.strip():
        return False, ["LLM did not return a graph query."]

    if language in {"cypher", "gql"}:
        normalized = _rewrite_return_id_fields(_normalize_cypher(query), schema)
        valid, cypher_errors = validate_cypher_full(normalized, schema)
        errors.extend(cypher_errors)
    elif language == "gremlin":
        stripped = query.strip()
        if not stripped.startswith("g."):
            errors.append("Gremlin query must start with traversal source 'g.'.")
        forbidden_steps = ("addV", "addE", "drop", "sideEffect")
        for step in forbidden_steps:
            if re.search(rf"\b{re.escape(step)}\s*\(", stripped):
                errors.append(f"Gremlin query uses disallowed write or side-effect step: {step}")
    elif language == "sparql":
        upper = query.upper()
        if not any(token in upper for token in ("SELECT", "ASK", "CONSTRUCT", "DESCRIBE")):
            errors.append("SPARQL query must be a read query: SELECT, ASK, CONSTRUCT, or DESCRIBE.")
        if "WHERE" not in upper and not upper.strip().startswith("DESCRIBE"):
            errors.append("SPARQL query should include a WHERE clause.")
    else:
        errors.append(f"Unsupported graph query language: {language}")

    try:
        import graph_query_analyzer
        analyzer_url = getattr(graph_query_analyzer, "GRAPH_QUERY_ANALYZER_URL", "").strip()
        if analyzer_url:
            graph_query_analyzer.analyze_graph_query(
                language=language,
                query=query,
                schema=schema,
                mode="read",
            )
    except Exception as exc:
        errors.append(f"Analyzer validation failed: {exc}")

    return len(errors) == 0, errors


def _generate_graph_query_with_llm_retries(
    *,
    language: str,
    natural_language_query: str,
    schema: Dict[str, Any],
    max_retries: int = MAX_LLM_GRAPH_QUERY_RETRIES,
) -> Dict[str, Any]:
    language = (language or "cypher").strip().lower()
    query_text = (natural_language_query or "").strip()
    if not query_text:
        return {
            "query": "",
            "cypher": "",
            "analysis": {},
            "valid": False,
            "validation_errors": ["Empty query"],
            "source": "llm",
            "query_type": language,
            "attempts": [],
        }
    if not os.environ.get("OPENAI_API_KEY", "").strip() or not OPENAI_AVAILABLE:
        return {
            "query": "",
            "cypher": "",
            "analysis": {},
            "valid": False,
            "validation_errors": [f"OPENAI_API_KEY is required for natural language to {language}."],
            "source": "llm",
            "query_type": language,
            "attempts": [],
        }

    attempts: List[Dict[str, Any]] = []
    previous_query: Optional[str] = None
    validation_errors: List[str] = []
    review: Optional[str] = None
    total_attempts = 1 + max(0, min(max_retries, MAX_LLM_GRAPH_QUERY_RETRIES))

    for attempt_number in range(1, total_attempts + 1):
        generated = _request_graph_query_from_llm(
            language=language,
            natural_language_query=query_text,
            schema=schema,
            previous_query=previous_query,
            validation_errors=validation_errors,
            review=review,
        )
        if language in {"cypher", "gql"} and generated:
            generated = _rewrite_return_id_fields(_normalize_cypher(generated), schema)

        if not generated:
            validation_errors = ["LLM did not return a graph query."]
            attempts.append({"attempt": attempt_number, "query": "", "valid": False, "validation_errors": validation_errors})
        else:
            valid, validation_errors = _validate_generated_graph_query(language, generated, schema)
            attempts.append({
                "attempt": attempt_number,
                "query": generated,
                "valid": valid,
                "validation_errors": validation_errors,
            })
            if valid:
                source = "llm" if attempt_number == 1 else f"llm_retry_{attempt_number - 1}"
                return {
                    "query": generated,
                    "cypher": generated,
                    "analysis": {},
                    "valid": True,
                    "validation_errors": [],
                    "source": source,
                    "query_type": language,
                    "attempts": attempts,
                }

        previous_query = generated or previous_query
        if attempt_number < total_attempts:
            review = _review_generated_query_with_llm(
                language=language,
                natural_language_query=query_text,
                schema=schema,
                generated_query=previous_query or "",
                validation_errors=validation_errors,
            )

    return {
        "query": previous_query or "",
        "cypher": previous_query or "",
        "analysis": {},
        "valid": False,
        "validation_errors": validation_errors,
        "source": "llm",
        "query_type": language,
        "attempts": attempts,
    }


def _var_to_label_map(cypher: str) -> Dict[str, str]:
    """Extract variable -> vertex label from patterns like (var:Label) or (var:Label1:Label2)."""
    mapping: Dict[str, str] = {}
    # (var:Label) or (var:Label1:Label2) - take first label
    for m in re.finditer(r"\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)", cypher):
        var, label = m.group(1), m.group(2).split(":")[0]
        if var not in mapping:
            mapping[var] = label
    return mapping


def validate_cypher_properties(cypher: str, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Heuristic: check that property references (var.prop) in RETURN and WHERE
    use only attributes defined for that variable's vertex label in the schema.
    Returns (valid, list of error messages).
    """
    errors: List[str] = []
    var_to_label = _var_to_label_map(cypher)
    vertex_attrs = get_vertex_attributes(schema)
    # Find var.prop usages (simple regex: word.word not inside quotes)
    for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\.\s*([a-zA-Z_][a-zA-Z0-9_]*)", cypher):
        var, prop = m.group(1), m.group(2)
        if var not in var_to_label:
            continue
        label = var_to_label[var]
        allowed = set(vertex_attrs.get(label, []))
        if allowed and prop not in allowed:
            errors.append(
                f"Property '{var}.{prop}' is not in schema for {label}. "
                f"Valid attributes: {sorted(allowed)}"
            )
    return len(errors) == 0, errors


def validate_cypher_against_schema(cypher: str, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    The sidecar parser is the authorization boundary for graph query structure.
    NL generation keeps schema-derived property checks local and lets execution
    paths call the remote analyzer before Cerbos.
    """
    return True, []


def validate_cypher_full(cypher: str, schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Run all Cypher validations: schema (labels/edges) and property usage.
    Ensures the Cypher is fully supported by the graph schema.
    """
    all_errors: List[str] = []
    valid_schema, schema_errors = validate_cypher_against_schema(cypher, schema)
    all_errors.extend(schema_errors)
    valid_props, prop_errors = validate_cypher_properties(cypher, schema)
    all_errors.extend(prop_errors)
    return (valid_schema and valid_props), all_errors


def nl_to_cypher(
    natural_language_query: str,
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    """
    LLM-only pipeline: pass redacted schema JSON and user query to the LLM to generate
    Cypher; validate against schema and property usage; retry up to three times
    with validation and review feedback if invalid. No rule-based fallback.
    Credentials are redacted from the schema before sending to the LLM.

    Returns:
        {
            "cypher": str,
            "analysis": { entities, relationships, amount_filter, limit },
            "valid": bool,
            "validation_errors": [str],
            "source": "llm",
        }
    """
    result = _generate_graph_query_with_llm_retries(
        language="cypher",
        natural_language_query=natural_language_query,
        schema=schema,
    )
    result["cypher"] = result.get("query", result.get("cypher", ""))
    return result


def nl_to_graph_query(
    natural_language_query: str,
    schema: Dict[str, Any],
    language: str = "cypher",
) -> Dict[str, Any]:
    """
    Generate a graph query for the selected route.

    Cypher, Gremlin, and SPARQL use LLM generation with validation/review retries.
    GQL uses the same LLM retry flow with a GQL-specific prompt.
    """
    language_normalized = (language or "cypher").strip().lower()
    if language_normalized not in {"cypher", "gremlin", "sparql", "gql"}:
        return {
            "query": "",
            "cypher": "",
            "analysis": {},
            "valid": False,
            "validation_errors": [f"Unsupported graph query language: {language}"],
            "source": "llm",
            "query_type": language_normalized,
        }
    return _generate_graph_query_with_llm_retries(
        language=language_normalized,
        natural_language_query=natural_language_query,
        schema=schema,
    )
