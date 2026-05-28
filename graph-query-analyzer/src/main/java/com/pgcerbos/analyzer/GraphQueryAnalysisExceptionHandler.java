package com.pgcerbos.analyzer;

import java.util.Map;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GraphQueryAnalysisExceptionHandler {
    @ExceptionHandler(GraphQueryAnalysisException.class)
    public ResponseEntity<Map<String, Object>> handleAnalysisException(GraphQueryAnalysisException exception) {
        return ResponseEntity.status(exception.status()).body(Map.of(
                "error", exception.getMessage(),
                "complete", false
        ));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> handleValidationException(MethodArgumentNotValidException exception) {
        return ResponseEntity.badRequest().body(Map.of(
                "error", "language and query are required",
                "complete", false
        ));
    }
}
