package com.pgcerbos.analyzer;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

class GraphQueryAnalyzerServiceTest {
    private final GraphQueryAnalyzerService service = new GraphQueryAnalyzerService();

    @Test
    void analyzesCypherIntoNormalizedAndLegacyFields() {
        Map<String, Object> analysis = service.analyze(new AnalyzeRequest(
                "cypher",
                null,
                "MATCH (c:Customer {team: 'Team A'})-[:OWNS]->(a:Account) RETURN c, a LIMIT 10",
                Map.of(),
                "read"
        ));

        assertThat(analysis.get("analysis_version")).isEqualTo("graph-query-analysis/v1");
        assertThat(analysis.get("complete")).isEqualTo(true);
        assertThat(analysis.get("language")).isEqualTo("cypher");
        assertThat(analysis.get("is_read_only")).isEqualTo(true);
        assertThat(analysis.get("has_write_operation")).isEqualTo(false);
        assertThat(asList(analysis.get("accessed_node_labels"))).containsExactly("Customer", "Account");
        assertThat(asList(analysis.get("accessed_edge_types"))).containsExactly("OWNS");
        assertThat(analysis.get("max_traversal_depth")).isEqualTo(1);
        assertThat(analysis.get("limit")).isEqualTo(10);
        assertThat(analysis.get("customer_team")).isEqualTo("Team A");
        assertThat(asList(analysis.get("node_labels"))).containsExactly("Customer", "Account");
        assertThat(asList(analysis.get("relationship_types"))).containsExactly("OWNS");
    }

    @Test
    void marksCypherWrites() {
        Map<String, Object> analysis = service.analyze(new AnalyzeRequest(
                "cypher",
                null,
                "MATCH (c:Customer) SET c.reviewed = true RETURN c",
                Map.of(),
                "read"
        ));

        assertThat(analysis.get("statement_type")).isEqualTo("write");
        assertThat(analysis.get("is_read_only")).isEqualTo(false);
        assertThat(analysis.get("has_write_operation")).isEqualTo(true);
    }

    @Test
    void parsesGremlinIntoBytecodeMetadata() {
        Map<String, Object> analysis = service.analyze(new AnalyzeRequest(
                "gremlin",
                null,
                "g.V().hasLabel('Customer').out('OWNS').limit(10)",
                Map.of(),
                "read"
        ));

        assertThat(analysis.get("language")).isEqualTo("gremlin");
        assertThat(analysis.get("statement_type")).isEqualTo("read");
        assertThat(asList(analysis.get("accessed_node_labels"))).containsExactly("Customer");
        assertThat(asList(analysis.get("accessed_edge_types"))).containsExactly("OWNS");
        assertThat(analysis.get("limit")).isEqualTo(10);
    }

    @Test
    void rejectsGremlinThatDoesNotProduceTraversalBytecode() {
        assertThatThrownBy(() -> service.analyze(new AnalyzeRequest(
                "gremlin",
                null,
                "1 + 1",
                Map.of(),
                "read"
        )))
                .isInstanceOf(GraphQueryAnalysisException.class)
                .hasMessageContaining("Gremlin parse failed")
                .extracting("status")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void parsesSparqlWithJenaArq() {
        Map<String, Object> analysis = service.analyze(new AnalyzeRequest(
                "sparql",
                null,
                "SELECT * WHERE { ?s <urn:knows> ?o } LIMIT 10",
                Map.of(),
                "read"
        ));

        assertThat(analysis.get("language")).isEqualTo("sparql");
        assertThat(analysis.get("statement_type")).isEqualTo("read");
        assertThat(analysis.get("limit")).isEqualTo(10);
        assertThat(asList(analysis.get("accessed_edge_types"))).contains("<urn:knows>");
    }

    @Test
    void rejectsInvalidSparql() {
        assertThatThrownBy(() -> service.analyze(new AnalyzeRequest(
                "sparql",
                null,
                "SELECT WHERE { ?s ?p }",
                Map.of(),
                "read"
        )))
                .isInstanceOf(GraphQueryAnalysisException.class)
                .hasMessageContaining("SPARQL parse failed")
                .extracting("status")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void parsesGqlWithIsoGrammar() {
        Map<String, Object> analysis = service.analyze(new AnalyzeRequest(
                "gql",
                null,
                "MATCH (c:Customer) RETURN c LIMIT 10",
                Map.of(),
                "read"
        ));

        assertThat(analysis.get("language")).isEqualTo("gql");
        assertThat(analysis.get("statement_type")).isEqualTo("read");
        assertThat(asList(analysis.get("accessed_node_labels"))).containsExactly("Customer");
        assertThat(analysis.get("limit")).isEqualTo(10);
    }

    @Test
    void rejectsInvalidGql() {
        assertThatThrownBy(() -> service.analyze(new AnalyzeRequest(
                "gql",
                null,
                "MATCH (c:Customer RETURN c",
                Map.of(),
                "read"
        )))
                .isInstanceOf(GraphQueryAnalysisException.class)
                .hasMessageContaining("GQL parse failed")
                .extracting("status")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @Test
    void rejectsUnsupportedLanguages() {
        assertThatThrownBy(() -> service.analyze(new AnalyzeRequest(
                "sql",
                null,
                "SELECT 1",
                Map.of(),
                "read"
        )))
                .isInstanceOf(GraphQueryAnalysisException.class)
                .extracting("status")
                .isEqualTo(HttpStatus.BAD_REQUEST);
    }

    @SuppressWarnings("unchecked")
    private List<String> asList(Object value) {
        return (List<String>) value;
    }
}
