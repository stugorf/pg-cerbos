package com.pgcerbos.analyzer;

import org.springframework.http.HttpStatus;

public class GraphQueryAnalysisException extends RuntimeException {
    private final HttpStatus status;

    public GraphQueryAnalysisException(HttpStatus status, String message) {
        super(message);
        this.status = status;
    }

    public HttpStatus status() {
        return status;
    }
}
