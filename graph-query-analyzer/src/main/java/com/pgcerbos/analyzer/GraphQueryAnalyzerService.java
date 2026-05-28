package com.pgcerbos.analyzer;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class GraphQueryAnalyzerService {
    private static final String ANALYSIS_VERSION = "graph-query-analysis/v1";
    private static final Pattern LIMIT_PATTERN = Pattern.compile("\\bLIMIT\\s+(\\d+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern NODE_BODY_PATTERN = Pattern.compile("\\(([^)]*)\\)");
    private static final Pattern NODE_LABEL_PATTERN = Pattern.compile(":\\s*([A-Za-z_][A-Za-z0-9_]*)");
    private static final Pattern REL_TYPE_PATTERN = Pattern.compile("-\\s*\\[[^\\]]*?:\\s*([A-Za-z_][A-Za-z0-9_]*)[^\\]]*]\\s*-?>?|<-\\s*\\[[^\\]]*?:\\s*([A-Za-z_][A-Za-z0-9_]*)[^\\]]*]\\s*-");
    private static final Pattern PARAM_PATTERN = Pattern.compile("\\$([A-Za-z_][A-Za-z0-9_]*)");
    private static final Pattern VARIABLE_PATH_PATTERN = Pattern.compile("-\\s*\\[[^\\]]*\\*\\s*\\d*(?:\\.\\.\\d*)?[^\\]]*]");

    public Map<String, Object> analyze(AnalyzeRequest request) {
        String language = normalize(request.language());
        String query = strip(request.query());
        if (query.isEmpty()) {
            throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "Query is required");
        }

        return switch (language) {
            case "cypher" -> analyzeCypher(query, request.dialect(), request.mode());
            case "sparql" -> analyzeSparql(query, request.dialect(), request.mode());
            case "gremlin" -> analyzeGremlin(query, request.dialect(), request.mode());
            case "gql" -> analyzeGql(query, request.dialect(), request.mode());
            default -> throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "Unsupported graph query language: " + request.language());
        };
    }

    private Map<String, Object> analyzeCypher(String query, String dialect, String mode) {
        String normalized = normalizeWhitespace(removeCypherComments(query));
        Set<String> nodeLabels = extractNodeLabels(normalized);
        Set<String> relationshipTypes = extractRelationshipTypes(normalized);
        Map<String, Object> filters = extractCypherFilters(normalized);
        Integer limit = extractLimit(normalized);
        int maxDepth = calculateTraversalDepth(normalized);
        boolean hasWriteOperation = contains(normalized, "\\b(CREATE|MERGE|SET|DELETE|DETACH\\s+DELETE|REMOVE|DROP|LOAD\\s+CSV)\\b");
        boolean hasAggregation = contains(normalized, "\\b(COUNT|SUM|AVG|MAX|MIN|COLLECT|DISTINCT)\\s*\\(");
        boolean hasUnion = contains(normalized, "\\bUNION\\b");
        boolean hasSubquery = contains(normalized, "\\bCALL\\s*\\{");
        boolean hasOptionalMatch = contains(normalized, "\\bOPTIONAL\\s+MATCH\\b");
        boolean hasWhere = contains(normalized, "\\bWHERE\\b");
        boolean hasOrderBy = contains(normalized, "\\bORDER\\s+BY\\b");
        boolean hasVariableLengthPaths = VARIABLE_PATH_PATTERN.matcher(normalized).find();
        String queryPattern = queryPattern(normalized, hasUnion, hasSubquery, hasOptionalMatch);
        List<String> pathVariables = extractPathVariables(normalized);

        Map<String, Object> analysis = base("cypher", dialectOr(dialect, "openCypher-compatible"), mode, query, !hasWriteOperation);
        analysis.put("accessed_node_labels", List.copyOf(nodeLabels));
        analysis.put("accessed_edge_types", List.copyOf(relationshipTypes));
        analysis.put("accessed_properties", List.of());
        analysis.put("path_patterns", List.of());
        analysis.put("max_traversal_depth", maxDepth);
        analysis.put("has_variable_length_paths", hasVariableLengthPaths);
        analysis.put("has_aggregation", hasAggregation);
        analysis.put("has_subquery", hasSubquery);
        analysis.put("has_union", hasUnion);
        analysis.put("has_optional_match", hasOptionalMatch);
        analysis.put("limit", limit);
        analysis.put("estimated_result_bound", limit != null ? limit : estimateNodeCount(normalized));
        analysis.put("filters", filters);
        analysis.put("parameters", extractParameters(normalized));
        analysis.put("warnings", List.of(Map.of(
                "code", "SIDECAR_HEURISTIC_ANALYZER",
                "severity", "warning",
                "security_relevant", false,
                "message", "Sidecar is wired but parser dependencies are not yet enabled; upgrade to Neo4j/Jena parsers for production semantic analysis."
        )));

        analysis.put("node_labels", List.copyOf(nodeLabels));
        analysis.put("relationship_types", List.copyOf(relationshipTypes));
        analysis.put("max_depth", maxDepth);
        analysis.put("has_aggregations", hasAggregation);
        analysis.put("query_pattern", queryPattern);
        analysis.put("path_variables", pathVariables);
        analysis.put("has_where_clause", hasWhere);
        analysis.put("has_order_by", hasOrderBy);
        analysis.put("has_limit", limit != null);
        analysis.put("estimated_nodes", limit != null ? limit : estimateNodeCount(normalized));
        analysis.put("estimated_edges", relationshipTypes.size() * 10);
        analysis.putAll(filters);
        return analysis;
    }

    private Map<String, Object> analyzeSparql(String query, String dialect, String mode) {
        String normalized = normalizeWhitespace(query);
        boolean hasWriteOperation = contains(normalized, "\\b(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD)\\b");
        Integer limit = extractLimit(normalized);
        Map<String, Object> analysis = base("sparql", dialectOr(dialect, "SPARQL 1.1"), mode, query, !hasWriteOperation);
        analysis.put("statement_type", hasWriteOperation ? "write" : "read");
        analysis.put("has_write_operation", hasWriteOperation);
        analysis.put("is_read_only", !hasWriteOperation);
        analysis.put("accessed_node_labels", List.of());
        analysis.put("accessed_edge_types", extractSparqlPredicates(normalized));
        analysis.put("accessed_properties", extractSparqlPredicates(normalized));
        analysis.put("path_patterns", List.of());
        analysis.put("max_traversal_depth", 0);
        analysis.put("has_variable_length_paths", contains(normalized, "[*/+|]"));
        analysis.put("has_aggregation", contains(normalized, "\\b(COUNT|SUM|AVG|MIN|MAX|GROUP_CONCAT|SAMPLE)\\s*\\("));
        analysis.put("has_subquery", contains(normalized, "\\{\\s*SELECT\\b"));
        analysis.put("has_union", contains(normalized, "\\bUNION\\b"));
        analysis.put("has_optional_match", contains(normalized, "\\bOPTIONAL\\b"));
        analysis.put("limit", limit);
        analysis.put("estimated_result_bound", limit != null ? limit : 0);
        analysis.put("filters", Map.of());
        analysis.put("parameters", List.of());
        analysis.put("warnings", List.of(Map.of(
                "code", "SPARQL_HEURISTIC_ANALYZER",
                "severity", "warning",
                "security_relevant", true,
                "message", "SPARQL support is contract-only until Apache Jena ARQ parsing is enabled."
        )));
        return analysis;
    }

    private Map<String, Object> analyzeGremlin(String query, String dialect, String mode) {
        String normalized = normalizeWhitespace(query);
        boolean hasWriteOperation = contains(normalized, "\\b(addV|addE|property|drop|sideEffect)\\s*\\(");
        Map<String, Object> analysis = base("gremlin", dialectOr(dialect, "gremlin-script"), mode, query, !hasWriteOperation);
        analysis.put("accessed_node_labels", extractGremlinLabels(normalized, "hasLabel"));
        analysis.put("accessed_edge_types", extractGremlinLabels(normalized, "outE|inE|bothE|out|in|both"));
        analysis.put("accessed_properties", List.of());
        analysis.put("path_patterns", List.of());
        analysis.put("max_traversal_depth", countGremlinTraversalSteps(normalized));
        analysis.put("has_variable_length_paths", contains(normalized, "\\b(repeat|until|emit)\\s*\\("));
        analysis.put("has_aggregation", contains(normalized, "\\b(count|sum|mean|min|max|group|groupCount)\\s*\\("));
        analysis.put("has_subquery", false);
        analysis.put("has_union", contains(normalized, "\\b(union|coalesce|choose)\\s*\\("));
        analysis.put("has_optional_match", contains(normalized, "\\b(optional)\\s*\\("));
        analysis.put("limit", extractGremlinLimit(normalized));
        analysis.put("estimated_result_bound", extractGremlinLimit(normalized) != null ? extractGremlinLimit(normalized) : 0);
        analysis.put("filters", Map.of());
        analysis.put("parameters", List.of());
        analysis.put("warnings", List.of(Map.of(
                "code", "GREMLIN_SCRIPT_HEURISTIC_ANALYZER",
                "severity", "warning",
                "security_relevant", true,
                "message", "Prefer Gremlin Bytecode for production authorization; raw scripts are high risk."
        )));
        return analysis;
    }

    private Map<String, Object> analyzeGql(String query, String dialect, String mode) {
        Map<String, Object> analysis = analyzeCypher(query, dialectOr(dialect, "GQL-compatible"), mode);
        analysis.put("language", "gql");
        analysis.put("query_type", "gql");
        analysis.put("warnings", List.of(Map.of(
                "code", "GQL_HEURISTIC_ANALYZER",
                "severity", "warning",
                "security_relevant", true,
                "message", "GQL support is contract-only until an ISO GQL parser is enabled."
        )));
        return analysis;
    }

    private Map<String, Object> base(String language, String dialect, String mode, String query, boolean readOnly) {
        Map<String, Object> analysis = new LinkedHashMap<>();
        analysis.put("analysis_version", ANALYSIS_VERSION);
        analysis.put("complete", true);
        analysis.put("language", language);
        analysis.put("dialect", dialect);
        analysis.put("mode", strip(mode).isEmpty() ? "read" : strip(mode));
        analysis.put("statement_type", readOnly ? "read" : "write");
        analysis.put("is_read_only", readOnly);
        analysis.put("has_write_operation", !readOnly);
        analysis.put("query_type", language);
        analysis.put("query", query);
        return analysis;
    }

    private Set<String> extractNodeLabels(String query) {
        Set<String> labels = new LinkedHashSet<>();
        Matcher nodeMatcher = NODE_BODY_PATTERN.matcher(query);
        while (nodeMatcher.find()) {
            String nodeBody = nodeMatcher.group(1);
            Matcher labelMatcher = NODE_LABEL_PATTERN.matcher(nodeBody);
            while (labelMatcher.find()) {
                labels.add(labelMatcher.group(1));
            }
        }
        return labels;
    }

    private Set<String> extractRelationshipTypes(String query) {
        Set<String> relationshipTypes = new LinkedHashSet<>();
        Matcher matcher = REL_TYPE_PATTERN.matcher(query);
        while (matcher.find()) {
            String value = matcher.group(1) != null ? matcher.group(1) : matcher.group(2);
            if (value != null) {
                relationshipTypes.add(value);
            }
        }
        return relationshipTypes;
    }

    private Map<String, Object> extractCypherFilters(String query) {
        Map<String, Object> filters = new LinkedHashMap<>();
        putStringFilter(filters, "risk_rating", query, "risk_rating");
        putStringFilter(filters, "severity", query, "severity");
        putStringFilter(filters, "status", query, "status");
        putStringFilter(filters, "customer_team", query, "team");
        putStringFilter(filters, "customer_region", query, "region");
        if (contains(query, "(?i)(?:\\.)?pep_flag\\s*=\\s*true|pep_flag\\s*:\\s*true")) {
            filters.put("pep_flag", true);
        } else if (contains(query, "(?i)(?:\\.)?pep_flag\\s*=\\s*false|pep_flag\\s*:\\s*false")) {
            filters.put("pep_flag", false);
        }

        Matcher amountMatcher = Pattern.compile("(?:\\.)?amount\\s*([<>=]+)\\s*(\\d+)", Pattern.CASE_INSENSITIVE).matcher(query);
        while (amountMatcher.find()) {
            String operator = amountMatcher.group(1);
            double value = Double.parseDouble(amountMatcher.group(2));
            switch (operator) {
                case ">", ">=" -> filters.put("transaction_amount_min", value);
                case "<", "<=" -> filters.put("transaction_amount_max", value);
                case "=" -> filters.put("transaction_amount", value);
                default -> {
                }
            }
        }
        return filters;
    }

    private void putStringFilter(Map<String, Object> filters, String target, String query, String source) {
        Pattern pattern = Pattern.compile("(?:[A-Za-z_][A-Za-z0-9_]*\\.)?" + source + "\\s*(?:[=<>!]+|:)\\s*(?:['\"]([^'\"]+)['\"]|([^'\"\\s,}]+))", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(query);
        if (matcher.find()) {
            filters.put(target, matcher.group(1) != null ? matcher.group(1) : matcher.group(2));
        }
    }

    private int calculateTraversalDepth(String query) {
        int maxDepth = 0;
        String[] matchParts = query.split("(?i)\\bMATCH\\s+");
        for (int i = 1; i < matchParts.length; i++) {
            String clause = matchParts[i].split("(?i)\\s+(WHERE|RETURN|WITH|ORDER|LIMIT|MATCH)\\b", 2)[0];
            int depth = 0;
            Matcher matcher = Pattern.compile("-\\s*\\[[^\\]]*]").matcher(clause);
            while (matcher.find()) {
                depth++;
            }
            maxDepth = Math.max(maxDepth, depth);
        }
        return maxDepth;
    }

    private List<String> extractPathVariables(String query) {
        List<String> variables = new ArrayList<>();
        Matcher matcher = Pattern.compile("([A-Za-z_][A-Za-z0-9_]*)\\s*=\\s*\\([^)]*\\)\\s*-\\s*\\[").matcher(query);
        while (matcher.find()) {
            variables.add(matcher.group(1));
        }
        return variables;
    }

    private List<String> extractParameters(String query) {
        Set<String> parameters = new LinkedHashSet<>();
        Matcher matcher = PARAM_PATTERN.matcher(query);
        while (matcher.find()) {
            parameters.add(matcher.group(1));
        }
        return List.copyOf(parameters);
    }

    private List<String> extractSparqlPredicates(String query) {
        Set<String> predicates = new LinkedHashSet<>();
        Matcher matcher = Pattern.compile("\\?\\w+\\s+([^\\s{};,.]+)\\s+").matcher(query);
        while (matcher.find()) {
            String predicate = matcher.group(1);
            if (!predicate.startsWith("?")) {
                predicates.add(predicate);
            }
        }
        return List.copyOf(predicates);
    }

    private List<String> extractGremlinLabels(String query, String stepPattern) {
        Set<String> labels = new LinkedHashSet<>();
        Matcher matcher = Pattern.compile("\\b(?:" + stepPattern + ")\\s*\\(\\s*['\"]([^'\"]+)['\"]").matcher(query);
        while (matcher.find()) {
            labels.add(matcher.group(1));
        }
        return List.copyOf(labels);
    }

    private int countGremlinTraversalSteps(String query) {
        Matcher matcher = Pattern.compile("\\.\\s*(out|in|both|outE|inE|bothE)\\s*\\(").matcher(query);
        int count = 0;
        while (matcher.find()) {
            count++;
        }
        return count;
    }

    private Integer extractLimit(String query) {
        Matcher matcher = LIMIT_PATTERN.matcher(query);
        return matcher.find() ? Integer.parseInt(matcher.group(1)) : null;
    }

    private Integer extractGremlinLimit(String query) {
        Matcher matcher = Pattern.compile("\\blimit\\s*\\(\\s*(\\d+)\\s*\\)").matcher(query);
        return matcher.find() ? Integer.parseInt(matcher.group(1)) : null;
    }

    private int estimateNodeCount(String query) {
        Integer limit = extractLimit(query);
        if (limit != null) {
            return limit;
        }
        int count = 0;
        Matcher matcher = NODE_BODY_PATTERN.matcher(query);
        while (matcher.find()) {
            if (matcher.group(1).contains(":")) {
                count++;
            }
        }
        return count * 10;
    }

    private String queryPattern(String query, boolean hasUnion, boolean hasSubquery, boolean hasOptionalMatch) {
        if (hasUnion) {
            return "union";
        }
        if (hasSubquery) {
            return "with_clause";
        }
        if (hasOptionalMatch) {
            return "multi_match";
        }
        if (contains(query, "\\b[A-Za-z_][A-Za-z0-9_]*\\s*=\\s*\\([^)]*\\)\\s*-\\s*\\[")) {
            return "path";
        }
        int matches = 0;
        Matcher matcher = Pattern.compile("\\bMATCH\\b", Pattern.CASE_INSENSITIVE).matcher(query);
        while (matcher.find()) {
            matches++;
        }
        if (matches > 1) {
            return "multi_match";
        }
        if (contains(query, "\\bWITH\\b")) {
            return "with_clause";
        }
        return "simple";
    }

    private String removeCypherComments(String query) {
        String withoutLineComments = query.replaceAll("(?m)//.*$", "");
        return withoutLineComments.replaceAll("(?s)/\\*.*?\\*/", "");
    }

    private String normalizeWhitespace(String query) {
        return strip(query).replaceAll("\\s+", " ");
    }

    private boolean contains(String text, String regex) {
        return Pattern.compile(regex, Pattern.CASE_INSENSITIVE).matcher(text).find();
    }

    private String normalize(String value) {
        return strip(value).toLowerCase(Locale.ROOT);
    }

    private String strip(String value) {
        return value == null ? "" : value.strip();
    }

    private String dialectOr(String dialect, String fallback) {
        return strip(dialect).isEmpty() ? fallback : strip(dialect);
    }
}
