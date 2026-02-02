import io, os, tarfile, time, yaml
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from db import SessionLocal, engine
from models import Policy
from auth_models import User, Role, Permission, Base
from auth_utils import (
    authenticate_user, create_access_token, verify_token, 
    get_password_hash, check_permission, is_admin, get_user_roles
)
from auth_models import (
    UserCreate, UserUpdate, UserResponse, RoleCreate, RoleResponse,
    PermissionCreate, PermissionResponse, LoginRequest, LoginResponse
)
from query_models import Query, QueryColumn, QueryResult, QueryStat, QueryCreate, QueryResponse, QueryResultResponse
from query_db import get_query_db, get_query_db_sync, init_query_database
try:
    from cerbos_client import get_cerbos_client
    CERBOS_CLIENT_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Could not import cerbos_client: {e}")
    CERBOS_CLIENT_AVAILABLE = False
    # Create a dummy function to prevent errors
    def get_cerbos_client():
        raise RuntimeError("Cerbos client not available")

# AML imports
try:
    from aml_models import (
        GraphExpandRequest, CaseNoteCreate, CaseAssignRequest, SARCreate,
        CustomerResponse, AccountResponse, TransactionResponse, AlertResponse,
        CaseResponse, CaseNoteResponse, SARResponse, GraphResponse, GraphNode, GraphEdge
    )
    from puppygraph_client import get_puppygraph_client
    AML_AVAILABLE = True
except ImportError as e:
    print(f"WARNING: Could not import AML modules: {e}")
    AML_AVAILABLE = False

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# In-memory store for authorization decisions (for demo purposes)
_authorization_decisions = []
_MAX_DECISIONS = 500


def log_authorization_decision(
    user_id: str,
    user_email: str,
    user_roles: List[str],
    resource_kind: str,
    action: str,
    allowed: bool,
    reason: Optional[str] = None,
    query_preview: Optional[str] = None,
    policy: Optional[str] = None
):
    """Log an authorization decision for display in the UI."""
    global _authorization_decisions
    decision = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "user_email": user_email,
        "user_roles": user_roles,
        "resource_kind": resource_kind,
        "action": action,
        "allowed": allowed,
        "reason": reason,
        "query_preview": query_preview,
        "policy": policy or resource_kind,  # Default to resource_kind if policy not provided
        "decision": "ALLOW" if allowed else "DENY"
    }
    _authorization_decisions.append(decision)
    # Keep only the most recent decisions
    if len(_authorization_decisions) > _MAX_DECISIONS:
        _authorization_decisions = _authorization_decisions[-_MAX_DECISIONS:]

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize query results database
try:
    init_query_database()
except Exception as e:
    print(f"Warning: Could not initialize query results database: {e}")

API = FastAPI(title="Policy Registry", version="0.1")

origins = [os.getenv("CORS_ORIGINS", "*")]
API.add_middleware(
    CORSMiddleware,
    allow_origins=origins if isinstance(origins, str) else origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Security
security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Get the current authenticated user."""
    token = credentials.credentials
    token_data = verify_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

def get_current_admin_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the current user and verify they have admin role."""
    if not is_admin(db, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

# Health check
@API.get("/health")
def health():
    return {"ok": True}

# Test endpoint to verify Cerbos routes are registered (no auth required for testing)
print("DEBUG: Defining /cerbos/test endpoint...")
@API.get("/cerbos/test")
def cerbos_test():
    """Test endpoint to verify Cerbos routes are working."""
    print("DEBUG: /cerbos/test endpoint handler called")
    return {"message": "Cerbos routes are registered", "status": "ok"}

# Test dynamic route
@API.get("/test/{test_id}")
def test_dynamic_route(test_id: int):
    """Test if dynamic routes are working."""
    print(f"DEBUG: test_dynamic_route called with test_id: {test_id}")
    return {"test_id": test_id, "message": "Dynamic route working"}

# Permission routes (moved here to avoid conflicts)
@API.get("/permissions/{permission_id}", response_model=PermissionResponse)
def get_permission(permission_id: str, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Get a specific permission by ID (admin only)."""
    print(f"DEBUG: get_permission called with permission_id: {permission_id}")
    print(f"DEBUG: Current user: {current_user.email}")
    
    # Convert string to int
    try:
        permission_id_int = int(permission_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission ID")
    
    permission = db.get(Permission, permission_id_int)
    print(f"DEBUG: Permission found: {permission is not None}")
    
    if not permission:
        print(f"DEBUG: Permission not found for ID: {permission_id}")
        raise HTTPException(status_code=404, detail="Permission not found")
    
    print(f"DEBUG: Permission data: id={permission.id}, name={permission.name}")
    
    return PermissionResponse(
        id=permission.id,
        name=permission.name,
        description=permission.description,
        resource_type=permission.resource_type,
        resource_name=permission.resource_name,
        field_name=permission.field_name,
        action=permission.action,
        created_at=permission.created_at
    )

@API.put("/permissions/{permission_id}", response_model=PermissionResponse)
def update_permission(permission_id: str, permission_data: PermissionCreate, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Update a permission (admin only)."""
    # Convert string to int
    try:
        permission_id_int = int(permission_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission ID")
    
    permission = db.get(Permission, permission_id_int)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    # Check if name is being changed and if it conflicts with existing permissions
    if permission_data.name != permission.name:
        existing_permission = db.query(Permission).filter(Permission.name == permission_data.name).first()
        if existing_permission:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Permission with this name already exists"
            )
    
    # Update fields
    permission.name = permission_data.name
    permission.description = permission_data.description
    permission.resource_type = permission_data.resource_type
    permission.resource_name = permission_data.resource_name
    permission.field_name = permission_data.field_name
    permission.action = permission_data.action
    
    db.commit()
    db.refresh(permission)
    
    return PermissionResponse(
        id=permission.id,
        name=permission.name,
        description=permission.description,
        resource_type=permission.resource_type,
        resource_name=permission.resource_name,
        field_name=permission.field_name,
        action=permission.action,
        created_at=permission.created_at
    )

@API.delete("/permissions/{permission_id}")
def delete_permission(permission_id: str, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Delete a permission (admin only)."""
    # Convert string to int
    try:
        permission_id_int = int(permission_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid permission ID")
    
    permission = db.get(Permission, permission_id_int)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    
    db.delete(permission)
    db.commit()
    return {"message": f"Permission {permission_id} deleted successfully"}

# Delete a specific query
@API.delete("/query/{query_id}")
def delete_query(query_id: str, current_user: User = Depends(get_current_user)):
    """Delete a specific query and all its associated data."""
    query_db = get_query_db_sync()
    
    try:
        # Find the query and verify ownership
        query = query_db.query(Query).filter(
            Query.id == query_id,
            Query.user_id == current_user.id
        ).first()
        
        if not query:
            raise HTTPException(status_code=404, detail="Query not found or access denied")
        
        # Delete associated data (cascade should handle this, but being explicit)
        query_db.query(QueryResult).filter(QueryResult.query_id == query_id).delete()
        query_db.query(QueryColumn).filter(QueryColumn.query_id == query_id).delete()
        query_db.query(QueryStat).filter(QueryStat.query_id == query_id).delete()
        
        # Delete the query itself
        query_db.delete(query)
        query_db.commit()
        
        return {"success": True, "message": "Query deleted successfully"}
        
    except Exception as e:
        query_db.rollback()
        print(f"Error deleting query {query_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete query")

# Clear all queries for a user
@API.delete("/queries")
def clear_user_queries(current_user: User = Depends(get_current_user)):
    """Clear all queries for the current user."""
    query_db = get_query_db_sync()
    
    try:
        # Get all queries for the user
        user_queries = query_db.query(Query).filter(Query.user_id == current_user.id).all()
        
        if not user_queries:
            return {"success": True, "message": "No queries to clear"}
        
        # Delete all associated data for user's queries
        for query in user_queries:
            query_db.query(QueryResult).filter(QueryResult.query_id == query.id).delete()
            query_db.query(QueryColumn).filter(QueryColumn.query_id == query.id).delete()
            query_db.query(QueryStat).filter(QueryStat.query_id == query.id).delete()
        
        # Delete all user's queries
        query_db.query(Query).filter(Query.user_id == current_user.id).delete()
        query_db.commit()
        
        return {"success": True, "message": f"Cleared {len(user_queries)} queries"}
        
    except Exception as e:
        query_db.rollback()
        print(f"Error clearing queries for user {current_user.id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear queries")

# Authentication endpoints
@API.post("/auth/login", response_model=LoginResponse)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    access_token = create_access_token(
        data={"sub": user.email, "user_id": user.id}
    )
    
    roles = get_user_roles(db, user.id)
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        is_active=user.is_active,
        created_at=user.created_at,
        roles=roles
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_response
    )

@API.get("/auth/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information."""
    roles = get_user_roles(db, current_user.id)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        roles=roles
    )

# User management endpoints (admin only)
@API.post("/users", response_model=dict)
def create_user(user_data: UserCreate, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Create a new user (admin only)."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": db_user.id, "message": "User created successfully"}

@API.get("/users", response_model=list[UserResponse])
def list_users(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """List all users (admin only)."""
    users = db.query(User).all()
    result = []
    for user in users:
        roles = get_user_roles(db, user.id)
        result.append(UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.created_at,
            roles=roles
        ))
    return result

@API.put("/users/{user_id}", response_model=dict)
def update_user(user_id: int, user_data: UserUpdate, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Update a user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = user_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.commit()
    return {"message": "User updated successfully"}

# Role management endpoints (admin only)
@API.post("/roles", response_model=RoleResponse)
def create_role(role_data: RoleCreate, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Create a new role (admin only)."""
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )
    
    db_role = Role(name=role_data.name, description=role_data.description)
    db.add(db_role)
    db.commit()
    db.refresh(db_role)
    return RoleResponse(
        id=db_role.id,
        name=db_role.name,
        description=db_role.description,
        created_at=db_role.created_at
    )

@API.get("/roles", response_model=list[RoleResponse])
def list_roles(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """List all roles (admin only)."""
    roles = db.query(Role).all()
    return [
        RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description,
            created_at=role.created_at
        ) for role in roles
    ]

# Permission management endpoints (admin only)
@API.post("/permissions", response_model=PermissionResponse)
def create_permission(permission_data: PermissionCreate, current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """Create a new permission (admin only)."""
    existing_permission = db.query(Permission).filter(Permission.name == permission_data.name).first()
    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permission with this name already exists"
        )
    
    db_permission = Permission(
        name=permission_data.name,
        description=permission_data.description,
        resource_type=permission_data.resource_type,
        resource_name=permission_data.resource_name,
        field_name=permission_data.field_name,
        action=permission_data.action
    )
    db.add(db_permission)
    db.commit()
    db.refresh(db_permission)
    return PermissionResponse(
        id=db_permission.id,
        name=db_permission.name,
        description=db_permission.description,
        resource_type=db_permission.resource_type,
        resource_name=db_permission.resource_name,
        field_name=db_permission.field_name,
        action=db_permission.action,
        created_at=db_permission.created_at
    )

@API.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """List all permissions (admin only)."""
    permissions = db.query(Permission).all()
    return [
        PermissionResponse(
            id=permission.id,
            name=permission.name,
            description=permission.description,
            resource_type=permission.resource_type,
            resource_name=permission.resource_name,
            field_name=permission.field_name,
            action=permission.action,
            created_at=permission.created_at
        ) for permission in permissions
    ]



# Existing policy endpoints (now require authentication)
@API.get("/policies")
def list_policies(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all policies (requires authentication)."""
    rows = db.execute(select(Policy).order_by(Policy.id.desc())).scalars().all()
    return [dict(id=p.id, name=p.name, path=p.path, version=p.version,
                published=p.published, bundle_name=p.bundle_name, 
                created_at=p.created_at, created_by=p.created_by) for p in rows]

@API.get("/policies/{policy_id}")
def get_policy(policy_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get a specific policy by ID (requires authentication)."""
    print(f"DEBUG: get_policy called with policy_id: {policy_id}")
    print(f"DEBUG: Current user: {current_user.email}")
    
    policy = db.get(Policy, policy_id)
    print(f"DEBUG: Policy found: {policy is not None}")
    
    if not policy:
        print(f"DEBUG: Policy not found for ID: {policy_id}")
        raise HTTPException(status_code=404, detail="Policy not found")
    
    print(f"DEBUG: Policy data: id={policy.id}, name={policy.name}, rego_text length={len(policy.rego_text) if policy.rego_text else 0}")
    
    return {
        "id": policy.id,
        "name": policy.name,
        "path": policy.path,
        "rego_text": policy.rego_text,
        "version": policy.version,
        "published": policy.published,
        "bundle_name": policy.bundle_name,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
        "created_by": policy.created_by
    }

@API.post("/policies")
def create_policy(item: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new policy (requires authentication)."""
    required = {"name","path","rego_text"}
    if not required.issubset(item.keys()):
        raise HTTPException(400, f"Missing {required - set(item.keys())}")
    p = Policy(
        name=item["name"], path=item["path"], rego_text=item["rego_text"],
        version=item.get("version", 1),
        published=bool(item.get("published", False)),
        bundle_name=item.get("bundle_name","main"),
        created_by=item.get("created_by","api")
    )
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id}

@API.post("/policies/{policy_id}/publish")
def publish_policy(policy_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Publish a policy (requires authentication)."""
    p = db.get(Policy, policy_id)
    if not p: raise HTTPException(404, "not found")
    db.execute(update(Policy).where(Policy.id==policy_id).values(published=True))
    db.commit()
    return {"ok": True}

@API.post("/policies/{policy_id}/unpublish")
def unpublish_policy(policy_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Unpublish a policy (requires authentication)."""
    p = db.get(Policy, policy_id)
    if not p: raise HTTPException(404, "not found")
    db.execute(update(Policy).where(Policy.id==policy_id).values(published=False))
    db.commit()
    return {"ok": True}

@API.put("/policies/{policy_id}")
def update_policy(policy_id: int, item: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a policy (requires authentication)."""
    p = db.get(Policy, policy_id)
    if not p: raise HTTPException(404, "Policy not found")
    
    # Update fields if provided
    if "name" in item:
        p.name = item["name"]
    if "path" in item:
        p.path = item["path"]
    if "rego_text" in item:
        p.rego_text = item["rego_text"]
    if "bundle_name" in item:
        p.bundle_name = item["bundle_name"]
    
    p.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(p)
    return {"message": f"Policy {policy_id} updated successfully"}

@API.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a policy (requires authentication)."""
    p = db.get(Policy, policy_id)
    if not p: raise HTTPException(404, "Policy not found")
    db.delete(p)
    db.commit()
    return {"message": f"Policy {policy_id} deleted successfully"}

# =============================================================================
# Cerbos Policy Management Endpoints (Legacy - removed duplicate)
# The correct endpoints are defined later in the file starting at line ~1242
# =============================================================================

# Removed duplicate /cerbos/policies/validate endpoint - using the one at line ~1447
# Removed duplicate /cerbos/health endpoint - can be added back if needed

# Graph Query endpoint: Execute Cypher/Gremlin queries via PuppyGraph with Cerbos authorization
@API.post("/query/graph")
def execute_graph_query(
    query_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a graph query (Cypher or Gremlin) via PuppyGraph with Cerbos authorization."""
    # Check if PuppyGraph is available
    try:
        from puppygraph_client import get_puppygraph_client
    except ImportError:
        raise HTTPException(status_code=503, detail="PuppyGraph client not available. Please ensure PuppyGraph is configured.")
    
    query = query_data.get("query", "").strip()
    query_type = query_data.get("type", "cypher").lower()  # "cypher" or "gremlin"
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    if query_type not in ["cypher", "gremlin"]:
        raise HTTPException(status_code=400, detail="Query type must be 'cypher' or 'gremlin'")
    
    # Parse Cypher query if it's a Cypher query
    cypher_metadata = {}
    resource_attributes = {}
    
    if query_type == "cypher":
        try:
            from cypher_parser import parse_cypher_query, extract_resource_attributes
            
            # Parse query to extract metadata
            cypher_metadata = parse_cypher_query(query)
            
            # Extract resource attributes from WHERE clauses
            resource_attributes = extract_resource_attributes(query)
            
            # Convert sets to lists for JSON serialization
            if "node_labels" in cypher_metadata:
                cypher_metadata["node_labels"] = list(cypher_metadata["node_labels"])
            if "relationship_types" in cypher_metadata:
                cypher_metadata["relationship_types"] = list(cypher_metadata["relationship_types"])
            
            logger.debug(f"Parsed Cypher query metadata: {cypher_metadata}")
            logger.debug(f"Extracted resource attributes: {resource_attributes}")
        except ImportError:
            logger.warning("cypher_parser module not available, skipping query parsing")
        except Exception as e:
            logger.warning(f"Error parsing Cypher query: {e}, continuing with basic authorization")
    
    # Check authorization with Cerbos
    cerbos_client = get_cerbos_client()
    user_roles = get_user_roles(db, current_user.id)
    
    # Build resource attributes for Cerbos
    cerbos_attributes = {
        "query_type": query_type,
        "query": query,
        **cypher_metadata,
        **resource_attributes
    }
    
    # Use cypher_query resource kind for Cypher queries, transaction for backward compatibility
    resource_kind = "cypher_query" if query_type == "cypher" else "transaction"
    action = "execute" if query_type == "cypher" else "graph_expand"
    
    # Check if user can execute graph queries
    allowed, reason, policy = cerbos_client.check_resource_access(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind=resource_kind,
        resource_id="graph-query",
        action=action,
        attributes=cerbos_attributes
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail=reason or "Not authorized to execute graph queries")
    
    # Log authorization decision
    log_authorization_decision(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind=resource_kind,
        action=action,
        allowed=True,
        reason="Graph query authorized",
        query_preview=query[:200],
        policy=policy
    )
    
    # Execute graph query via PuppyGraph
    try:
        puppygraph = get_puppygraph_client()
        import time
        start_time = time.time()
        
        if query_type == "cypher":
            result = puppygraph.execute_cypher(query)
        else:  # gremlin
            result = puppygraph.execute_gremlin(query)
        
        execution_time = (time.time() - start_time) * 1000
        
        # Parse and return result
        # PuppyGraph response format may vary, return raw result for now
        return {
            "success": True,
            "data": result,
            "query_type": query_type,
            "execution_time_ms": execution_time,
            "query": query
        }
    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Graph query failed: {str(e)}")

# SQL Query endpoint: Execute queries with Cerbos authorization
@API.post("/query")
def execute_sql_query(query_data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), query_db: Session = Depends(get_query_db)):
    """Execute SQL query through Trino with Cerbos authorization."""
    import json
    
    print(f"DEBUG: /query endpoint called with data: {query_data}")
    print(f"DEBUG: Current user: {current_user.email}, ID: {current_user.id}")
    
    # Extract query from request
    if "query" not in query_data:
        print("DEBUG: Missing query field in request")
        raise HTTPException(status_code=400, detail="Query field is required")
    
    sql_query = query_data["query"]
    catalog = query_data.get("catalog", "postgres")
    schema = query_data.get("schema", "public")
    
    print(f"DEBUG: SQL Query: {sql_query}")
    print(f"DEBUG: Catalog: {catalog}, Schema: {schema}")
    
    # Get user roles
    user_roles = get_user_roles(db, current_user.id)
    print(f"DEBUG: User roles: {user_roles}")
    
    # Check authorization with Cerbos
    try:
        print("DEBUG: Calling Cerbos for authorization...")
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_query_permission(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            method="POST",
            path="/v1/statement",
            query_body=sql_query
        )
        
        # Log authorization decision for UI display
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="iceberg" if "iceberg." in sql_query.lower() else "postgres",
            action="query",
            allowed=allowed,
            reason=reason,
            query_preview=sql_query[:200],
            policy=policy
        )
        
        if not allowed:
            print(f"DEBUG: Cerbos denied access: {reason}")
            raise HTTPException(
                status_code=403,
                detail=reason or "Query not authorized by Cerbos policy"
            )
        
        print("DEBUG: Cerbos authorized query, proceeding with execution")
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 403)
        raise
    except Exception as e:
        print(f"DEBUG: Cerbos authorization check failed: {e}")
        # Fail closed - deny access on error
        raise HTTPException(
            status_code=503,
            detail=f"Authorization service unavailable: {str(e)}"
        )
    
    # Execute the query through Trino using the official Python client
    from trino_client import get_trino_client
    
    try:
        # Get Trino client and execute query
        trino_client = get_trino_client()
        username = current_user.email.split("@")[0]
        
        print(f"DEBUG: Executing query with Trino client for user: {username}")
        print(f"DEBUG: Query: {sql_query}")
        print(f"DEBUG: Catalog: {catalog}, Schema: {schema}")
        
        # Execute query with automatic result handling
        with trino_client.execute_query(username, catalog, schema, sql_query) as (success, data, columns, error):
            if success:
                # Query executed successfully - store results immediately
                from datetime import datetime
                import uuid
                
                # Generate a unique query ID
                query_id = str(uuid.uuid4())
                
                # Store the query and results in the database
                new_query = Query(
                    id=query_id,  # Use the generated UUID as the primary key
                    user_id=current_user.id,
                    user_email=current_user.email,
                    sql_query=sql_query,
                    catalog=catalog,
                    schema=schema,
                    status="FINISHED",
                    submitted_at=datetime.now(),
                    completed_at=datetime.now(),
                    trino_query_id=query_id,
                    trino_next_uri=None,  # Not needed with client approach
                    trino_info_uri=None    # Not needed with client approach
                )
                query_db.add(new_query)
                query_db.commit()
                
                # Store the results immediately
                if data and columns:
                    from query_models import QueryColumn, QueryResult
                    
                    # Store columns
                    for i, col in enumerate(columns):
                        column = QueryColumn(
                            query_id=new_query.id,
                            column_name=col.get("name", f"col_{i}"),
                            column_type=col.get("type", "unknown"),
                            column_position=i
                        )
                        query_db.add(column)
                    
                    # Store results
                    for row_num, row in enumerate(data):
                        for col_pos, cell_value in enumerate(row):
                            result = QueryResult(
                                query_id=new_query.id,
                                row_number=row_num,
                                column_position=col_pos,
                                cell_value=str(cell_value) if cell_value is not None else None
                            )
                            query_db.add(result)
                    
                    query_db.commit()
                    print(f"DEBUG: Results stored immediately for query {new_query.id}")
                
                return {
                    "success": True,
                    "query_id": new_query.id,
                    "status": "FINISHED",
                    "next_uri": None,  # Not needed with client approach
                    "info_uri": None,   # Not needed with client approach
                    "message": "Query executed successfully using Trino client",
                    "data": data,
                    "columns": columns
                }
            else:
                # Query failed
                return {
                    "success": False,
                    "error": error or "Unknown Trino error",
                    "code": "trino_error"
                }
                
    except Exception as e:
        print(f"DEBUG: Error executing query with Trino client: {e}")
        return {
            "success": False,
            "error": f"Failed to execute query: {str(e)}",
            "code": "execution_error"
        }


def _get_results_from_uri_with_session(uri: str, username: str, catalog: str, schema: str) -> dict:
    """Helper function to get results from a specific URI with proper Trino session management."""
    import requests
    
    try:
        print(f"DEBUG: Getting results from URI: {uri}")
        print(f"DEBUG: Using session context - User: {username}, Catalog: {catalog}, Schema: {schema}")
        
        # CRITICAL: Use the same headers and session context as the initial request
        headers = {
            "Content-Type": "text/plain",
            "X-Trino-User": username,
            "X-Trino-Catalog": catalog,
            "X-Trino-Schema": schema
        }
        
        print(f"DEBUG: Request headers: {headers}")
        
        # Make the request with proper session context
        response = requests.get(uri, headers=headers, timeout=10)
        
        print(f"DEBUG: Response status: {response.status_code}")
        print(f"DEBUG: Response size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"DEBUG: Response data keys: {list(data.keys()) if data else 'None'}")
                print(f"DEBUG: Response has data field: {'data' in data}")
                print(f"DEBUG: Response has columns field: {'columns' in data}")
                
                if data.get('data') and data.get('columns'):
                    print(f"DEBUG: Successfully retrieved results from URI")
                    print(f"DEBUG: Data rows: {len(data.get('data', []))}")
                    print(f"DEBUG: Columns: {[col.get('name') for col in data.get('columns', [])]}")
                    return data
                else:
                    print(f"DEBUG: URI returned data but missing data/columns fields")
                    print(f"DEBUG: Available fields: {list(data.keys()) if data else 'None'}")
                    return None
            except Exception as parse_error:
                print(f"DEBUG: Error parsing JSON response: {parse_error}")
                print(f"DEBUG: Response body (first 200 chars): {response.text[:200]}")
                return None
        else:
            print(f"DEBUG: URI returned status {response.status_code}")
            print(f"DEBUG: Error response body: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"DEBUG: Error getting results from URI: {e}")
        print(f"DEBUG: Exception type: {type(e).__name__}")
        return None

def _store_query_results(query: Query, trino_data: dict, query_db: Session):
    """Helper function to store query results in the database."""
    try:
        # Store columns
        if "columns" in trino_data:
            for i, col in enumerate(trino_data["columns"]):
                column = QueryColumn(
                    query_id=query.id,
                    column_name=col.get("name", f"col_{i}"),
                    column_type=col.get("type", "unknown"),
                    column_position=i
                )
                query_db.add(column)
        
        # Store results
        if "data" in trino_data:
            for row_num, row in enumerate(trino_data["data"]):
                for col_pos, cell_value in enumerate(row):
                    result = QueryResult(
                        query_id=query.id,
                        row_number=row_num,
                        column_position=col_pos,
                        cell_value=str(cell_value) if cell_value is not None else None
                    )
                    query_db.add(result)
        
        # Store stats
        if "stats" in trino_data:
            for stat_name, stat_value in trino_data["stats"].items():
                stat = QueryStat(
                    query_id=query.id,
                    stat_name=stat_name,
                    stat_value=str(stat_value) if stat_value is not None else None,
                    stat_type="string"
                )
                query_db.add(stat)
        
        query_db.commit()
        print(f"DEBUG: Stored query results for query: {query.id}")
        
    except Exception as e:
        print(f"Warning: Could not store query results: {e}")
        query_db.rollback()

@API.get("/queries")
def list_user_queries(
    current_user: User = Depends(get_current_user), 
    query_db: Session = Depends(get_query_db),
    page: int = 1,
    per_page: int = 20
):
    """List queries for the current user."""
    try:
        # Get total count
        total = query_db.query(Query).filter(Query.user_id == current_user.id).count()
        
        # Get paginated queries
        offset = (page - 1) * per_page
        queries = query_db.query(Query).filter(
            Query.user_id == current_user.id
        ).order_by(
            Query.submitted_at.desc()
        ).offset(offset).limit(per_page).all()
        
        return {
            "success": True,
            "queries": [query.to_dict() for query in queries],
            "total": total,
            "page": page,
            "per_page": per_page
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch queries: {str(e)}")

@API.get("/query/{query_id}/results")
def get_query_results(query_id: str, current_user: User = Depends(get_current_user)):
    """Get results for a submitted query from stored results."""
    
    # Use synchronous database session
    query_db = get_query_db_sync()
    
    try:
        print(f"DEBUG: Looking for query {query_id} with user_id {current_user.id}")
        
        stored_query = query_db.query(Query).filter(
            Query.id == query_id,
            Query.user_id == current_user.id
        ).first()
        
        if not stored_query:
            print(f"DEBUG: Query not found in database")
            return {
                "success": False,
                "error": "Query not found or access denied",
                "code": "query_not_found"
            }
        
        print(f"DEBUG: Query found: {stored_query.id}, status={stored_query.status}")
        
        # Get stored columns and results
        columns = query_db.query(QueryColumn).filter(
            QueryColumn.query_id == query_id
        ).order_by(QueryColumn.column_position).all()
        
        results = query_db.query(QueryResult).filter(
            QueryResult.query_id == query_id
        ).order_by(QueryResult.row_number, QueryResult.column_position).all()
        
        # Get stored stats
        stats = query_db.query(QueryStat).filter(
            QueryStat.query_id == query_id
        ).all()
        
        # Reconstruct data matrix
        if columns and results:
            # Group results by row
            data_matrix = {}
            for result in results:
                if result.row_number not in data_matrix:
                    data_matrix[result.row_number] = {}
                data_matrix[result.row_number][result.column_position] = result.cell_value
            
            # Convert to list format
            data = []
            for row_num in sorted(data_matrix.keys()):
                row_data = []
                for col_pos in range(len(columns)):
                    row_data.append(data_matrix[row_num].get(col_pos, None))
                data.append(row_data)
            
            # Convert stats to dict
            stats_dict = {stat.stat_name: stat.stat_value for stat in stats}
            
            return {
                "success": True,
                "status": stored_query.status,
                "data": data,
                "columns": [{"name": col.column_name, "type": col.column_type} for col in columns],
                "stats": stats_dict,
                "message": "Query results retrieved from storage"
            }
        else:
            return {
                "success": False,
                "error": "No results found for this query",
                "code": "no_results"
            }
            
    except Exception as e:
        print(f"DEBUG: Error retrieving query results: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "code": "database_error"
        }

@API.get("/query/{query_id}/results-immediate")
def get_query_results_immediate(query_id: str, current_user: User = Depends(get_current_user)):
    """Get results immediately from stored database results (no HTTP API calls)."""
    
    # Use synchronous database session
    query_db = get_query_db_sync()
    
    try:
        print(f"DEBUG: Immediate results lookup for query {query_id}")
        
        stored_query = query_db.query(Query).filter(
            Query.id == query_id,
            Query.user_id == current_user.id
        ).first()
        
        if not stored_query:
            return {
                "success": False,
                "error": "Query not found or access denied",
                "code": "query_not_found"
            }
        
        # Since we're using the Trino client, all results should already be stored
        # Just return the current status and any available results
        if stored_query.status == "FINISHED":
            # Get stored columns and results
            columns = query_db.query(QueryColumn).filter(
                QueryColumn.query_id == query_id
            ).order_by(QueryColumn.column_position).all()
            
            results = query_db.query(QueryResult).filter(
                QueryResult.query_id == query_id
            ).order_by(QueryResult.row_number, QueryResult.column_position).all()
            
            # Get stored stats
            stats = query_db.query(QueryStat).filter(
                QueryStat.query_id == query_id
            ).all()
            
            # Reconstruct data matrix
            if columns and results:
                # Group results by row
                data_matrix = {}
                for result in results:
                    if result.row_number not in data_matrix:
                        data_matrix[result.row_number] = {}
                    data_matrix[result.row_number][result.column_position] = result.cell_value
                
                # Convert to list format
                data = []
                for row_num in sorted(data_matrix.keys()):
                    row_data = []
                    for col_pos in range(len(columns)):
                        row_data.append(data_matrix[row_num].get(col_pos, None))
                    data.append(row_data)
                
                # Convert stats to dict
                stats_dict = {stat.stat_name: stat.stat_value for stat in stats}
                
                return {
                    "success": True,
                    "status": "FINISHED",
                    "data": data,
                    "columns": [{"name": col.column_name, "type": col.column_type} for col in columns],
                    "stats": stats_dict,
                    "message": "Query results retrieved from storage (Trino client mode)"
                }
            else:
                return {
                    "success": True,
                    "status": "FINISHED",
                    "message": "Query completed but no results stored yet",
                    "data": [],
                    "columns": [],
                    "stats": {}
                }
        else:
            # Query not finished yet
            return {
                "success": True,
                "status": stored_query.status,
                "message": f"Query is {stored_query.status.lower()}",
                "data": [],
                "columns": [],
                "stats": {}
            }
            
    except Exception as e:
        print(f"DEBUG: Error retrieving query results: {e}")
        return {
            "success": False,
            "error": f"Database error: {str(e)}",
            "code": "database_error"
        }


@API.post("/query/{query_id}/store-results")
def store_query_results(query_id: str, current_user: User = Depends(get_current_user)):
    """Manually trigger storing results for a completed query (Trino client mode)."""
    
    # Use synchronous database session
    query_db = get_query_db_sync()
    
    try:
        # Get the stored query
        stored_query = query_db.query(Query).filter(
            Query.id == query_id,
            Query.user_id == current_user.id
        ).first()
        
        if not stored_query:
            raise HTTPException(status_code=404, detail="Query not found or access denied")
        
        # Since we're using the Trino client, results should already be stored
        # Just verify the current status and return appropriate message
        if stored_query.status == "FINISHED":
            # Check if results are already stored
            existing_results = query_db.query(QueryResult).filter(
                QueryResult.query_id == query_id
            ).first()
            
            if existing_results:
                return {
                    "success": True,
                    "message": "Query results already stored (Trino client mode)",
                    "status": "already_stored"
                }
            else:
                return {
                    "success": False,
                    "error": "Query completed but no results found in storage",
                    "code": "no_results_stored"
                }
        else:
            return {
                "success": False,
                "error": f"Query not completed yet. Current status: {stored_query.status}",
                "code": "query_not_finished"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check query results: {str(e)}")

@API.post("/query/template")
def execute_query_template(template_data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), query_db: Session = Depends(get_query_db)):
    """Execute a parameterized query template with validation and Cerbos authorization."""
    import re
    
    # Extract template and parameters
    if "template" not in template_data:
        raise HTTPException(status_code=400, detail="Template field is required")
    
    template = template_data["template"]
    parameters = template_data.get("parameters", {})
    
    # Validate template format (prevent SQL injection)
    if not re.match(r'^[A-Za-z\s\*\(\)\.,\-\+\/\%\<\>\=\!\?\_\[\]\{\}\|\&\^~`@#$]+$', template):
        raise HTTPException(status_code=400, detail="Invalid template format")
    
    # Validate parameters (only allow alphanumeric and basic punctuation)
    for key, value in parameters.items():
        if not re.match(r'^[A-Za-z0-9\s\.,\-\_\?]+$', str(value)):
            raise HTTPException(status_code=400, detail=f"Invalid parameter value for {key}")
    
    # Build the final query by replacing parameters
    sql_query = template
    for key, value in parameters.items():
        placeholder = f"{{{key}}}"
        if placeholder in sql_query:
            sql_query = sql_query.replace(placeholder, str(value))
    
    # Extract catalog and schema from template or use defaults
    catalog = template_data.get("catalog", "postgres")
    schema = template_data.get("schema", "public")
    
    # Get user roles
    user_roles = get_user_roles(db, current_user.id)
    
    # Check authorization with Cerbos
    try:
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_query_permission(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            method="POST",
            path="/query/template",
            query_body=sql_query
        )
        
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=reason or "Query template not authorized by Cerbos policy"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Authorization service unavailable: {str(e)}"
        )
    
    # Execute the query through Trino using the official Python client
    from trino_client import get_trino_client
    
    try:
        # Get Trino client and execute query
        trino_client = get_trino_client()
        username = current_user.email.split("@")[0]
        
        # Execute query with automatic result handling
        with trino_client.execute_query(username, catalog, schema, sql_query) as (success, data, columns, error):
            if success:
                # Query executed successfully - store results immediately
                from datetime import datetime
                import uuid
                
                # Generate a unique query ID
                query_id = str(uuid.uuid4())
                
                # Store the query and results in the database
                new_query = Query(
                    user_id=current_user.id,
                    sql_query=sql_query,
                    catalog=catalog,
                    schema=schema,
                    status="FINISHED",
                    submitted_at=datetime.now(),
                    completed_at=datetime.now(),
                    trino_query_id=query_id,
                    trino_next_uri=None,  # Not needed with client approach
                    trino_info_uri=None    # Not needed with client approach
                )
                query_db.add(new_query)
                query_db.commit()
                
                # Store the results immediately
                if data and columns:
                    from query_models import QueryColumn, QueryResult
                    
                    # Store columns
                    for i, col in enumerate(columns):
                        column = QueryColumn(
                            query_id=new_query.id,
                            column_name=col.get("name", f"col_{i}"),
                            column_type=col.get("type", "unknown"),
                            column_position=i
                        )
                        query_db.add(column)
                    
                    # Store results
                    for row_num, row in enumerate(data):
                        for col_pos, cell_value in enumerate(row):
                            result = QueryResult(
                                query_id=new_query.id,
                                row_number=row_num,
                                column_position=col_pos,
                                cell_value=str(cell_value) if cell_value is not None else None
                            )
                            query_db.add(result)
                    
                    query_db.commit()
                    logger.info(f"Results stored immediately for query {new_query.id}")
                
                return {
                    "success": True,
                    "query_id": new_query.id,
                    "status": "FINISHED",
                    "next_uri": None,  # Not needed with client approach
                    "info_uri": None,   # Not needed with client approach
                    "template_used": template,
                    "parameters_applied": parameters,
                    "final_query": sql_query,
                    "message": "Query executed successfully using Trino client",
                    "data": data,
                    "columns": columns
                }
            else:
                # Query failed
                return {
                    "success": False,
                    "error": error or "Unknown Trino error",
                    "code": "trino_error"
                }
                
    except Exception as e:
        logger.error(f"Error executing query with Trino client: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to execute query: {str(e)}")

# =============================================================================
# Cerbos Policy Management Endpoints
# =============================================================================

# Debug: Print that we're defining Cerbos routes
print("DEBUG: Defining Cerbos policy endpoints...")

@API.get("/cerbos/policies")
def list_cerbos_policies(current_user: User = Depends(get_current_admin_user), db: Session = Depends(get_db)):
    """List all Cerbos policies."""
    logger.info("GET /cerbos/policies endpoint called")
    print("DEBUG: /cerbos/policies endpoint handler called")
    import os
    import glob
    
    policies_dir = os.getenv("CERBOS_POLICIES_DIR", "/policies")
    logger.info(f"Looking for policies in: {policies_dir}")
    
    if not os.path.exists(policies_dir):
        # Fallback to local cerbos directory
        fallback_dir = os.path.join(os.path.dirname(__file__), "../../cerbos/policies")
        logger.info(f"Policies directory not found at {policies_dir}, trying fallback: {fallback_dir}")
        if os.path.exists(fallback_dir):
            policies_dir = fallback_dir
        else:
            logger.error(f"Neither {policies_dir} nor {fallback_dir} exist")
            return {"policies": []}
    
    logger.info(f"Scanning policies directory: {policies_dir}")
    policies = []
    
    # Find all YAML files in policies directory
    for root, dirs, files in os.walk(policies_dir):
        # Skip hidden directories and test directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'tests']
        
        for file in files:
            if file.endswith(('.yaml', '.yml')) and not file.endswith('.bak'):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, policies_dir)
                
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        policy_type = "resource" if "resourcePolicy" in content else "principal" if "principalPolicy" in content else "unknown"
                        policies.append({
                            "path": rel_path,
                            "content": content,
                            "type": policy_type
                        })
                        logger.info(f"Loaded policy: {rel_path} (type: {policy_type})")
                except Exception as e:
                    logger.error(f"Error reading policy file {file_path}: {e}")
    
    logger.info(f"Found {len(policies)} policies")
    return {"policies": policies}


@API.get("/cerbos/policies/{policy_path:path}")
def get_cerbos_policy(policy_path: str, current_user: User = Depends(get_current_admin_user)):
    """Get a specific Cerbos policy by path."""
    import os
    
    policies_dir = os.getenv("CERBOS_POLICIES_DIR", "/policies")
    if not os.path.exists(policies_dir):
        policies_dir = os.path.join(os.path.dirname(__file__), "../../cerbos/policies")
    
    # Sanitize path to prevent directory traversal
    policy_path = os.path.normpath(policy_path).lstrip('/')
    full_path = os.path.join(policies_dir, policy_path)
    
    # Ensure path is within policies directory
    if not os.path.commonpath([policies_dir, full_path]) == policies_dir:
        raise HTTPException(status_code=400, detail="Invalid policy path")
    
    if not os.path.exists(full_path) or not full_path.endswith(('.yaml', '.yml')):
        raise HTTPException(status_code=404, detail="Policy not found")
    
    try:
        with open(full_path, 'r') as f:
            content = f.read()
            return {
                "path": policy_path,
                "content": content
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading policy: {str(e)}")


@API.post("/cerbos/policies")
def create_cerbos_policy(policy_data: dict, current_user: User = Depends(get_current_admin_user)):
    """Create a new Cerbos policy."""
    import os
    import yaml
    
    policy_path = policy_data.get("path")
    content = policy_data.get("content")
    
    if not policy_path or not content:
        raise HTTPException(status_code=400, detail="path and content are required")
    
    # Validate YAML syntax
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    
    policies_dir = os.getenv("CERBOS_POLICIES_DIR", "/policies")
    if not os.path.exists(policies_dir):
        policies_dir = os.path.join(os.path.dirname(__file__), "../../cerbos/policies")
    
    # Sanitize path
    policy_path = os.path.normpath(policy_path).lstrip('/')
    full_path = os.path.join(policies_dir, policy_path)
    
    # Ensure path is within policies directory
    if not os.path.commonpath([policies_dir, full_path]) == policies_dir:
        raise HTTPException(status_code=400, detail="Invalid policy path")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # Write policy file
    try:
        with open(full_path, 'w') as f:
            f.write(content)
        
        # Note: In production, you'd want to trigger Cerbos to reload policies
        # For now, Cerbos watches the directory, so it should auto-reload
        
        return {
            "path": policy_path,
            "message": "Policy created successfully",
            "reload_required": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error writing policy: {str(e)}")


@API.put("/cerbos/policies/{policy_path:path}")
def update_cerbos_policy(policy_path: str, policy_data: dict, current_user: User = Depends(get_current_admin_user)):
    """Update a Cerbos policy."""
    import os
    import yaml
    
    content = policy_data.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    
    # Validate YAML syntax
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    
    policies_dir = os.getenv("CERBOS_POLICIES_DIR", "/policies")
    if not os.path.exists(policies_dir):
        policies_dir = os.path.join(os.path.dirname(__file__), "../../cerbos/policies")
    
    # Sanitize path
    policy_path = os.path.normpath(policy_path).lstrip('/')
    full_path = os.path.join(policies_dir, policy_path)
    
    # Ensure path is within policies directory
    if not os.path.commonpath([policies_dir, full_path]) == policies_dir:
        raise HTTPException(status_code=400, detail="Invalid policy path")
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Policy not found")
    
    try:
        with open(full_path, 'w') as f:
            f.write(content)
        
        return {
            "path": policy_path,
            "message": "Policy updated successfully",
            "reload_required": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating policy: {str(e)}")


@API.delete("/cerbos/policies/{policy_path:path}")
def delete_cerbos_policy(policy_path: str, current_user: User = Depends(get_current_admin_user)):
    """Delete a Cerbos policy."""
    import os
    
    policies_dir = os.getenv("CERBOS_POLICIES_DIR", "/policies")
    if not os.path.exists(policies_dir):
        policies_dir = os.path.join(os.path.dirname(__file__), "../../cerbos/policies")
    
    # Sanitize path
    policy_path = os.path.normpath(policy_path).lstrip('/')
    full_path = os.path.join(policies_dir, policy_path)
    
    # Ensure path is within policies directory
    if not os.path.commonpath([policies_dir, full_path]) == policies_dir:
        raise HTTPException(status_code=400, detail="Invalid policy path")
    
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Policy not found")
    
    try:
        os.remove(full_path)
        return {
            "path": policy_path,
            "message": "Policy deleted successfully",
            "reload_required": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting policy: {str(e)}")


@API.post("/cerbos/policies/validate")
def validate_cerbos_policy(policy_data: dict, current_user: User = Depends(get_current_admin_user)):
    """Validate a Cerbos policy YAML."""
    import yaml
    
    content = policy_data.get("content")
    if not content:
        raise HTTPException(status_code=400, detail="content is required")
    
    try:
        parsed = yaml.safe_load(content)
        
        # Basic validation - check for required Cerbos policy fields
        if "resourcePolicy" not in parsed and "principalPolicy" not in parsed:
            return {
                "valid": False,
                "errors": ["Policy must be either a resourcePolicy or principalPolicy"]
            }
        
        return {
            "valid": True,
            "message": "Policy syntax is valid"
        }
    except yaml.YAMLError as e:
        return {
            "valid": False,
            "errors": [f"YAML syntax error: {str(e)}"]
        }


@API.get("/cerbos/logs")
def get_cerbos_logs(current_user: User = Depends(get_current_admin_user), lines: int = 200):
    """Get Cerbos container logs to demonstrate authorization as a service."""
    import subprocess
    import json
    
    try:
        # Get logs from Cerbos container
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), "pg-cerbos-cerbos", "--timestamps"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode != 0:
            logger.warning(f"Failed to get Cerbos logs: {result.stderr}")
            # Fallback: return backend authorization logs
            return get_backend_authz_logs(lines)
        
        # Parse JSON logs if available, otherwise return as text
        log_lines = result.stdout.strip().split('\n')
        parsed_logs = []
        
        for line in log_lines:
            if not line.strip():
                continue
            
            # Extract timestamp if present (Docker logs format: 2024-01-01T12:00:00.000000000Z message)
            timestamp = ""
            message = line
            if line.startswith("20") and "T" in line[:30]:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    timestamp = parts[0]
                    message = parts[1]
            
            try:
                log_entry = json.loads(message)
                parsed_logs.append({
                    "timestamp": log_entry.get("ts", timestamp),
                    "level": log_entry.get("level", "info"),
                    "message": log_entry.get("msg", message),
                    "call_id": log_entry.get("callID", ""),
                    "method": log_entry.get("method", ""),
                    "raw": line,
                    "type": "cerbos"
                })
            except json.JSONDecodeError:
                # Not JSON, treat as plain text
                # Check if it's an authorization-related log
                is_authz = "CheckResources" in message or "authorization" in message.lower() or "EFFECT" in message
                parsed_logs.append({
                    "timestamp": timestamp,
                    "level": "info",
                    "message": message,
                    "call_id": "",
                    "method": "CheckResources" if is_authz else "",
                    "raw": line,
                    "type": "cerbos"
                })
        
        # Also include backend authorization logs
        backend_logs = get_backend_authz_logs(50)
        if backend_logs.get("logs"):
            parsed_logs.extend(backend_logs["logs"])
        
        # Sort by timestamp (newest first)
        parsed_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return {
            "logs": parsed_logs[:lines],
            "total": len(parsed_logs)
        }
        
    except subprocess.TimeoutExpired:
        return get_backend_authz_logs(lines)
    except FileNotFoundError:
        return get_backend_authz_logs(lines)
    except Exception as e:
        logger.error(f"Error fetching Cerbos logs: {e}", exc_info=True)
        return get_backend_authz_logs(lines)


def get_backend_authz_logs(lines: int = 100):
    """Get authorization logs from backend (fallback when Docker logs unavailable)."""
    global _authorization_decisions
    
    logs = []
    
    # Convert authorization decisions to log format
    for decision in _authorization_decisions[-lines:]:
        policy_name = decision.get('policy', decision.get('resource_kind', 'unknown'))
        decision_text = (
            f"Cerbos Authorization Decision: {decision['decision']} | "
            f"User: {decision['user_email']} ({decision['user_id']}) | "
            f"Roles: {', '.join(decision['user_roles'])} | "
            f"Resource: {decision['resource_kind']} | "
            f"Action: {decision['action']} | "
            f"Policy: {policy_name}"
        )
        if decision.get('query_preview'):
            decision_text += f" | Query: {decision['query_preview'][:100]}..."
        if decision.get('reason') and not decision['allowed']:
            decision_text += f" | Reason: {decision['reason']}"
        
        logs.append({
            "timestamp": decision['timestamp'],
            "level": "info",
            "message": decision_text,
            "call_id": f"authz-{decision['user_id']}-{decision['timestamp']}",
            "method": "CheckResources",
            "raw": decision_text,
            "type": "authorization",
            "decision": decision['decision'],
            "user_email": decision['user_email'],
            "resource_kind": decision['resource_kind'],
            "policy": policy_name
        })
    
    if not logs:
        logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": "info",
            "message": "No authorization decisions yet. Run queries in the SQL Query tab to see Cerbos authorization checks.",
            "call_id": "",
            "method": "",
            "raw": "",
            "type": "info"
        })
    
    return {
        "logs": logs,
        "total": len(logs)
    }


# =============================================================================
# AML (Anti-Money Laundering) API Endpoints
# =============================================================================

if AML_AVAILABLE:
    from trino_client import get_trino_client
    
    @API.get("/aml/alerts", response_model=List[AlertResponse])
    def list_alerts(
        status: Optional[str] = None,
        severity: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """List AML alerts with optional filtering."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=get_user_roles(db, current_user.id),
            resource_kind="alert",
            resource_id="*",
            action="view"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to view alerts")
        
        # Build query
        query = "SELECT * FROM postgres.demo_data.aml.alert WHERE 1=1"
        params = []
        if status:
            query += " AND status = %s"
            params.append(status)
        if severity:
            query += " AND severity = %s"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT 100"
        
        # Execute via Trino
        trino = get_trino_client()
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success:
                raise HTTPException(status_code=500, detail=error or "Failed to fetch alerts")
            
            # Convert to response models
            alerts = []
            for row in data:
                alerts.append(AlertResponse(
                    alert_id=row[0],
                    alert_type=row[1],
                    created_at=row[2],
                    severity=row[3],
                    status=row[4],
                    primary_customer_id=row[5],
                    primary_account_id=row[6]
                ))
            return alerts
    
    @API.get("/aml/alerts/{alert_id}", response_model=AlertResponse)
    def get_alert(
        alert_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Get a specific alert by ID."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=get_user_roles(db, current_user.id),
            resource_kind="alert",
            resource_id=str(alert_id),
            action="view"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to view this alert")
        
        # Fetch alert
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.alert WHERE alert_id = {alert_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Alert not found")
            
            row = data[0]
            return AlertResponse(
                alert_id=row[0],
                alert_type=row[1],
                created_at=row[2],
                severity=row[3],
                status=row[4],
                primary_customer_id=row[5],
                primary_account_id=row[6]
            )
    
    @API.post("/aml/alerts/{alert_id}/escalate", response_model=CaseResponse)
    def escalate_alert(
        alert_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Escalate an alert to create a case."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=get_user_roles(db, current_user.id),
            resource_kind="alert",
            resource_id=str(alert_id),
            action="escalate"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to escalate this alert")
        
        # Get alert first
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.alert WHERE alert_id = {alert_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Alert not found")
        
        # Create case
        insert_query = f"""
            INSERT INTO postgres.demo_data.aml.case 
            (status, priority, owner_user_id, team, source_alert_id, created_at, updated_at)
            VALUES ('open', 'medium', '{current_user.id}', NULL, {alert_id}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING case_id, status, priority, created_at, updated_at, owner_user_id, team, source_alert_id
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", insert_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=500, detail=error or "Failed to create case")
            
            row = data[0]
            return CaseResponse(
                case_id=row[0],
                status=row[1],
                priority=row[2],
                created_at=row[3],
                updated_at=row[4],
                owner_user_id=row[5],
                team=row[6],
                source_alert_id=row[7]
            )
    
    @API.get("/aml/cases", response_model=List[CaseResponse])
    def list_cases(
        status: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """List AML cases with optional filtering."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=get_user_roles(db, current_user.id),
            resource_kind="case",
            resource_id="*",
            action="view"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to view cases")
        
        # Build query
        query = "SELECT * FROM postgres.demo_data.aml.case WHERE 1=1"
        if status:
            query += f" AND status = '{status}'"
        if owner_user_id:
            query += f" AND owner_user_id = '{owner_user_id}'"
        query += " ORDER BY created_at DESC LIMIT 100"
        
        # Execute via Trino
        trino = get_trino_client()
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success:
                raise HTTPException(status_code=500, detail=error or "Failed to fetch cases")
            
            cases = []
            for row in data:
                cases.append(CaseResponse(
                    case_id=row[0],
                    status=row[1],
                    priority=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                    owner_user_id=row[5],
                    team=row[6],
                    source_alert_id=row[7]
                ))
            return cases
    
    @API.get("/aml/cases/{case_id}", response_model=CaseResponse)
    def get_case(
        case_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Get a specific case by ID."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        # First get case to check ownership
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.case WHERE case_id = {case_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Case not found")
            
            row = data[0]
            case_owner = row[5]  # owner_user_id
            
            # Check authorization with case attributes
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=get_user_roles(db, current_user.id),
                resource_kind="case",
                resource_id=str(case_id),
                action="view",
                attributes={"owner_user_id": case_owner, "status": row[1], "team": row[6] or ""}
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=reason or "Not authorized to view this case")
            
            return CaseResponse(
                case_id=row[0],
                status=row[1],
                priority=row[2],
                created_at=row[3],
                updated_at=row[4],
                owner_user_id=row[5],
                team=row[6],
                source_alert_id=row[7]
            )
    
    @API.post("/aml/cases/{case_id}/notes", response_model=CaseNoteResponse)
    def add_case_note(
        case_id: int,
        note_data: CaseNoteCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Add a note to a case."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        # Get case first to check ownership
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.case WHERE case_id = {case_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Case not found")
            
            row = data[0]
            case_owner = row[5]
            
            # Check authorization
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=get_user_roles(db, current_user.id),
                resource_kind="case",
                resource_id=str(case_id),
                action="add_note",
                attributes={"owner_user_id": case_owner, "status": row[1]}
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=reason or "Not authorized to add notes to this case")
        
        # Insert note
        text_escaped = note_data.text.replace("'", "''")
        insert_query = f"""
            INSERT INTO postgres.demo_data.aml.case_note 
            (case_id, author_user_id, text, created_at)
            VALUES ({case_id}, '{current_user.id}', '{text_escaped}', CURRENT_TIMESTAMP)
            RETURNING note_id, case_id, author_user_id, created_at, text
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", insert_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=500, detail=error or "Failed to create note")
            
            row = data[0]
            return CaseNoteResponse(
                note_id=row[0],
                case_id=row[1],
                author_user_id=row[2],
                created_at=row[3],
                text=row[4]
            )
    
    @API.post("/aml/cases/{case_id}/graph-expand", response_model=GraphResponse)
    def expand_case_graph(
        case_id: int,
        expand_request: GraphExpandRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Expand transaction network from a case using PuppyGraph."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        # Get case first
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.case WHERE case_id = {case_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Case not found")
            
            row = data[0]
            case_owner = row[5]
            
            # Check authorization for graph expansion
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=get_user_roles(db, current_user.id),
                resource_kind="transaction",
                resource_id=f"case-{case_id}",
                action="graph_expand",
                attributes={"case_id": str(case_id), "owner_user_id": case_owner}
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=reason or "Not authorized to expand graph for this case")
        
        # Execute graph query via PuppyGraph
        try:
            puppygraph = get_puppygraph_client()
            
            # Build openCypher query to expand transaction network
            cypher_query = f"""
            MATCH (c:Case {{case_id: {case_id}}})-[:FROM_ALERT]->(a:Alert)-[:FLAGS_CUSTOMER]->(cust:Customer)
            MATCH path = (cust)-[:OWNS]->(acc:Account)-[:SENT_TXN*1..{expand_request.depth}]->(txn:Transaction)
            RETURN c, a, cust, acc, txn
            LIMIT 100
            """
            
            import time
            start_time = time.time()
            result = puppygraph.execute_cypher(cypher_query)
            execution_time = (time.time() - start_time) * 1000
            
            # Parse PuppyGraph response and convert to GraphResponse
            nodes = []
            edges = []
            node_ids = set()  # Track unique nodes
            
            # PuppyGraph typically returns results in a specific format
            # Adjust parsing based on actual API response structure
            if isinstance(result, dict):
                # Handle different possible response formats
                data = result.get("data", result.get("results", []))
                
                for row in data:
                    # Each row contains matched entities
                    # Extract nodes and relationships
                    if isinstance(row, (list, tuple)):
                        for entity in row:
                            if isinstance(entity, dict):
                                # Extract node information
                                label = entity.get("label", entity.get("_label", "Unknown"))
                                node_id = entity.get("id", entity.get("_id"))
                                properties = {k: v for k, v in entity.items() 
                                            if k not in ["label", "_label", "id", "_id"]}
                                
                                if node_id and (label, node_id) not in node_ids:
                                    nodes.append(GraphNode(
                                        label=label,
                                        id=node_id,
                                        properties=properties
                                    ))
                                    node_ids.add((label, node_id))
                    elif isinstance(row, dict):
                        # Single entity or path result
                        for key, value in row.items():
                            if isinstance(value, dict):
                                label = value.get("label", value.get("_label", key))
                                node_id = value.get("id", value.get("_id"))
                                properties = {k: v for k, v in value.items() 
                                            if k not in ["label", "_label", "id", "_id"]}
                                
                                if node_id and (label, node_id) not in node_ids:
                                    nodes.append(GraphNode(
                                        label=label,
                                        id=node_id,
                                        properties=properties
                                    ))
                                    node_ids.add((label, node_id))
            
            # If no nodes found, return empty graph (query may have returned no results)
            # This is valid - the case may not have associated transactions yet
            
            return GraphResponse(
                nodes=nodes,
                edges=edges,  # Edges can be inferred from relationships or parsed separately
                query=cypher_query,
                execution_time_ms=execution_time
            )
        except Exception as e:
            logger.error(f"PuppyGraph query failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Graph expansion failed: {str(e)}")
    
    @API.post("/aml/cases/{case_id}/assign", response_model=CaseResponse)
    def assign_case(
        case_id: int,
        assign_data: CaseAssignRequest,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Assign a case to an analyst (manager only)."""
        # Check authorization - only managers can assign
        cerbos_client = get_cerbos_client()
        user_roles = get_user_roles(db, current_user.id)
        if "aml_manager" not in user_roles:
            raise HTTPException(status_code=403, detail="Only managers can assign cases")
        
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="case",
            resource_id=str(case_id),
            action="assign"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to assign this case")
        
        # Update case
        trino = get_trino_client()
        team_val = f"'{assign_data.team}'" if assign_data.team else "NULL"
        update_query = f"""
            UPDATE postgres.demo_data.aml.case 
            SET owner_user_id = '{assign_data.owner_user_id}', 
                team = {team_val},
                updated_at = CURRENT_TIMESTAMP
            WHERE case_id = {case_id}
            RETURNING case_id, status, priority, created_at, updated_at, owner_user_id, team, source_alert_id
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", update_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=500, detail=error or "Failed to assign case")
            
            row = data[0]
            return CaseResponse(
                case_id=row[0],
                status=row[1],
                priority=row[2],
                created_at=row[3],
                updated_at=row[4],
                owner_user_id=row[5],
                team=row[6],
                source_alert_id=row[7]
            )
    
    @API.post("/aml/cases/{case_id}/close", response_model=CaseResponse)
    def close_case(
        case_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Close a case (analyst if assigned, manager always)."""
        # Get case first
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.case WHERE case_id = {case_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Case not found")
            
            row = data[0]
            case_owner = row[5]
            
            # Check authorization
            cerbos_client = get_cerbos_client()
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=get_user_roles(db, current_user.id),
                resource_kind="case",
                resource_id=str(case_id),
                action="close",
                attributes={"owner_user_id": case_owner, "status": row[1]}
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=reason or "Not authorized to close this case")
        
        # Update case status
        update_query = f"""
            UPDATE postgres.demo_data.aml.case 
            SET status = 'closed', updated_at = CURRENT_TIMESTAMP
            WHERE case_id = {case_id}
            RETURNING case_id, status, priority, created_at, updated_at, owner_user_id, team, source_alert_id
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", update_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=500, detail=error or "Failed to close case")
            
            row = data[0]
            return CaseResponse(
                case_id=row[0],
                status=row[1],
                priority=row[2],
                created_at=row[3],
                updated_at=row[4],
                owner_user_id=row[5],
                team=row[6],
                source_alert_id=row[7]
            )
    
    @API.get("/aml/cases/{case_id}/notes", response_model=List[CaseNoteResponse])
    def list_case_notes(
        case_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """List all notes for a case."""
        # Check case exists and user can view it
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.case WHERE case_id = {case_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Case not found")
            
            row = data[0]
            case_owner = row[5]
            
            # Check authorization
            cerbos_client = get_cerbos_client()
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=get_user_roles(db, current_user.id),
                resource_kind="case",
                resource_id=str(case_id),
                action="view",
                attributes={"owner_user_id": case_owner, "status": row[1]}
            )
            if not allowed:
                raise HTTPException(status_code=403, detail=reason or "Not authorized to view this case")
        
        # Get notes
        notes_query = f"""
            SELECT note_id, case_id, author_user_id, created_at, text
            FROM postgres.demo_data.aml.case_note
            WHERE case_id = {case_id}
            ORDER BY created_at ASC
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", notes_query) as (success, data, columns, error):
            if not success:
                raise HTTPException(status_code=500, detail=error or "Failed to fetch notes")
            
            notes = []
            for row in data:
                notes.append(CaseNoteResponse(
                    note_id=row[0],
                    case_id=row[1],
                    author_user_id=row[2],
                    created_at=row[3],
                    text=row[4]
                ))
            return notes
    
    @API.get("/aml/sars", response_model=List[SARResponse])
    def list_sars(
        status: Optional[str] = None,
        case_id: Optional[int] = None,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """List SARs with optional filtering."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=get_user_roles(db, current_user.id),
            resource_kind="sar",
            resource_id="*",
            action="view"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to view SARs")
        
        # Build query
        query = "SELECT * FROM postgres.demo_data.aml.sar WHERE 1=1"
        if status:
            query += f" AND status = '{status}'"
        if case_id:
            query += f" AND case_id = {case_id}"
        query += " ORDER BY created_at DESC LIMIT 100"
        
        # Execute via Trino
        trino = get_trino_client()
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success:
                raise HTTPException(status_code=500, detail=error or "Failed to fetch SARs")
            
            sars = []
            for row in data:
                sars.append(SARResponse(
                    sar_id=row[0],
                    case_id=row[1],
                    status=row[2],
                    created_at=row[3],
                    submitted_at=row[4] if len(row) > 4 else None
                ))
            return sars
    
    @API.get("/aml/sars/{sar_id}", response_model=SARResponse)
    def get_sar(
        sar_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Get a specific SAR by ID."""
        # Check authorization
        cerbos_client = get_cerbos_client()
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=get_user_roles(db, current_user.id),
            resource_kind="sar",
            resource_id=str(sar_id),
            action="view"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to view this SAR")
        
        # Fetch SAR
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.sar WHERE sar_id = {sar_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="SAR not found")
            
            row = data[0]
            return SARResponse(
                sar_id=row[0],
                case_id=row[1],
                status=row[2],
                created_at=row[3],
                submitted_at=row[4] if len(row) > 4 else None
            )
    
    @API.post("/aml/sars", response_model=SARResponse)
    def create_sar(
        sar_data: SARCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Create a SAR draft (manager only)."""
        # Check authorization - only managers can create SARs
        cerbos_client = get_cerbos_client()
        user_roles = get_user_roles(db, current_user.id)
        if "aml_manager" not in user_roles:
            raise HTTPException(status_code=403, detail="Only managers can create SARs")
        
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            resource_id="new",
            action="draft"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to create SARs")
        
        # Verify case exists
        trino = get_trino_client()
        case_query = f"SELECT * FROM postgres.demo_data.aml.case WHERE case_id = {sar_data.case_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", case_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="Case not found")
        
        # Create SAR
        insert_query = f"""
            INSERT INTO postgres.demo_data.aml.sar 
            (case_id, status, created_at)
            VALUES ({sar_data.case_id}, 'draft', CURRENT_TIMESTAMP)
            RETURNING sar_id, case_id, status, created_at, submitted_at
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", insert_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=500, detail=error or "Failed to create SAR")
            
            row = data[0]
            return SARResponse(
                sar_id=row[0],
                case_id=row[1],
                status=row[2],
                created_at=row[3],
                submitted_at=row[4] if len(row) > 4 else None
            )
    
    @API.post("/aml/sars/{sar_id}/submit", response_model=SARResponse)
    def submit_sar(
        sar_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        """Submit a SAR (manager only)."""
        # Check authorization - only managers can submit SARs
        cerbos_client = get_cerbos_client()
        user_roles = get_user_roles(db, current_user.id)
        if "aml_manager" not in user_roles:
            raise HTTPException(status_code=403, detail="Only managers can submit SARs")
        
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            resource_id=str(sar_id),
            action="submit"
        )
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Not authorized to submit this SAR")
        
        # Get SAR first
        trino = get_trino_client()
        query = f"SELECT * FROM postgres.demo_data.aml.sar WHERE sar_id = {sar_id}"
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=404, detail="SAR not found")
            
            if data[0][2] == "submitted":  # status column
                raise HTTPException(status_code=400, detail="SAR is already submitted")
        
        # Update SAR status
        update_query = f"""
            UPDATE postgres.demo_data.aml.sar 
            SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP
            WHERE sar_id = {sar_id}
            RETURNING sar_id, case_id, status, created_at, submitted_at
        """
        with trino.execute_query(str(current_user.id), "postgres", "demo_data", update_query) as (success, data, columns, error):
            if not success or not data:
                raise HTTPException(status_code=500, detail=error or "Failed to submit SAR")
            
            row = data[0]
            return SARResponse(
                sar_id=row[0],
                case_id=row[1],
                status=row[2],
                created_at=row[3],
                submitted_at=row[4] if len(row) > 4 else None
            )

# =============================================================================
# OPA bundle endpoint (DEPRECATED - OPA has been removed, kept for legacy compatibility)
# =============================================================================

# OPA bundle endpoint: returns a .tar.gz with all published policies for bundle 'main'
# NOTE: This endpoint is deprecated. The system now uses Cerbos for authorization.
# This endpoint is kept only for backward compatibility with legacy OPA editor.
@API.get("/bundles/main.tar.gz", deprecated=True)
def get_bundle(db: Session = Depends(get_db)):
    """Get OPA bundle (DEPRECATED - OPA has been removed, use Cerbos policies instead)."""
    # Return empty bundle since OPA is no longer used
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        pass  # Empty bundle
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openpolicyagent.bundles",
        headers={"Content-Disposition":"attachment; filename=main.tar.gz"}
    )

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(
        API,
        host=os.getenv("BIND_HOST","0.0.0.0"),
        port=int(os.getenv("BIND_PORT","8080"))
    )