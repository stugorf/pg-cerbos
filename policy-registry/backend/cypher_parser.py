"""
Cypher Query Parser

This module provides parsing functionality for Cypher queries to extract metadata
for authorization purposes. It extracts node labels, relationship types, traversal depth,
query patterns, and resource attributes.

This parser uses regex patterns to extract information from Cypher queries without
requiring a full Cypher parser dependency.
"""
import re
import logging
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


def parse_cypher_query(query: str) -> Dict[str, Any]:
    """
    Parse a Cypher query and extract metadata for authorization.
    
    Args:
        query: Cypher query string
        
    Returns:
        Dictionary containing parsed query metadata:
        - node_labels: Set of node labels found in the query
        - relationship_types: Set of relationship types found
        - max_depth: Maximum traversal depth (number of hops)
        - has_aggregations: Boolean indicating if query has aggregation functions
        - query_pattern: Type of query pattern (simple, path, multi_match, etc.)
        - path_variables: List of path variable names
        - has_where_clause: Boolean indicating if query has WHERE clause
        - has_order_by: Boolean indicating if query has ORDER BY clause
        - has_limit: Boolean indicating if query has LIMIT clause
    """
    if not query or not query.strip():
        return _empty_metadata()
    
    query_normalized = _normalize_query(query)
    
    return {
        "node_labels": extract_node_labels(query_normalized),
        "relationship_types": extract_relationship_types(query_normalized),
        "max_depth": calculate_traversal_depth(query_normalized),
        "has_aggregations": has_aggregation_functions(query_normalized),
        "query_pattern": detect_query_pattern(query_normalized),
        "path_variables": extract_path_variables(query_normalized),
        "has_where_clause": has_where_clause(query_normalized),
        "has_order_by": has_order_by(query_normalized),
        "has_limit": has_limit(query_normalized),
        "estimated_nodes": estimate_node_count(query_normalized),
        "estimated_edges": estimate_edge_count(query_normalized),
    }


def extract_node_labels(query: str) -> Set[str]:
    """
    Extract all node labels from a Cypher query.
    
    Examples:
        (c:Customer) -> {"Customer"}
        (txn:Transaction) -> {"Transaction"}
        (c:Customer)-[:OWNS]->(acc:Account) -> {"Customer", "Account"}
    
    Args:
        query: Cypher query string
        
    Returns:
        Set of node labels found in the query
    """
    labels = set()
    
    # Pattern for node labels: (var:Label) or (:Label) or (var:Label1:Label2)
    # Use a pattern that captures everything after the first colon until the closing paren
    # This handles: (n:Customer), (:Customer), (n:Customer:Person)
    node_pattern = r'\([^:)]*:([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)\)'
    
    matches = re.finditer(node_pattern, query)
    for match in matches:
        # Extract the label part after the colon - this captures "Customer:Person" as one string
        label_part = match.group(1)
        # Handle multiple labels (Label1:Label2) by splitting on colon
        for label in label_part.split(':'):
            if label and label.strip():
                labels.add(label.strip())
    
    return labels


def extract_relationship_types(query: str) -> Set[str]:
    """
    Extract all relationship types from a Cypher query.
    
    Examples:
        -[:OWNS]-> -> {"OWNS"}
        -[:SENT_TXN]-> -> {"SENT_TXN"}
        -[:TO_ACCOUNT]-> -> {"TO_ACCOUNT"}
    
    Args:
        query: Cypher query string
        
    Returns:
        Set of relationship types found in the query
    """
    rel_types = set()
    
    # Pattern for relationship types: -[:TYPE]-> or <-[:TYPE]-
    # Matches: -[:OWNS]-, <-[:OWNS]-, -[:SENT_TXN]->, etc.
    rel_pattern = r'-\[:([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)\]->?|<-\[:([A-Za-z_][A-Za-z0-9_]*(?::[A-Za-z_][A-Za-z0-9_]*)*)\]'
    
    matches = re.finditer(rel_pattern, query)
    for match in matches:
        # Group 1 for -> direction, Group 2 for <- direction
        rel_type = match.group(1) or match.group(2)
        if rel_type:
            # Handle multiple types (Type1:Type2)
            for rtype in rel_type.split(':'):
                if rtype:
                    rel_types.add(rtype)
    
    return rel_types


def calculate_traversal_depth(query: str) -> int:
    """
    Calculate the maximum traversal depth (number of hops) in a Cypher query.
    
    This counts the number of relationship traversals in the longest path.
    
    Examples:
        (a)-[:R1]->(b) -> depth 1
        (a)-[:R1]->(b)-[:R2]->(c) -> depth 2
        path = (a)-[:R1]->(b)-[:R2]->(c)-[:R3]->(d) -> depth 3
    
    Args:
        query: Cypher query string
        
    Returns:
        Maximum traversal depth (number of hops)
    """
    # Count relationship patterns: -[:TYPE]-> or <-[:TYPE]-
    rel_pattern = r'-\[:[^\]]+\]'
    
    # Find all MATCH clauses - split by MATCH keyword and process each separately
    # This handles multiple MATCH clauses correctly
    match_parts = re.split(r'\bMATCH\s+', query, flags=re.IGNORECASE)
    
    max_depth = 0
    
    # Process each MATCH clause (skip first empty part before first MATCH)
    for part in match_parts[1:]:
        # Extract content until next keyword (WHERE, RETURN, WITH, ORDER, LIMIT, MATCH) or end
        clause_match = re.match(r'(.*?)(?=\s+(?:WHERE|RETURN|WITH|ORDER|LIMIT|MATCH|$))', part, re.DOTALL)
        if clause_match:
            clause_content = clause_match.group(1)
            # Count relationships in this clause
            rel_matches = re.findall(rel_pattern, clause_content)
            depth = len(rel_matches)
            max_depth = max(max_depth, depth)
    
    # Also check for path variables with explicit depth
    path_pattern = r'path\s*=\s*\([^)]+\)(-\[:[^\]]+\]-?>?\([^)]+\))+'
    path_matches = re.finditer(path_pattern, query, re.IGNORECASE)
    for path_match in path_matches:
        path_content = path_match.group(0)
        rel_matches = re.findall(rel_pattern, path_content)
        depth = len(rel_matches)
        max_depth = max(max_depth, depth)
    
    return max_depth


def has_aggregation_functions(query: str) -> bool:
    """
    Check if the query contains aggregation functions.
    
    Common aggregation functions: COUNT, SUM, AVG, MAX, MIN, COLLECT
    
    Args:
        query: Cypher query string
        
    Returns:
        True if query contains aggregation functions, False otherwise
    """
    aggregation_pattern = r'\b(COUNT|SUM|AVG|MAX|MIN|COLLECT|DISTINCT)\s*\('
    return bool(re.search(aggregation_pattern, query, re.IGNORECASE))


def detect_query_pattern(query: str) -> str:
    """
    Detect the type of query pattern.
    
    Patterns:
        - simple: Single MATCH with no path variables
        - path: Uses path variables (path = ...)
        - multi_match: Multiple MATCH clauses
        - with_clause: Uses WITH clause for aggregation/chaining
        - union: Uses UNION or UNION ALL
        
    Args:
        query: Cypher query string
        
    Returns:
        String describing the query pattern
    """
    query_upper = query.upper()
    
    # Check for UNION
    if re.search(r'\bUNION\s+(ALL\s+)?', query_upper):
        return "union"
    
    # Check for path variables
    if re.search(r'\bpath\s*=\s*', query, re.IGNORECASE):
        return "path"
    
    # Count MATCH clauses
    match_count = len(re.findall(r'\bMATCH\b', query_upper))
    if match_count > 1:
        return "multi_match"
    
    # Check for WITH clause
    if re.search(r'\bWITH\b', query_upper):
        return "with_clause"
    
    return "simple"


def extract_path_variables(query: str) -> List[str]:
    """
    Extract path variable names from the query.
    
    Examples:
        path = (a)-[:R]->(b) -> ["path"]
        p = (a)-[:R]->(b) -> ["p"]
    
    Args:
        query: Cypher query string
        
    Returns:
        List of path variable names
    """
    path_vars = []
    
    # Pattern: var = (node)-[:rel]->(node)
    path_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\([^)]+\)(-\[:[^\]]+\]-?>?\([^)]+\))+'
    matches = re.finditer(path_pattern, query, re.IGNORECASE)
    for match in matches:
        var_name = match.group(1)
        if var_name:
            path_vars.append(var_name)
    
    return path_vars


def has_where_clause(query: str) -> bool:
    """Check if query has a WHERE clause."""
    return bool(re.search(r'\bWHERE\b', query, re.IGNORECASE))


def has_order_by(query: str) -> bool:
    """Check if query has an ORDER BY clause."""
    return bool(re.search(r'\bORDER\s+BY\b', query, re.IGNORECASE))


def has_limit(query: str) -> bool:
    """Check if query has a LIMIT clause."""
    return bool(re.search(r'\bLIMIT\b', query, re.IGNORECASE))


def estimate_node_count(query: str) -> int:
    """
    Estimate the number of nodes that might be returned.
    
    This is a rough estimate based on the number of node patterns and LIMIT clauses.
    
    Args:
        query: Cypher query string
        
    Returns:
        Estimated node count (0 if cannot estimate)
    """
    # Check for explicit LIMIT
    limit_match = re.search(r'\bLIMIT\s+(\d+)', query, re.IGNORECASE)
    if limit_match:
        return int(limit_match.group(1))
    
    # Count node patterns as rough estimate
    node_patterns = len(re.findall(r'\([^)]*:[A-Za-z_][A-Za-z0-9_]+\)', query))
    return node_patterns * 10  # Rough estimate: 10 nodes per pattern


def estimate_edge_count(query: str) -> int:
    """
    Estimate the number of edges that might be returned.
    
    This is a rough estimate based on the number of relationship patterns.
    
    Args:
        query: Cypher query string
        
    Returns:
        Estimated edge count (0 if cannot estimate)
    """
    # Count relationship patterns
    rel_patterns = len(re.findall(r'-\[:[^\]]+\]', query))
    return rel_patterns * 10  # Rough estimate: 10 edges per pattern


def extract_resource_attributes(query: str) -> Dict[str, Any]:
    """
    Extract resource attributes from Cypher WHERE clauses and node properties.
    
    Extracts attributes like:
        - risk_rating (from Customer nodes)
        - amount (from Transaction nodes)
        - pep_flag (from Customer nodes)
        - status (from Case/Alert nodes)
        - severity (from Alert nodes)
        - customer_team (from Customer nodes) - Phase 3: ABAC
        - customer_region (from Customer nodes) - Phase 3: ABAC
    
    Args:
        query: Cypher query string
        
    Returns:
        Dictionary of extracted resource attributes
    """
    attributes = {}
    query_normalized = _normalize_query(query)
    
    # Extract WHERE clauses - use non-greedy match to stop at RETURN, WITH, ORDER, LIMIT
    where_pattern = r'\bWHERE\s+(.*?)(?=\s+(?:RETURN|WITH|ORDER|LIMIT|$))'
    where_matches = re.finditer(where_pattern, query_normalized, re.IGNORECASE | re.DOTALL)
    
    for where_match in where_matches:
        where_clause = where_match.group(1)
        
        # Extract risk_rating - handle patterns like c.risk_rating = 'high' or risk_rating = 'high'
        risk_match = re.search(r'(?:\.)?risk_rating\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if risk_match:
            attributes["risk_rating"] = risk_match.group(1).strip("'\"")
        
        # Extract transaction amount thresholds - handle patterns like txn.amount > 50000
        amount_matches = re.finditer(r'(?:\.)?amount\s*([<>=]+)\s*(\d+)', where_clause, re.IGNORECASE)
        for amt_match in amount_matches:
            operator = amt_match.group(1)
            value = float(amt_match.group(2))
            if operator == ">":
                attributes["transaction_amount_min"] = value
            elif operator == "<":
                attributes["transaction_amount_max"] = value
            elif operator == ">=":
                attributes["transaction_amount_min"] = value
            elif operator == "<=":
                attributes["transaction_amount_max"] = value
            elif operator == "=":
                attributes["transaction_amount"] = value
        
        # Extract PEP flag - handle patterns like c.pep_flag = true
        if re.search(r'(?:\.)?pep_flag\s*=\s*true', where_clause, re.IGNORECASE):
            attributes["pep_flag"] = True
        elif re.search(r'(?:\.)?pep_flag\s*=\s*false', where_clause, re.IGNORECASE):
            attributes["pep_flag"] = False
        
        # Extract severity - handle patterns like a.severity = 'high'
        severity_match = re.search(r'(?:\.)?severity\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if severity_match:
            attributes["severity"] = severity_match.group(1).strip("'\"")
        
        # Extract status
        status_match = re.search(r'(?:\.)?status\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if status_match:
            attributes["status"] = status_match.group(1).strip("'\"")
        
        # Extract customer_team from WHERE clauses - Phase 3: ABAC
        # Handles: c.team = 'Team A', customer.team = 'Team B', team = 'Team C'
        team_match = re.search(r'(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?team\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if team_match:
            attributes["customer_team"] = team_match.group(1).strip("'\"")
        
        # Extract customer_region from WHERE clauses - Phase 3: ABAC
        # Handles: c.region = 'US', customer.region = 'EU', region = 'APAC'
        region_match = re.search(r'(?:[a-zA-Z_][a-zA-Z0-9_]*\.)?region\s*[=<>!]+\s*[\'"]?([^\'"\s,]+)[\'"]?', where_clause, re.IGNORECASE)
        if region_match:
            attributes["customer_region"] = region_match.group(1).strip("'\"")
    
    # Also check node property patterns: {property: value}
    node_prop_pattern = r'\{([^}]+)\}'
    prop_matches = re.finditer(node_prop_pattern, query_normalized)
    for prop_match in prop_matches:
        props = prop_match.group(1)
        
        # Extract PEP flag from node properties
        if re.search(r'pep_flag\s*:\s*true', props, re.IGNORECASE):
            attributes["pep_flag"] = True
        
        # Extract risk_rating from node properties
        risk_prop_match = re.search(r'risk_rating\s*:\s*[\'"]?([^\'"\s,}]+)[\'"]?', props, re.IGNORECASE)
        if risk_prop_match:
            attributes["risk_rating"] = risk_prop_match.group(1).strip("'\"")
        
        # Extract customer_team from node properties - Phase 3: ABAC
        # Handles: {team: 'Team A'}, Customer {team: 'Team B'}
        team_prop_match = re.search(r'team\s*:\s*[\'"]?([^\'"\s,}]+)[\'"]?', props, re.IGNORECASE)
        if team_prop_match:
            attributes["customer_team"] = team_prop_match.group(1).strip("'\"")
        
        # Extract customer_region from node properties - Phase 3: ABAC
        # Handles: {region: 'US'}, Customer {region: 'EU'}
        region_prop_match = re.search(r'region\s*:\s*[\'"]?([^\'"\s,}]+)[\'"]?', props, re.IGNORECASE)
        if region_prop_match:
            attributes["customer_region"] = region_prop_match.group(1).strip("'\"")
    
    return attributes


def _normalize_query(query: str) -> str:
    """
    Normalize query string for parsing.
    
    Removes comments and normalizes whitespace.
    
    Args:
        query: Raw Cypher query string
        
    Returns:
        Normalized query string
    """
    # Remove single-line comments (// ...)
    query = re.sub(r'//.*$', '', query, flags=re.MULTILINE)
    
    # Remove multi-line comments (/* ... */)
    query = re.sub(r'/\*.*?\*/', '', query, flags=re.DOTALL)
    
    # Normalize whitespace
    query = re.sub(r'\s+', ' ', query)
    
    return query.strip()


def _empty_metadata() -> Dict[str, Any]:
    """Return empty metadata structure."""
    return {
        "node_labels": set(),
        "relationship_types": set(),
        "max_depth": 0,
        "has_aggregations": False,
        "query_pattern": "simple",
        "path_variables": [],
        "has_where_clause": False,
        "has_order_by": False,
        "has_limit": False,
        "estimated_nodes": 0,
        "estimated_edges": 0,
    }
