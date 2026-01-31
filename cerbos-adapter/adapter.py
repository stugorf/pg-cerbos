"""
Envoy-Cerbos Adapter Service

This service translates Envoy's ext_authz filter requests to Cerbos API format
and returns responses in the format Envoy expects.
"""
import json
import os
import re
import sys
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import httpx

app = FastAPI(title="Cerbos Adapter", version="1.0.0")

# Middleware to log all requests
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        import sys
        print(f"DEBUG MIDDLEWARE: {request.method} {request.url.path}", file=sys.stderr, flush=True)
        response = await call_next(request)
        return response

app.add_middleware(LoggingMiddleware)

CERBOS_URL = os.getenv("CERBOS_URL", "http://cerbos:3593/api/check")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Log registered routes on startup  
@app.on_event("startup")
async def startup_event():
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info("=" * 60)
    logger.info("DEBUG: Registered routes:")
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            logger.info(f"DEBUG:   {sorted(route.methods)} {route.path}")
        elif hasattr(route, "path"):
            logger.info(f"DEBUG:   {route.path}")
    logger.info("=" * 60)


def extract_user_info(headers: Dict[str, str]) -> Dict[str, Any]:
    """Extract user information from Envoy request headers.
    
    Headers can be in different formats:
    - Lowercase: 'x-user-id', 'x-user-email', 'x-user-roles'
    - Original case: 'X-User-Id', 'X-User-Email', 'X-User-Roles'
    """
    # Try lowercase first (most common)
    user_id = headers.get("x-user-id") or headers.get("X-User-Id", "")
    user_email = headers.get("x-user-email") or headers.get("X-User-Email", "")
    user_roles_str = headers.get("x-user-roles") or headers.get("X-User-Roles", "")
    
    # Handle empty roles
    user_roles = [r.strip() for r in user_roles_str.split(",") if r.strip()] if user_roles_str else []
    
    return {
        "id": user_id,
        "email": user_email,
        "roles": user_roles
    }


def determine_resource_kind(query_body: str) -> str:
    """Determine resource kind (postgres or iceberg) from SQL query."""
    query_lower = query_body.lower()
    if "iceberg." in query_lower:
        return "iceberg"
    return "postgres"


def contains_ssn_field(query_body: str) -> bool:
    """Check if SQL query contains SSN-related fields."""
    ssn_patterns = [
        r"\bssn\b",
        r"\bSSN\b",
        r"\bsocial_security\b",
        r"\bsocial_security_number\b",
        r"\bssn_number\b"
    ]
    for pattern in ssn_patterns:
        if re.search(pattern, query_body, re.IGNORECASE):
            return True
    return False


def build_cerbos_request(
    user_info: Dict[str, Any],
    method: str,
    path: str,
    query_body: str
) -> Dict[str, Any]:
    """Build Cerbos authorization request from Envoy request."""
    resource_kind = determine_resource_kind(query_body)
    
    return {
        "principal": {
            "id": user_info["id"],
            "roles": user_info["roles"],
            "attr": {
                "email": user_info["email"]
            }
        },
        "resource": {
            "kind": resource_kind,
            "id": f"query-{user_info['id']}",
            "attr": {
                "method": method,
                "path": path,
                "body": query_body,
                "catalog": resource_kind
            }
        },
        "actions": ["query"]
    }


async def call_cerbos(cerbos_request: Dict[str, Any]) -> Dict[str, Any]:
    """Call Cerbos API and return response."""
    async with httpx.AsyncClient(timeout=2.0) as client:
        try:
            response = await client.post(
                CERBOS_URL,
                json=cerbos_request
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            print(f"ERROR: Cerbos request failed: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Cerbos service unavailable: {str(e)}"
            )


def transform_cerbos_response(
    cerbos_response: Dict[str, Any],
    user_info: Dict[str, Any]
) -> Dict[str, Any]:
    """Transform Cerbos response to Envoy ext_authz format."""
    # Cerbos response structure:
    # {
    #   "requestId": "...",
    #   "results": [{
    #     "resource": {...},
    #     "actions": {
    #       "query": "EFFECT_ALLOW" | "EFFECT_DENY"
    #     }
    #   }]
    # }
    
    results = cerbos_response.get("results", [])
    if not results:
        return {
            "allowed": False,
            "headers": {},
            "body": "No authorization result from Cerbos"
        }
    
    action_result = results[0].get("actions", {}).get("query", "EFFECT_DENY")
    allowed = action_result == "EFFECT_ALLOW"
    
    return {
        "allowed": allowed,
        "headers": {
            "x-authz": "cerbos",
            "x-user-id": user_info["id"],
            "x-user-email": user_info["email"],
            "x-user-roles": ",".join(user_info["roles"])
        },
        "body": "" if allowed else "Access denied by Cerbos policy"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    import sys
    print("DEBUG: /health endpoint called", file=sys.stderr, flush=True)
    return {"status": "healthy", "service": "cerbos-adapter"}

# Add exception handler to catch 404s and log them
@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    import logging
    logger = logging.getLogger("uvicorn")
    logger.error("=" * 50)
    logger.error(f"DEBUG: 404 Not Found - Path: {request.url.path}, Method: {request.method}")
    logger.error("DEBUG: Available routes:")
    for route in app.routes:
        if hasattr(route, "path"):
            methods = getattr(route, "methods", set())
            logger.error(f"DEBUG:   {methods} {route.path}")
    logger.error("=" * 50)
    return JSONResponse(
        status_code=404,
        content={"detail": f"Not Found - Path: {request.url.path}"}
    )


async def process_check_request(request: Request):
    """
    Process authorization check request.
    
    This is the actual handler logic, called by both route handlers.
    Handles both Envoy ext_authz JSON format and raw body format.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    try:
        logger.info(f"DEBUG: Received request at {request.url.path}")
        logger.info(f"DEBUG: Request method: {request.method}")
        logger.info(f"DEBUG: Full URL path: {request.url.path}")
        
        # Log all headers for debugging
        print(f"DEBUG: Request headers: {dict(request.headers)}", file=sys.stderr, flush=True)
        logger.info(f"DEBUG: Request headers: {dict(request.headers)}")
        
        body = await request.body()
        print(f"DEBUG: Request body length: {len(body)} bytes", file=sys.stderr, flush=True)
        logger.info(f"DEBUG: Request body length: {len(body)} bytes")
        
        # Log raw body for debugging (first 500 chars)
        body_str = body.decode('utf-8', errors='replace') if body else ""
        print(f"DEBUG: Request body (first 500 chars): {body_str[:500]}", file=sys.stderr, flush=True)
        logger.info(f"DEBUG: Request body preview: {body_str[:200]}")
        
        # Try to parse as JSON (Envoy ext_authz format)
        envoy_request = None
        if body:
            try:
                envoy_request = json.loads(body)
                print(f"DEBUG: Parsed as JSON successfully", file=sys.stderr, flush=True)
                logger.info("DEBUG: Request body is valid JSON (Envoy ext_authz format)")
            except json.JSONDecodeError:
                # Body is not JSON - might be raw SQL query
                print(f"DEBUG: Body is not JSON, treating as raw query", file=sys.stderr, flush=True)
                logger.warning("DEBUG: Request body is not JSON - Envoy may be sending raw body")
                envoy_request = None
        
        # Extract request information
        if envoy_request and "attributes" in envoy_request:
            # Standard Envoy ext_authz format
            print(f"DEBUG: Using Envoy ext_authz format", file=sys.stderr, flush=True)
            logger.info("DEBUG: Using Envoy ext_authz JSON format")
            attributes = envoy_request.get("attributes", {})
            request_http = attributes.get("request", {}).get("http", {})
            
            # Extract headers
            headers = request_http.get("headers", {})
            method = request_http.get("method", "")
            path = request_http.get("path", "")
            query_body = request_http.get("body", "")
        else:
            # Raw body format - reconstruct from request
            print(f"DEBUG: Using raw body format, reconstructing from request", file=sys.stderr, flush=True)
            logger.warning("DEBUG: Reconstructing Envoy request from raw body and headers")
            
            # Extract headers from the HTTP request
            headers = {}
            for key, value in request.headers.items():
                headers[key.lower()] = value
            
            # Get method and path from the original request
            # The path in the adapter request is /check/v1/statement, but we need /v1/statement
            full_path = request.url.path
            if full_path.startswith("/check/"):
                path = full_path[7:]  # Remove "/check" prefix
            else:
                path = full_path
            
            method = request.method
            query_body = body_str if body_str else ""
            
            # Log reconstructed values
            print(f"DEBUG: Reconstructed - method={method}, path={path}, body_length={len(query_body)}", file=sys.stderr, flush=True)
            logger.info(f"DEBUG: Reconstructed - method={method}, path={path}, body_length={len(query_body)}")
        
        # Extract user information
        user_info = extract_user_info(headers)
        print(f"DEBUG: Extracted user info: id={user_info['id']}, email={user_info['email']}, roles={user_info['roles']}", file=sys.stderr, flush=True)
        logger.info(f"DEBUG: Extracted user info: id={user_info['id']}, email={user_info['email']}, roles={user_info['roles']}")
        
        # Build Cerbos request
        cerbos_request = build_cerbos_request(
            user_info,
            method,
            path,
            query_body
        )
        
        # Call Cerbos
        cerbos_response = await call_cerbos(cerbos_request)
        
        # Transform response for Envoy
        envoy_response = transform_cerbos_response(cerbos_response, user_info)
        print(f"DEBUG: Authorization result: allowed={envoy_response.get('allowed')}")
        
        return JSONResponse(content=envoy_response)
        
    except json.JSONDecodeError as e:
        return JSONResponse(
            status_code=400,
            content={
                "allowed": False,
                "headers": {},
                "body": f"Invalid request format: {str(e)}"
            }
        )
    except Exception as e:
        print(f"ERROR: Adapter error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "allowed": False,
                "headers": {},
                "body": f"Adapter error: {str(e)}"
            }
        )


# Handle /check endpoint
# Envoy should call this directly (without appending original path)
@app.post("/check")
async def check_handler(request: Request):
    """
    Main authorization check endpoint.
    
    Receives Envoy ext_authz format request and translates it to Cerbos format.
    """
    import sys
    import logging
    logger = logging.getLogger("uvicorn")
    
    # Log that route was matched
    print("=" * 60, file=sys.stderr, flush=True)
    print(f"ROUTE MATCHED: /check (exact)", file=sys.stderr, flush=True)
    print(f"Request path: {request.url.path}", file=sys.stderr, flush=True)
    print(f"Request method: {request.method}", file=sys.stderr, flush=True)
    logger.info("=" * 60)
    logger.info("ROUTE MATCHED: /check (exact)")
    logger.info(f"Request path: {request.url.path}")
    logger.info(f"Request method: {request.method}")
    print("=" * 60, file=sys.stderr, flush=True)
    
    return await process_check_request(request)


# Fallback route: Handle /check/* paths if Envoy still appends original path
# This should only match if /check doesn't match exactly
@app.post("/check/{rest:path}")
async def check_with_path(request: Request, rest: str):
    """
    Fallback handler for /check/* paths.
    
    This route will only be matched if Envoy appends the original request path
    (e.g., /check/v1/statement) despite having /check in the URI.
    """
    import sys
    import logging
    logger = logging.getLogger("uvicorn")
    
    print("=" * 60, file=sys.stderr, flush=True)
    print(f"ROUTE MATCHED: /check/{{rest:path}} with rest='{rest}'", file=sys.stderr, flush=True)
    print(f"Request path: {request.url.path}", file=sys.stderr, flush=True)
    logger.warning("=" * 60)
    logger.warning("FALLBACK ROUTE MATCHED: /check/{rest:path}")
    logger.warning(f"Rest path: {rest}")
    logger.warning(f"Full request path: {request.url.path}")
    logger.warning("This suggests Envoy is appending the original path despite URI configuration")
    print("=" * 60, file=sys.stderr, flush=True)
    
    # Call the same handler logic
    return await process_check_request(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
