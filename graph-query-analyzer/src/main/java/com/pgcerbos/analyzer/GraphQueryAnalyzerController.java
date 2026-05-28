package com.pgcerbos.analyzer;

import jakarta.validation.Valid;
import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class GraphQueryAnalyzerController {
    private final GraphQueryAnalyzerService analyzerService;

    public GraphQueryAnalyzerController(GraphQueryAnalyzerService analyzerService) {
        this.analyzerService = analyzerService;
    }

    @GetMapping("/health")
    public Map<String, Object> health() {
        return Map.of("ok", true, "service", "graph-query-analyzer");
    }

    @PostMapping("/analyze")
    public ResponseEntity<Map<String, Object>> analyze(@Valid @RequestBody AnalyzeRequest request) {
        return ResponseEntity.ok(analyzerService.analyze(request));
    }
}
