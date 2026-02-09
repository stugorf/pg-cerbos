"""
Natural language to Cypher conversion.

Schema and user query are passed to the LLM (with credentials redacted from schema);
generated Cypher is validated and retried once on failure. Rule-based generation
is used only when the LLM is unavailable or still invalid after retry.
"""
import copy
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Optional OpenAI for LLM-based Cypher generation
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Optional: use cypher_parser for validation
try:
    from cypher_parser import (
        extract_node_labels,
        extract_relationship_types,
    )
    CYPHER_PARSER_AVAILABLE = True
except ImportError:
    CYPHER_PARSER_AVAILABLE = False


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


def _llm_client() -> Optional[Any]:
    """Return OpenAI client if API key is set and library available."""
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or not OPENAI_AVAILABLE:
        return None
    base_url = os.environ.get("OPENAI_BASE_URL")
    client_kw: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kw["base_url"] = base_url
    return openai.OpenAI(**client_kw)


def _model_for_cypher() -> str:
    """
    Model used for natural-language-to-Cypher generation.
    Prefer OPENAI_MODEL_CYPHER (e.g. stronger model for code), then OPENAI_MODEL, then default.
    """
    return (
        os.environ.get("OPENAI_MODEL_CYPHER", "").strip()
        or os.environ.get("OPENAI_MODEL", "").strip()
        or "gpt-4o-mini"
    )


def _generate_cypher_with_llm(
    natural_language_query: str,
    schema: Dict[str, Any],
) -> Optional[str]:
    """
    Generate Cypher by sending redacted schema JSON and the user query to the LLM.
    Returns Cypher string or None if LLM is unavailable or fails.
    """
    client = _llm_client()
    if not client:
        return None
    model = _model_for_cypher()
    redacted = _redact_schema_for_llm(schema)
    schema_json = json.dumps(redacted, indent=2)

    system = (
        "You generate a single openCypher (version 9) statement for PuppyGraph. "
        "Use ONLY the graph schema provided: vertex labels (graph.vertices[].label), "
        "edges (graph.edges[].label, fromVertex, toVertex), and vertex attributes (oneToOne.attributes, oneToOne.id.fields with alias/field). "
        "Rules: No space after colon in node labels (e.g. (c:Customer) not (c: Customer)). "
        "Use only MATCH, RETURN, WHERE, ORDER BY, LIMIT. Integer literals for whole numbers in WHERE. "
        "Always include LIMIT. For ordering by risk_rating (values may be high/med/low or HIGH/MEDIUM/LOW), "
        "use ORDER BY CASE toUpper(trim(toString(var.risk_rating))) WHEN 'HIGH' THEN 3 WHEN 'MEDIUM' THEN 2 WHEN 'MED' THEN 2 WHEN 'LOW' THEN 1 ELSE 0 END DESC. "
        "Output only the Cypher statement, no markdown or explanation."
    )
    user = (
        f"Graph schema (JSON):\n{schema_json}\n\n"
        f"Natural language question: {natural_language_query}\n\n"
        "Cypher query:"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
            max_tokens=800,
        )
        content = (response.choices[0].message.content or "").strip()
        cypher = _extract_cypher_from_llm_response(content)
        if cypher and ("MATCH" in cypher.upper() or "RETURN" in cypher.upper()):
            return cypher
        logger.warning("LLM response did not contain valid Cypher: %s", content[:200])
        return None
    except Exception as e:
        logger.warning("LLM Cypher generation failed: %s", e)
        return None


def _generate_cypher_with_llm_retry(
    natural_language_query: str,
    schema: Dict[str, Any],
    validation_errors: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Retry Cypher generation with validation errors. Same as _generate_cypher_with_llm
    but includes validation feedback so the LLM can fix the query.
    """
    client = _llm_client()
    if not client:
        return None
    model = _model_for_cypher()
    redacted = _redact_schema_for_llm(schema)
    schema_json = json.dumps(redacted, indent=2)

    system = (
        "You generate openCypher (version 9) for PuppyGraph. Use ONLY the provided schema. "
        "Fix the query so it passes validation. No space after colon in labels. Include LIMIT. "
        "Output only the Cypher statement, no markdown."
    )
    err_block = ""
    if validation_errors:
        err_block = (
            "\n\nThe previous Cypher was rejected. Validation errors:\n"
            + "\n".join(f"- {e}" for e in validation_errors[:8])
            + "\n\nCorrected Cypher query:"
        )
    user = (
        f"Graph schema (JSON):\n{schema_json}\n\n"
        f"Natural language question: {natural_language_query}"
        f"{err_block}"
    )
    if not err_block:
        user += "\n\nCypher query:"
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.1,
            max_tokens=800,
        )
        content = (response.choices[0].message.content or "").strip()
        cypher = _extract_cypher_from_llm_response(content)
        if cypher and ("MATCH" in cypher.upper() or "RETURN" in cypher.upper()):
            return cypher
        return None
    except Exception as e:
        logger.warning("LLM retry failed: %s", e)
        return None


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
    Validate that all node labels and relationship types in the Cypher query
    exist in the schema. Returns (valid, list of error messages).
    """
    errors: List[str] = []
    vertex_labels = get_vertex_labels(schema)
    edge_map = get_edges_by_label(schema)
    valid_edges = set(edge_map.keys())

    if not CYPHER_PARSER_AVAILABLE:
        return True, []

    node_labels = extract_node_labels(cypher)
    rel_types = extract_relationship_types(cypher)

    for label in node_labels:
        if label not in vertex_labels:
            errors.append(f"Vertex label '{label}' is not in the graph schema. Valid: {sorted(vertex_labels)}")
    for r in rel_types:
        if r not in valid_edges:
            errors.append(f"Relationship type '{r}' is not in the graph schema. Valid: {sorted(valid_edges)}")

    return len(errors) == 0, errors


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
    Cypher; validate against schema and property usage; retry once with validation
    errors if invalid. No rule-based fallback. Credentials are redacted from the
    schema before sending to the LLM.

    Returns:
        {
            "cypher": str,
            "analysis": { entities, relationships, amount_filter, limit },
            "valid": bool,
            "validation_errors": [str],
            "source": "llm",
        }
    """
    query = (natural_language_query or "").strip()
    if not query:
        return {
            "cypher": "",
            "analysis": {},
            "valid": False,
            "validation_errors": ["Empty query"],
            "source": "llm",
        }

    cypher: Optional[str] = None
    analysis: Dict[str, Any] = {"entities": [], "relationships": [], "amount_filter": None, "limit": None}
    validation_errors: List[str] = []

    if not os.environ.get("OPENAI_API_KEY", "").strip() or not OPENAI_AVAILABLE:
        return {
            "cypher": "",
            "analysis": analysis,
            "valid": False,
            "validation_errors": ["OPENAI_API_KEY is required for natural language to Cypher."],
            "source": "llm",
        }

    llm_cypher = _generate_cypher_with_llm(query, schema)
    if not llm_cypher:
        # Try rule-based fallback before failing
        try:
            rule_analysis = analyze_natural_language(query, schema)
            rule_cypher = generate_cypher(rule_analysis, schema)
            rule_cypher = _normalize_cypher(rule_cypher)
            rule_valid, _ = validate_cypher_full(rule_cypher, schema)
            if rule_valid:
                return {
                    "cypher": rule_cypher,
                    "analysis": rule_analysis,
                    "valid": True,
                    "validation_errors": [],
                    "source": "rule_based",
                }
        except Exception as e:
            logger.debug("Rule-based fallback after LLM failure: %s", e)
        return {
            "cypher": "",
            "analysis": analysis,
            "valid": False,
            "validation_errors": ["LLM did not return valid Cypher."],
            "source": "llm",
        }

    cypher = _normalize_cypher(llm_cypher)
    valid_full, validation_errors = validate_cypher_full(cypher, schema)
    if valid_full:
        return {
            "cypher": cypher,
            "analysis": analysis,
            "valid": True,
            "validation_errors": [],
            "source": "llm",
        }

    retry_cypher = _generate_cypher_with_llm_retry(query, schema, validation_errors)
    if retry_cypher:
        cypher = _normalize_cypher(retry_cypher)
        valid_retry, retry_errors = validate_cypher_full(cypher, schema)
        if valid_retry:
            return {
                "cypher": cypher,
                "analysis": analysis,
                "valid": True,
                "validation_errors": [],
                "source": "llm",
            }
        validation_errors = retry_errors

    # Rule-based fallback when LLM failed or returned invalid Cypher
    try:
        rule_analysis = analyze_natural_language(query, schema)
        rule_cypher = generate_cypher(rule_analysis, schema)
        rule_cypher = _normalize_cypher(rule_cypher)
        rule_valid, rule_errors = validate_cypher_full(rule_cypher, schema)
        if rule_valid:
            return {
                "cypher": rule_cypher,
                "analysis": rule_analysis,
                "valid": True,
                "validation_errors": [],
                "source": "rule_based",
            }
    except Exception as e:
        logger.debug("Rule-based Cypher fallback failed: %s", e)

    return {
        "cypher": cypher or "",
        "analysis": analysis,
        "valid": False,
        "validation_errors": validation_errors,
        "source": "llm",
    }
