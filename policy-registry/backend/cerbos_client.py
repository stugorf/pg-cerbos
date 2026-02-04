"""
Cerbos Authorization Client

This module provides a client wrapper for Cerbos authorization checks.
It integrates Cerbos as the core policy decision point for query authorization.
"""
import os
import logging
from typing import List, Optional
from cerbos.sdk.grpc.client import CerbosClient
from cerbos.engine.v1 import engine_pb2
from google.protobuf.struct_pb2 import Value, ListValue

logger = logging.getLogger(__name__)

# Cerbos uses gRPC, so URL should be host:port format (no http://)
CERBOS_URL = os.getenv("CERBOS_URL", "cerbos:3593")


class CerbosAuthz:
    """Cerbos authorization client wrapper."""
    
    def __init__(self, cerbos_url: Optional[str] = None):
        """
        Initialize Cerbos client.
        
        Args:
            cerbos_url: Optional Cerbos service URL. Defaults to CERBOS_URL env var or http://cerbos:3593
        """
        raw_url = cerbos_url or CERBOS_URL
        # Strip http:// or https:// prefix if present (gRPC uses host:port format)
        if raw_url.startswith("http://"):
            self.cerbos_url = raw_url[7:]  # Remove "http://"
        elif raw_url.startswith("https://"):
            self.cerbos_url = raw_url[8:]  # Remove "https://"
        else:
            self.cerbos_url = raw_url
        
        try:
            # Initialize gRPC client (tls_verify=False for development)
            self.client = CerbosClient(self.cerbos_url, tls_verify=False)
            logger.info(f"Cerbos gRPC client initialized with URL: {self.cerbos_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Cerbos client: {e}")
            raise
    
    def check_query_permission(
        self,
        user_id: str,
        user_email: str,
        user_roles: List[str],
        method: str,
        path: str,
        query_body: str
    ) -> tuple[bool, Optional[str], str]:
        """
        Check if user can execute a SQL query.
        
        Args:
            user_id: User identifier
            user_email: User email address
            user_roles: List of user roles
            method: HTTP method (typically "POST")
            path: Request path (typically "/v1/statement")
            query_body: SQL query string
            
        Returns:
            Tuple of (allowed: bool, reason: Optional[str], policy: str)
            - allowed: True if query is authorized, False otherwise
            - reason: Optional denial reason if not allowed
            - policy: Policy name that was evaluated (e.g., "postgres", "iceberg")
        """
        try:
            # Determine resource kind from query content
            query_lower = query_body.lower()
            if "iceberg." in query_lower:
                resource_kind = "iceberg"
            else:
                resource_kind = "postgres"
            
            # Create principal using gRPC protobuf format
            principal = engine_pb2.Principal(
                id=user_id,
                roles=set(user_roles),
                attr={
                    "email": Value(string_value=user_email)
                }
            )
            
            # Create resource using gRPC protobuf format
            resource = engine_pb2.Resource(
                id=f"query-{user_id}",
                kind=resource_kind,
                attr={
                    "method": Value(string_value=method),
                    "path": Value(string_value=path),
                    "body": Value(string_value=query_body),
                    "catalog": Value(string_value=resource_kind)
                }
            )
            
            # Execute check using Cerbos SDK
            logger.debug(f"Checking Cerbos authorization for user {user_id}, resource {resource_kind}")
            logger.debug(f"Cerbos client URL: {self.cerbos_url}, Principal: {principal.id}, Resource: {resource.kind}:{resource.id}")
            
            # Use is_allowed for single action check (simpler API)
            try:
                allowed = self.client.is_allowed("query", principal, resource)
            except Exception as sdk_error:
                logger.error(f"Cerbos SDK error during is_allowed call: {sdk_error}", exc_info=True)
                # Re-raise to be caught by outer exception handler
                raise
            
            # Log authorization decision for audit trail
            decision = "ALLOW" if allowed else "DENY"
            logger.info(
                f"Cerbos authorization decision: {decision} | "
                f"user={user_id} | roles={user_roles} | "
                f"resource={resource_kind} | action=query | "
                f"query_preview={query_body[:100]}..."
            )
            
            if allowed:
                logger.info(f"Cerbos authorized query for user {user_id}, resource {resource_kind}")
                return True, None, resource_kind
            else:
                logger.info(f"Cerbos denied query for user {user_id}, resource {resource_kind}")
                return False, "Query not authorized by Cerbos policy", resource_kind
                
        except Exception as e:
            logger.error(f"Error checking Cerbos authorization: {e}", exc_info=True)
            # Fail closed - deny access on error
            return False, f"Authorization check failed: {str(e)}", resource_kind
    
    def check_resource_access(
        self,
        user_id: str,
        user_email: str,
        user_roles: List[str],
        resource_kind: str,
        resource_id: str,
        action: str,
        attributes: Optional[dict] = None,
        principal_attributes: Optional[dict] = None
    ) -> tuple[bool, Optional[str], str]:
        """
        Generic resource access check.
        
        Args:
            user_id: User identifier
            user_email: User email address
            user_roles: List of user roles
            resource_kind: Type of resource (e.g., "postgres", "iceberg", "cypher_query")
            resource_id: Resource identifier
            action: Action to check (e.g., "query", "read", "write", "execute")
            attributes: Optional additional resource attributes
            principal_attributes: Optional additional principal attributes (e.g., team, region, clearance_level)
            
        Returns:
            Tuple of (allowed: bool, reason: Optional[str], policy: str)
            - allowed: True if access is authorized, False otherwise
            - reason: Optional denial reason if not allowed
            - policy: Policy name that was evaluated (resource_kind)
        """
        try:
            # Build principal attributes
            principal_attr = {
                "email": Value(string_value=user_email)
            }
            
            # Add additional principal attributes if provided
            # Skip None values - they should not be included in attributes
            # This allows CEL expressions to properly check for null using == null
            if principal_attributes:
                for key, val in principal_attributes.items():
                    if val is None:
                        # Skip None values - don't include in attributes
                        # This allows CEL to properly evaluate P.attr.team == null
                        continue
                    elif isinstance(val, str):
                        principal_attr[key] = Value(string_value=val)
                    elif isinstance(val, bool):
                        principal_attr[key] = Value(bool_value=val)
                    elif isinstance(val, (int, float)):
                        principal_attr[key] = Value(number_value=float(val))
                    else:
                        principal_attr[key] = Value(string_value=str(val))
            
            # Create principal using gRPC protobuf format
            principal = engine_pb2.Principal(
                id=user_id,
                roles=set(user_roles),
                attr=principal_attr
            )
            
            # Create resource using gRPC protobuf format
            # Skip None values - they should not be included in attributes
            # This allows CEL expressions to properly check for null using == null
            resource_attr = attributes or {}
            resource_dict = {}
            for key, val in resource_attr.items():
                if val is None:
                    # Skip None values - don't include in attributes
                    # This allows CEL to properly evaluate R.attr.customer_team == null
                    continue
                elif isinstance(val, str):
                    resource_dict[key] = Value(string_value=val)
                elif isinstance(val, bool):
                    resource_dict[key] = Value(bool_value=val)
                elif isinstance(val, (int, float)):
                    resource_dict[key] = Value(number_value=float(val))
                elif isinstance(val, (set, list)):
                    # Convert sets/lists to list_value for Cerbos (supports array operations in CEL)
                    val_list = list(val) if isinstance(val, set) else val
                    # Use list_value for proper array support in Cerbos CEL expressions
                    list_vals = [Value(string_value=str(v)) for v in val_list]
                    resource_dict[key] = Value(list_value=ListValue(values=list_vals))
                else:
                    resource_dict[key] = Value(string_value=str(val))
            
            resource = engine_pb2.Resource(
                id=resource_id,
                kind=resource_kind,
                attr=resource_dict
            )
            
            logger.debug(f"Checking Cerbos authorization for {action} on {resource_kind}:{resource_id}")
            # Use is_allowed for single action check (simpler API)
            allowed = self.client.is_allowed(action, principal, resource)
            
            if allowed:
                return True, None, resource_kind
            else:
                return False, f"{action} not authorized on {resource_kind}:{resource_id}", resource_kind
                
        except Exception as e:
            logger.error(f"Error checking Cerbos authorization: {e}", exc_info=True)
            return False, f"Authorization check failed: {str(e)}", resource_kind


# Global instance (will be initialized on first use)
_cerbos_authz: Optional[CerbosAuthz] = None


def get_cerbos_client() -> CerbosAuthz:
    """Get or create the global Cerbos client instance."""
    global _cerbos_authz
    if _cerbos_authz is None:
        _cerbos_authz = CerbosAuthz()
    return _cerbos_authz
