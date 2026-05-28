package com.pgcerbos.analyzer;

import jakarta.validation.constraints.NotBlank;
import java.util.Map;

public record AnalyzeRequest(
        @NotBlank String language,
        String dialect,
        @NotBlank String query,
        Map<String, Object> schema,
        String mode
) {
}
