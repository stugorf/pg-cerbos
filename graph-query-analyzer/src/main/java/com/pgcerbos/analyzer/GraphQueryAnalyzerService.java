package com.pgcerbos.analyzer;

import com.pgcerbos.analyzer.gql.GQLLexer;
import com.pgcerbos.analyzer.gql.GQLParser;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import javax.script.Bindings;
import javax.script.ScriptException;
import org.apache.jena.graph.Node;
import org.antlr.v4.runtime.BaseErrorListener;
import org.antlr.v4.runtime.CharStreams;
import org.antlr.v4.runtime.CommonTokenStream;
import org.antlr.v4.runtime.RecognitionException;
import org.antlr.v4.runtime.Recognizer;
import org.apache.jena.query.Query;
import org.apache.jena.query.QueryFactory;
import org.apache.jena.query.Syntax;
import org.apache.jena.sparql.core.TriplePath;
import org.apache.jena.sparql.syntax.ElementPathBlock;
import org.apache.jena.sparql.syntax.ElementVisitorBase;
import org.apache.jena.sparql.syntax.ElementWalker;
import org.apache.tinkerpop.gremlin.groovy.jsr223.GremlinGroovyScriptEngine;
import org.apache.tinkerpop.gremlin.process.traversal.Bytecode;
import org.apache.tinkerpop.gremlin.process.traversal.Traversal;
import org.apache.tinkerpop.gremlin.process.traversal.dsl.graph.GraphTraversalSource;
import org.apache.tinkerpop.gremlin.tinkergraph.structure.TinkerGraph;
import org.neo4j.cypherdsl.parser.CypherParser;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class GraphQueryAnalyzerService {
    private static final String ANALYSIS_VERSION = "graph-query-analysis/v1";

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
        try {
            CypherParser.parse(query);
        } catch (RuntimeException exc) {
            throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "Cypher parse failed: " + rootMessage(exc));
        }
        return propertyGraphAnalysis("cypher", dialectOr(dialect, "openCypher-compatible"), mode, query);
    }

    private Map<String, Object> analyzeGql(String query, String dialect, String mode) {
        try {
            GQLLexer lexer = new GQLLexer(CharStreams.fromString(query));
            CollectingErrorListener listener = new CollectingErrorListener();
            lexer.removeErrorListeners();
            lexer.addErrorListener(listener);
            GQLParser parser = new GQLParser(new CommonTokenStream(lexer));
            parser.removeErrorListeners();
            parser.addErrorListener(listener);
            parser.gqlRequest();
            if (listener.hasErrors()) {
                throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "GQL parse failed: " + listener.message());
            }
        } catch (GraphQueryAnalysisException exc) {
            throw exc;
        } catch (RuntimeException exc) {
            throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "GQL parse failed: " + rootMessage(exc));
        }
        return propertyGraphAnalysis("gql", dialectOr(dialect, "ISO GQL"), mode, query);
    }

    private Map<String, Object> analyzeSparql(String query, String dialect, String mode) {
        Query parsed;
        try {
            parsed = QueryFactory.create(query, Syntax.syntaxSPARQL_11);
        } catch (RuntimeException exc) {
            throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "SPARQL parse failed: " + rootMessage(exc));
        }

        Set<String> predicates = sparqlPredicates(parsed);
        Integer limit = parsed.hasLimit() ? Math.toIntExact(parsed.getLimit()) : null;
        boolean hasWriteOperation = !parsed.isSelectType() && !parsed.isAskType() && !parsed.isConstructType() && !parsed.isDescribeType();
        Map<String, Object> analysis = base("sparql", dialectOr(dialect, "SPARQL 1.1"), mode, query, !hasWriteOperation);
        analysis.put("statement_type", hasWriteOperation ? "write" : "read");
        analysis.put("has_write_operation", hasWriteOperation);
        analysis.put("is_read_only", !hasWriteOperation);
        analysis.put("accessed_node_labels", List.of());
        analysis.put("accessed_edge_types", List.copyOf(predicates));
        analysis.put("accessed_properties", List.copyOf(predicates));
        analysis.put("path_patterns", List.of());
        analysis.put("max_traversal_depth", TextInspector.containsAny(query, "*", "+", "|") ? 1 : 0);
        analysis.put("has_variable_length_paths", TextInspector.containsAny(query, "*", "+", "|"));
        analysis.put("has_aggregation", TextInspector.containsWord(query, "COUNT", "SUM", "AVG", "MIN", "MAX", "GROUP_CONCAT", "SAMPLE"));
        analysis.put("has_subquery", TextInspector.containsWordsInOrder(query, "SELECT", "WHERE", "SELECT"));
        analysis.put("has_union", TextInspector.containsWord(query, "UNION"));
        analysis.put("has_optional_match", TextInspector.containsWord(query, "OPTIONAL"));
        analysis.put("limit", limit);
        analysis.put("estimated_result_bound", limit != null ? limit : 0);
        analysis.put("filters", Map.of());
        analysis.put("parameters", List.of());
        return analysis;
    }

    private Map<String, Object> analyzeGremlin(String query, String dialect, String mode) {
        Bytecode bytecode = parseGremlinBytecode(query);
        Set<String> nodeLabels = new LinkedHashSet<>();
        Set<String> edgeTypes = new LinkedHashSet<>();
        int traversalDepth = 0;
        Integer limit = null;
        boolean hasWriteOperation = false;
        boolean hasAggregation = false;
        boolean hasVariableLengthPaths = false;

        for (Bytecode.Instruction instruction : bytecode.getStepInstructions()) {
            String operator = instruction.getOperator();
            List<Object> args = List.of(instruction.getArguments());
            if ("hasLabel".equals(operator)) {
                collectStringArgs(args, nodeLabels);
            }
            if (List.of("out", "in", "both", "outE", "inE", "bothE").contains(operator)) {
                traversalDepth++;
                collectStringArgs(args, edgeTypes);
            }
            if ("repeat".equals(operator) || "until".equals(operator) || "emit".equals(operator)) {
                hasVariableLengthPaths = true;
            }
            if (List.of("count", "sum", "mean", "min", "max", "group", "groupCount").contains(operator)) {
                hasAggregation = true;
            }
            if ("limit".equals(operator) && !args.isEmpty() && args.get(0) instanceof Number number) {
                limit = number.intValue();
            }
            if (List.of("addV", "addE", "property", "drop", "sideEffect").contains(operator)) {
                hasWriteOperation = true;
            }
        }

        Map<String, Object> analysis = base("gremlin", dialectOr(dialect, "TinkerPop Bytecode"), mode, query, !hasWriteOperation);
        analysis.put("accessed_node_labels", List.copyOf(nodeLabels));
        analysis.put("accessed_edge_types", List.copyOf(edgeTypes));
        analysis.put("accessed_properties", List.of());
        analysis.put("path_patterns", List.of());
        analysis.put("max_traversal_depth", traversalDepth);
        analysis.put("has_variable_length_paths", hasVariableLengthPaths);
        analysis.put("has_aggregation", hasAggregation);
        analysis.put("has_subquery", false);
        analysis.put("has_union", hasStep(bytecode, "union", "coalesce", "choose"));
        analysis.put("has_optional_match", hasStep(bytecode, "optional"));
        analysis.put("limit", limit);
        analysis.put("estimated_result_bound", limit != null ? limit : 0);
        analysis.put("filters", Map.of());
        analysis.put("parameters", List.of());
        analysis.put("node_labels", List.copyOf(nodeLabels));
        analysis.put("relationship_types", List.copyOf(edgeTypes));
        analysis.put("max_depth", traversalDepth);
        analysis.put("has_aggregations", hasAggregation);
        analysis.put("query_pattern", hasStep(bytecode, "union") ? "union" : "simple");
        analysis.put("path_variables", List.of());
        analysis.put("has_where_clause", hasStep(bytecode, "has", "where"));
        analysis.put("has_order_by", hasStep(bytecode, "order"));
        analysis.put("has_limit", limit != null);
        analysis.put("estimated_nodes", limit != null ? limit : 0);
        analysis.put("estimated_edges", edgeTypes.size() * 10);
        return analysis;
    }

    private Map<String, Object> propertyGraphAnalysis(String language, String dialect, String mode, String query) {
        TextInspector.PropertyGraphMetadata metadata = TextInspector.propertyGraph(query);
        boolean hasWriteOperation = TextInspector.containsWord(query, "CREATE", "MERGE", "SET", "DELETE", "DETACH", "REMOVE", "DROP", "INSERT");
        Map<String, Object> filters = TextInspector.filters(query);
        Map<String, Object> analysis = base(language, dialect, mode, query, !hasWriteOperation);
        analysis.put("accessed_node_labels", List.copyOf(metadata.nodeLabels()));
        analysis.put("accessed_edge_types", List.copyOf(metadata.relationshipTypes()));
        analysis.put("accessed_properties", List.of());
        analysis.put("path_patterns", List.of());
        analysis.put("max_traversal_depth", metadata.maxDepth());
        analysis.put("has_variable_length_paths", metadata.hasVariableLengthPath());
        analysis.put("has_aggregation", TextInspector.containsWord(query, "COUNT", "SUM", "AVG", "MAX", "MIN", "COLLECT", "DISTINCT"));
        analysis.put("has_subquery", TextInspector.containsWord(query, "CALL"));
        analysis.put("has_union", TextInspector.containsWord(query, "UNION"));
        analysis.put("has_optional_match", TextInspector.containsWordsInOrder(query, "OPTIONAL", "MATCH"));
        analysis.put("limit", metadata.limit());
        analysis.put("estimated_result_bound", metadata.limit() != null ? metadata.limit() : metadata.estimatedNodes());
        analysis.put("filters", filters);
        analysis.put("parameters", metadata.parameters());
        analysis.put("node_labels", List.copyOf(metadata.nodeLabels()));
        analysis.put("relationship_types", List.copyOf(metadata.relationshipTypes()));
        analysis.put("max_depth", metadata.maxDepth());
        analysis.put("has_aggregations", analysis.get("has_aggregation"));
        analysis.put("query_pattern", metadata.queryPattern());
        analysis.put("path_variables", metadata.pathVariables());
        analysis.put("has_where_clause", TextInspector.containsWord(query, "WHERE"));
        analysis.put("has_order_by", TextInspector.containsWordsInOrder(query, "ORDER", "BY"));
        analysis.put("has_limit", metadata.limit() != null);
        analysis.put("estimated_nodes", metadata.limit() != null ? metadata.limit() : metadata.estimatedNodes());
        analysis.put("estimated_edges", metadata.relationshipTypes().size() * 10);
        analysis.putAll(filters);
        return analysis;
    }

    private Set<String> sparqlPredicates(Query parsed) {
        Set<String> predicates = new LinkedHashSet<>();
        if (parsed.getQueryPattern() == null) {
            return predicates;
        }
        ElementWalker.walk(parsed.getQueryPattern(), new ElementVisitorBase() {
            @Override
            public void visit(ElementPathBlock element) {
                var iterator = element.patternElts();
                while (iterator.hasNext()) {
                    TriplePath triplePath = iterator.next();
                    Node predicate = triplePath.getPredicate();
                    if (predicate != null) {
                        predicates.add(formatSparqlNode(predicate));
                    } else if (triplePath.getPath() != null) {
                        predicates.add(triplePath.getPath().toString());
                    }
                }
            }
        });
        return predicates;
    }

    private String formatSparqlNode(Node node) {
        if (node.isURI()) {
            return "<" + node.getURI() + ">";
        }
        return node.toString();
    }

    private Bytecode parseGremlinBytecode(String query) {
        TinkerGraph graph = TinkerGraph.open();
        try (GraphTraversalSource g = graph.traversal()) {
            GremlinGroovyScriptEngine engine = new GremlinGroovyScriptEngine();
            Bindings bindings = engine.createBindings();
            bindings.put("g", g);
            Object result = engine.eval(query, bindings);
            if (result instanceof Traversal<?, ?> traversal) {
                return traversal.asAdmin().getBytecode();
            }
            throw new GraphQueryAnalysisException(
                    HttpStatus.BAD_REQUEST,
                    "Gremlin parse failed: query must evaluate to a TinkerPop traversal with inspectable Bytecode"
            );
        } catch (ScriptException exc) {
            throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "Gremlin parse failed: " + rootMessage(exc));
        } catch (GraphQueryAnalysisException exc) {
            throw exc;
        } catch (Exception exc) {
            throw new GraphQueryAnalysisException(HttpStatus.BAD_REQUEST, "Gremlin parse failed: " + rootMessage(exc));
        } finally {
            try {
                graph.close();
            } catch (Exception ignored) {
            }
        }
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

    private static boolean hasStep(Bytecode bytecode, String... operators) {
        Set<String> target = Set.of(operators);
        return bytecode.getStepInstructions().stream().anyMatch(instruction -> target.contains(instruction.getOperator()));
    }

    private static void collectStringArgs(Collection<Object> args, Set<String> target) {
        for (Object arg : args) {
            if (arg instanceof String value && !value.isBlank()) {
                target.add(value);
            } else if (arg instanceof Object[] values) {
                collectStringArgs(List.of(values), target);
            } else if (arg instanceof Collection<?> values) {
                collectStringArgs(new ArrayList<>(values), target);
            }
        }
    }

    private static String normalize(String value) {
        return strip(value).toLowerCase(Locale.ROOT);
    }

    private static String strip(String value) {
        return value == null ? "" : value.strip();
    }

    private static String dialectOr(String value, String fallback) {
        return strip(value).isEmpty() ? fallback : strip(value);
    }

    private static String rootMessage(Throwable throwable) {
        Throwable current = throwable;
        while (current.getCause() != null) {
            current = current.getCause();
        }
        String message = current.getMessage();
        return message == null || message.isBlank() ? current.getClass().getSimpleName() : message;
    }

    private static class CollectingErrorListener extends BaseErrorListener {
        private final List<String> errors = new ArrayList<>();

        @Override
        public void syntaxError(
                Recognizer<?, ?> recognizer,
                Object offendingSymbol,
                int line,
                int charPositionInLine,
                String msg,
                RecognitionException e
        ) {
            errors.add("line " + line + ":" + charPositionInLine + " " + msg);
        }

        boolean hasErrors() {
            return !errors.isEmpty();
        }

        String message() {
            return String.join("; ", errors);
        }
    }
}
