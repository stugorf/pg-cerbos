import io, os, tarfile, time, threading, yaml, json
import logging
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select, text, update
from db import SessionLocal, engine
from models import Policy
from auth_models import User, Role, Permission, Base
from auth_utils import (
    authenticate_user, create_access_token, verify_token, 
    get_password_hash, check_permission, is_admin, get_user_roles, get_user_attributes
)
from auth_models import (
    UserCreate, UserUpdate, UserResponse, RoleCreate, RoleResponse,
    PermissionCreate, PermissionResponse, LoginRequest, LoginResponse,
    UserAttributesCreate, UserAttributesUpdate, UserAttributesResponse
)
from query_models import Query, QueryColumn, QueryResult, QueryStat, QueryCreate, QueryResponse, QueryResultResponse
from query_db import get_query_db, get_query_db_sync, init_query_database
import requests
from startup_initializer import ensure_iceberg_demo_data, get_startup_init_status
from graph_query_analyzer import analyze_graph_query, GraphQueryAnalysisError
from graph_engine_adapter import get_graph_engine_adapter, get_graph_route, GraphEngineExecutionError
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

origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
API.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# Security
security = HTTPBearer()


def _graph_query_analysis_error_detail(exc: GraphQueryAnalysisError) -> dict:
    return {
        "error": "graph_query_analysis_failed",
        "message": f"Graph query analysis failed: {str(exc)}",
        "details": exc.details,
    }


@API.on_event("startup")
def initialize_demo_data_on_startup():
    def run_initializer():
        try:
            ensure_iceberg_demo_data()
        except Exception as exc:
            logger.error("Startup demo data initialization failed: %s", exc, exc_info=True)

    threading.Thread(target=run_initializer, name="startup-demo-data-init", daemon=True).start()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Get the effective authenticated user, optionally impersonated by an admin."""
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
    impersonate_user_id = request.headers.get("X-Impersonate-User-Id")
    if impersonate_user_id:
        if not is_admin(db, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can select an effective policy user"
            )
        try:
            target_user_id = int(impersonate_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid effective user id")
        target_user = db.query(User).filter(User.id == target_user_id).first()
        if target_user is None or not target_user.is_active:
            raise HTTPException(status_code=404, detail="Effective user not found")
        target_user.authenticated_user = user
        target_user.impersonated_by_user_id = user.id
        return target_user
    return user

def get_current_admin_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the current user and verify they have admin role."""
    authenticated_user = getattr(current_user, "authenticated_user", current_user)
    if not is_admin(db, authenticated_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return authenticated_user

# Health check
@API.get("/health")
def health():
    return {"ok": True}


def _component(status_name: str, ok: bool, detail: str = ""):
    return {
        "status": status_name,
        "ok": ok,
        "detail": detail,
    }


def _check_policy_db():
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
            return _component("ready", True, f"{user_count} users")
        finally:
            db.close()
    except Exception as exc:
        return _component("error", False, str(exc))


def _check_query_db():
    try:
        db = get_query_db_sync()
        try:
            db.execute(text("SELECT 1"))
            return _component("ready", True, "query results database reachable")
        finally:
            db.close()
    except Exception as exc:
        return _component("error", False, str(exc))


def _check_cerbos():
    try:
        cerbos_client = get_cerbos_client()
        allowed, reason, _policy = cerbos_client.check_query_permission(
            user_id="readiness",
            user_email="readiness@pg-cerbos.local",
            user_roles=["admin"],
            method="POST",
            path="/v1/statement",
            query_body="SELECT 1 FROM postgres.public.person LIMIT 1",
        )
        if allowed:
            return _component("ready", True, "Cerbos PDP authorization reachable")
        return _component("error", False, reason or "readiness authorization denied")
    except Exception as exc:
        return _component("error", False, str(exc))


def _check_trino():
    try:
        info_url = os.getenv("TRINO_INFO_URL", "http://trino-coordinator:8080/v1/info")
        response = requests.get(info_url, timeout=2)
        if response.ok:
            info = response.json()
            version = info.get("nodeVersion", {}).get("version", "unknown")
            environment = info.get("environment", "unknown")
            return _component(
                "ready",
                True,
                f"Trino coordinator reachable ({environment}, {version})",
            )
        return _component("error", False, f"HTTP {response.status_code}")
    except Exception as exc:
        return _component("error", False, str(exc))


def _check_iceberg():
    init_status = get_startup_init_status()
    state = init_status.get("state", "error")
    if state == "ready":
        return _component("ready", True, "Iceberg demo data initialized")
    if state in ("pending", "running"):
        return _component(
            "warning",
            False,
            "Iceberg demo data initialization is still running",
        )
    if state == "failed":
        return _component(
            "warning",
            False,
            init_status.get("error") or "Iceberg demo data initialization failed",
        )
    return _component("error", False, init_status.get("error") or f"unknown initializer state: {state}")


def _check_puppygraph():
    try:
        response = requests.get("http://puppygraph:8081/", timeout=2)
        if response.ok:
            return _component("ready", True, "PuppyGraph reachable")
        return _component("error", False, f"HTTP {response.status_code}")
    except Exception as exc:
        return _component("error", False, str(exc))


@API.get("/readiness")
def readiness():
    components = {
        "policy_db": _check_policy_db(),
        "query_db": _check_query_db(),
        "cerbos": _check_cerbos(),
        "trino": _check_trino(),
        "iceberg": _check_iceberg(),
        "puppygraph": _check_puppygraph(),
    }
    ready = all(component["ok"] for component in components.values())
    return {
        "ok": ready,
        "status": "ready" if ready else "degraded",
        "startup_init": get_startup_init_status(),
        "components": components,
        "checked_at": datetime.utcnow().isoformat() + "Z",
    }

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

# User Attributes management endpoints (Phase 3: ABAC)
@API.get("/users/{user_id}/attributes", response_model=UserAttributesResponse)
def get_user_attributes_endpoint(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user attributes."""
    # Only allow users to view their own attributes, or admins to view any
    if current_user.id != user_id and not is_admin(db, current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this user's attributes")
    
    from auth_models import UserAttributes
    user_attrs = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    
    if not user_attrs:
        raise HTTPException(status_code=404, detail="User attributes not found")
    
    return UserAttributesResponse(
        user_id=user_attrs.user_id,
        team=user_attrs.team,
        region=user_attrs.region,
        clearance_level=user_attrs.clearance_level,
        department=user_attrs.department,
        created_at=user_attrs.created_at,
        updated_at=user_attrs.updated_at
    )

@API.put("/users/{user_id}/attributes", response_model=UserAttributesResponse)
def update_user_attributes_endpoint(
    user_id: int,
    attributes_update: UserAttributesUpdate,
    current_user: User = Depends(get_current_admin_user),  # Only admins can update
    db: Session = Depends(get_db)
):
    """Update user attributes (admin only)."""
    from auth_models import UserAttributes
    
    user_attrs = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    
    if not user_attrs:
        # Create if doesn't exist
        user_attrs = UserAttributes(user_id=user_id)
        db.add(user_attrs)
    
    # Update fields
    update_data = attributes_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user_attrs, key, value)
    
    db.commit()
    db.refresh(user_attrs)
    
    return UserAttributesResponse(
        user_id=user_attrs.user_id,
        team=user_attrs.team,
        region=user_attrs.region,
        clearance_level=user_attrs.clearance_level,
        department=user_attrs.department,
        created_at=user_attrs.created_at,
        updated_at=user_attrs.updated_at
    )

@API.post("/users/{user_id}/attributes", response_model=UserAttributesResponse)
def create_user_attributes_endpoint(
    user_id: int,
    attributes_create: UserAttributesCreate,
    current_user: User = Depends(get_current_admin_user),  # Only admins can create
    db: Session = Depends(get_db)
):
    """Create user attributes (admin only)."""
    from auth_models import UserAttributes
    
    # Check if attributes already exist
    existing = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="User attributes already exist. Use PUT to update.")
    
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create new attributes
    user_attrs = UserAttributes(
        user_id=user_id,
        team=attributes_create.team,
        region=attributes_create.region,
        clearance_level=attributes_create.clearance_level or 1,
        department=attributes_create.department
    )
    db.add(user_attrs)
    db.commit()
    db.refresh(user_attrs)
    
    return UserAttributesResponse(
        user_id=user_attrs.user_id,
        team=user_attrs.team,
        region=user_attrs.region,
        clearance_level=user_attrs.clearance_level,
        department=user_attrs.department,
        created_at=user_attrs.created_at,
        updated_at=user_attrs.updated_at
    )

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

# Graph schema endpoint: Retrieve schema from PuppyGraph for NL interface and validation
@API.get("/query/graph/schema")
def get_graph_schema(language: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Retrieve the current graph schema from the configured graph engine."""
    query_type = (language or "cypher").lower()
    try:
        schema = get_graph_engine_adapter(query_type).get_schema()
        return {"success": True, "schema": schema, "route": get_graph_route(query_type)}
    except GraphEngineExecutionError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get graph schema: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to retrieve schema: {str(e)}")


# Natural language to Cypher: analyze query, generate Cypher, optionally execute
@API.post("/query/graph/natural-language")
def natural_language_graph_query(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accept a natural language question, retrieve schema from the selected graph engine, analyze the query
    (entities and relationships), generate a graph query validated against the schema,
    and optionally execute it (with Cerbos authorization).
    """
    request_start = time.time()
    try:
        from nl_to_cypher import nl_to_graph_query
    except ImportError as ex:
        logger.warning("Natural language endpoint import failed: %s", ex)
        raise HTTPException(
            status_code=503,
            detail=f"Natural language query not available: {str(ex)}",
        )
    query_text = (body.get("query") or "").strip()
    query_type = (body.get("type") or "cypher").strip().lower()
    execute = body.get("execute", False)

    if not query_text:
        raise HTTPException(status_code=400, detail="Natural language query is required.")
    if query_type not in ["cypher", "gremlin", "sparql", "gql"]:
        raise HTTPException(status_code=400, detail="Query type must be 'cypher', 'gremlin', 'sparql', or 'gql'")

    try:
        schema_start = time.time()
        graph_engine = get_graph_engine_adapter(query_type)
        schema = graph_engine.get_schema()
        schema_ms = (time.time() - schema_start) * 1000
    except GraphEngineExecutionError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get schema: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to retrieve schema: {str(e)}")

    try:
        model_start = time.time()
        result = nl_to_graph_query(query_text, schema, query_type)
        model_ms = (time.time() - model_start) * 1000
    except Exception as e:
        logger.error(f"NL to graph query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Could not generate graph query: {str(e)}")

    logger.info(
        "NLI query=%r language=%s source=%s valid=%s graph_query_preview=%s",
        query_text[:100],
        query_type,
        result.get("source"),
        result.get("valid"),
        (result.get("query") or result.get("cypher") or "")[:200],
    )
    if not result["valid"]:
        return {
            "success": False,
            "cypher": result.get("query", result.get("cypher", "")),
            "query": result.get("query", result.get("cypher", "")),
            "query_type": query_type,
            "analysis": result.get("analysis", {}),
            "valid": False,
            "validation_errors": result.get("validation_errors", []),
            "generation_source": result.get("source"),
            "generation_attempts": result.get("attempts", []),
            "executed": False,
            "sequence_metrics": {
                "schema_ms": schema_ms,
                "model_ms": model_ms,
                "backend_ms": (time.time() - request_start) * 1000,
            },
        }

    # Optional: validate that the selected graph engine accepts the generated query (dry run)
    validate_with_puppygraph = body.get("validate_with_puppygraph", False)
    generated_query = result.get("query") or result.get("cypher") or ""
    if validate_with_puppygraph and generated_query:
        try:
            graph_engine.execute(query_type, generated_query)
        except GraphEngineExecutionError as e:
            exec_err = str(e)
            logger.warning("Graph engine validation run failed: %s", exec_err)
            return {
                "success": False,
                "cypher": generated_query,
                "query": generated_query,
                "query_type": query_type,
                "analysis": result.get("analysis", {}),
                "valid": False,
                "validation_errors": result.get("validation_errors", []) + [f"Graph engine execution: {exec_err}"],
                "generation_source": result.get("source"),
                "generation_attempts": result.get("attempts", []),
                "executed": False,
                "sequence_metrics": {
                    "schema_ms": schema_ms,
                    "model_ms": model_ms,
                    "backend_ms": (time.time() - request_start) * 1000,
                },
            }
        except Exception as e:
            exec_err = str(e)
            logger.warning("Graph engine validation run failed: %s", exec_err)
            return {
                "success": False,
                "cypher": generated_query,
                "query": generated_query,
                "query_type": query_type,
                "analysis": result.get("analysis", {}),
                "valid": False,
                "validation_errors": result.get("validation_errors", []) + [f"Graph engine execution: {exec_err}"],
                "generation_source": result.get("source"),
                "generation_attempts": result.get("attempts", []),
                "executed": False,
                "sequence_metrics": {
                    "schema_ms": schema_ms,
                    "model_ms": model_ms,
                    "backend_ms": (time.time() - request_start) * 1000,
                },
            }

    if not execute:
        return {
            "success": True,
            "cypher": generated_query,
            "query": generated_query,
            "query_type": query_type,
            "analysis": result.get("analysis", {}),
            "valid": True,
            "validation_errors": [],
            "generation_source": result.get("source"),
            "generation_attempts": result.get("attempts", []),
            "executed": False,
            "sequence_metrics": {
                "schema_ms": schema_ms,
                "model_ms": model_ms,
                "backend_ms": (time.time() - request_start) * 1000,
            },
        }

    # Execute via same authorization path as /query/graph
    query = generated_query
    try:
        analysis_start = time.time()
        cerbos_attributes = analyze_graph_query(
            language=query_type,
            query=query,
            schema=schema,
            mode="read",
        )
        analysis_ms = (time.time() - analysis_start) * 1000
    except GraphQueryAnalysisError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=_graph_query_analysis_error_detail(exc),
        )

    cerbos_client = get_cerbos_client()
    user_roles = get_user_roles(db, current_user.id)
    user_attributes = get_user_attributes(db, current_user.id)
    cerbos_start = time.time()
    allowed, reason, policy = cerbos_client.check_resource_access(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind="cypher_query",
        resource_id="graph-query",
        action="execute",
        attributes=cerbos_attributes,
        principal_attributes=user_attributes,
    )
    cerbos_ms = (time.time() - cerbos_start) * 1000
    log_authorization_decision(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind="cypher_query",
        action="execute",
        allowed=allowed,
        reason=reason or ("NL graph query authorized" if allowed else "Not authorized"),
        query_preview=query[:200],
        policy=policy,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=reason or "Not authorized to execute this graph query.")

    engine_start = time.time()
    elapsed_ms = 0
    try:
        engine_start = time.time()
        data = graph_engine.execute(query_type, query)
        elapsed_ms = (time.time() - engine_start) * 1000
        total_backend_ms = (time.time() - request_start) * 1000

        # Optional: suggest chart type and ECharts option via LLM (NL path: use user question as context)
        chart_info = {"chart_type": "table_only", "chart_subtype": None, "echarts_option": None}
        try:
            from chart_suggestion import suggest_chart_and_echarts
            logger.info("Chart suggestion: calling for NL query (execute=True)")
            chart_info = suggest_chart_and_echarts(query_text, data, is_natural_language=True)
            if chart_info.get("chart_type") != "table_only":
                logger.info("Chart suggestion: type=%s subtype=%s has_option=%s", chart_info.get("chart_type"), chart_info.get("chart_subtype"), chart_info.get("echarts_option") is not None)
            else:
                logger.info("Chart suggestion: returned table_only")
        except Exception as chart_err:
            logger.info("Chart suggestion skipped: %s", chart_err)

        return {
            "success": True,
            "cypher": query,
            "query": query,
            "query_type": query_type,
            "route": get_graph_route(query_type),
            "analysis": result.get("analysis", {}),
            "valid": True,
            "validation_errors": [],
            "generation_source": result.get("source"),
            "generation_attempts": result.get("attempts", []),
            "executed": True,
            "data": data,
            "execution_time_ms": elapsed_ms,
            "sequence_metrics": {
                "schema_ms": schema_ms,
                "model_ms": model_ms,
                "analysis_ms": analysis_ms,
                "cerbos_ms": cerbos_ms,
                "engine_ms": elapsed_ms,
                "backend_ms": total_backend_ms,
            },
            "chart_type": chart_info.get("chart_type", "table_only"),
            "chart_subtype": chart_info.get("chart_subtype"),
            "echarts_option": chart_info.get("echarts_option"),
        }
    except GraphEngineExecutionError as e:
        elapsed_ms = (time.time() - engine_start) * 1000
        return JSONResponse(
            status_code=e.status_code,
            content={
                "success": False,
                "detail": str(e),
                "query": query,
                "query_type": query_type,
                "route": get_graph_route(query_type),
                "analysis": result.get("analysis", {}),
                "valid": True,
                "validation_errors": [],
                "generation_source": result.get("source"),
                "generation_attempts": result.get("attempts", []),
                "executed": True,
                "sequence_metrics": {
                    "schema_ms": schema_ms,
                    "model_ms": model_ms,
                    "analysis_ms": analysis_ms,
                    "cerbos_ms": cerbos_ms,
                    "engine_ms": elapsed_ms,
                    "backend_ms": (time.time() - request_start) * 1000,
                },
            },
        )
    except Exception as e:
        logger.error(f"NL graph query execution failed: {e}", exc_info=True)
        elapsed_ms = (time.time() - engine_start) * 1000
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Query execution failed: {str(e)}",
                "query": query,
                "query_type": query_type,
                "route": get_graph_route(query_type),
                "analysis": result.get("analysis", {}),
                "valid": True,
                "validation_errors": [],
                "generation_source": result.get("source"),
                "generation_attempts": result.get("attempts", []),
                "executed": True,
                "sequence_metrics": {
                    "schema_ms": schema_ms,
                    "model_ms": model_ms,
                    "analysis_ms": analysis_ms,
                    "cerbos_ms": cerbos_ms,
                    "engine_ms": elapsed_ms,
                    "backend_ms": (time.time() - request_start) * 1000,
                },
            },
        )


# Graph Query endpoint: Execute graph queries with Cerbos authorization
@API.post("/query/graph")
def execute_graph_query(
    query_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Execute a graph query via the selected graph backend with Cerbos authorization."""
    request_start = time.time()
    query = query_data.get("query", "").strip()
    query_type = query_data.get("type", "cypher").lower()
    
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    
    if query_type not in ["cypher", "gremlin", "sparql", "gql"]:
        raise HTTPException(status_code=400, detail="Query type must be 'cypher', 'gremlin', 'sparql', or 'gql'")

    try:
        schema_start = time.time()
        graph_engine = get_graph_engine_adapter(query_type)
        schema = graph_engine.get_schema()
        schema_ms = (time.time() - schema_start) * 1000
    except GraphEngineExecutionError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get graph schema for query validation: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to retrieve schema: {str(e)}")

    try:
        analysis_start = time.time()
        cerbos_attributes = analyze_graph_query(
            language=query_type,
            query=query,
            schema=schema,
            mode="read",
        )
        analysis_ms = (time.time() - analysis_start) * 1000
        logger.debug(f"Graph query analysis: {cerbos_attributes}")
    except GraphQueryAnalysisError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=_graph_query_analysis_error_detail(exc),
        )
    
    # Check authorization with Cerbos
    cerbos_client = get_cerbos_client()
    user_roles = get_user_roles(db, current_user.id)
    
    # Get user attributes for ABAC (Phase 3)
    user_attributes = get_user_attributes(db, current_user.id)
    
    # Use the existing graph resource policy for all graph languages while the
    # analyzer contract evolves beyond Cypher.
    resource_kind = "cypher_query"
    action = "execute"
    
    # Check if user can execute graph queries
    cerbos_start = time.time()
    allowed, reason, policy = cerbos_client.check_resource_access(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind=resource_kind,
        resource_id="graph-query",
        action=action,
        attributes=cerbos_attributes,
        principal_attributes=user_attributes  # Phase 3: Pass user attributes for ABAC
    )
    cerbos_ms = (time.time() - cerbos_start) * 1000
    
    # Log authorization decision (both allowed and denied)
    log_authorization_decision(
        user_id=str(current_user.id),
        user_email=current_user.email,
        user_roles=user_roles,
        resource_kind=resource_kind,
        action=action,
        allowed=allowed,
        reason=reason or ("Graph query authorized" if allowed else "Not authorized to execute graph queries"),
        query_preview=query[:200],
        policy=policy
    )
    
    if not allowed:
        raise HTTPException(status_code=403, detail=reason or "Not authorized to execute graph queries")
    
    # Execute graph query via the configured graph engine adapter
    engine_start = time.time()
    execution_time = 0
    try:
        engine_start = time.time()
        result = graph_engine.execute(query_type, query)
        
        execution_time = (time.time() - engine_start) * 1000
        total_backend_ms = (time.time() - request_start) * 1000

        # Optional: suggest chart type and ECharts option via LLM.
        chart_info = {"chart_type": "table_only", "chart_subtype": None, "echarts_option": None}
        try:
            from chart_suggestion import suggest_chart_and_echarts
            logger.info("Chart suggestion: calling for graph query execute")
            chart_info = suggest_chart_and_echarts(query, result, is_natural_language=False)
            if chart_info.get("chart_type") != "table_only":
                logger.info("Chart suggestion: type=%s subtype=%s has_option=%s", chart_info.get("chart_type"), chart_info.get("chart_subtype"), chart_info.get("echarts_option") is not None)
            else:
                logger.info("Chart suggestion: returned table_only")
        except Exception as chart_err:
            logger.info("Chart suggestion skipped: %s", chart_err)

        # Graph adapter response format may vary, return raw result for now.
        return {
            "success": True,
            "data": result,
            "query_type": query_type,
            "route": get_graph_route(query_type),
            "execution_time_ms": execution_time,
            "sequence_metrics": {
                "schema_ms": schema_ms,
                "analysis_ms": analysis_ms,
                "cerbos_ms": cerbos_ms,
                "engine_ms": execution_time,
                "backend_ms": total_backend_ms
            },
            "query": query,
            "chart_type": chart_info.get("chart_type", "table_only"),
            "chart_subtype": chart_info.get("chart_subtype"),
            "echarts_option": chart_info.get("echarts_option"),
        }
    except GraphEngineExecutionError as e:
        execution_time = (time.time() - engine_start) * 1000
        return JSONResponse(
            status_code=e.status_code,
            content={
                "success": False,
                "detail": str(e),
                "query": query,
                "query_type": query_type,
                "route": get_graph_route(query_type),
                "sequence_metrics": {
                    "schema_ms": schema_ms,
                    "analysis_ms": analysis_ms,
                    "cerbos_ms": cerbos_ms,
                    "engine_ms": execution_time,
                    "backend_ms": (time.time() - request_start) * 1000,
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Graph query failed: {e}", exc_info=True)
        execution_time = (time.time() - engine_start) * 1000
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "detail": f"Graph query failed: {str(e)}",
                "query": query,
                "query_type": query_type,
                "route": get_graph_route(query_type),
                "sequence_metrics": {
                    "schema_ms": schema_ms,
                    "analysis_ms": analysis_ms,
                    "cerbos_ms": cerbos_ms,
                    "engine_ms": execution_time,
                    "backend_ms": (time.time() - request_start) * 1000,
                },
            },
        )

# SQL Query endpoint: Execute queries with Cerbos authorization
@API.post("/query")
def execute_sql_query(query_data: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), query_db: Session = Depends(get_query_db)):
    """Execute SQL query through Trino with Cerbos authorization."""
    import json
    request_start = time.time()
    cerbos_ms = 0
    engine_ms = 0
    
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
        cerbos_start = time.time()
        allowed, reason, policy = cerbos_client.check_query_permission(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            method="POST",
            path="/v1/statement",
            query_body=sql_query
        )
        cerbos_ms = (time.time() - cerbos_start) * 1000
        
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
        engine_start = time.time()
        with trino_client.execute_query(username, catalog, schema, sql_query) as (success, data, columns, error):
            engine_ms = (time.time() - engine_start) * 1000
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
                    "columns": columns,
                    "sequence_metrics": {
                        "cerbos_ms": cerbos_ms,
                        "engine_ms": engine_ms,
                        "backend_ms": (time.time() - request_start) * 1000
                    }
                }
            else:
                # Query failed
                return {
                    "success": False,
                    "error": error or "Unknown Trino error",
                    "code": "trino_error",
                    "sequence_metrics": {
                        "cerbos_ms": cerbos_ms,
                        "engine_ms": engine_ms,
                        "backend_ms": (time.time() - request_start) * 1000
                    }
                }
                
    except Exception as e:
        print(f"DEBUG: Error executing query with Trino client: {e}")
        if "engine_start" in locals() and engine_ms == 0:
            engine_ms = (time.time() - engine_start) * 1000
        return {
            "success": False,
            "error": f"Failed to execute query: {str(e)}",
            "code": "execution_error",
            "sequence_metrics": {
                "cerbos_ms": cerbos_ms,
                "engine_ms": engine_ms,
                "backend_ms": (time.time() - request_start) * 1000
            }
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
        
        # Log authorization decision (both allowed and denied)
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
    
    # Find all YAML files in policies directory (include tests/ so UI matches just list-cerbos-policies)
    for root, dirs, files in os.walk(policies_dir):
        # Skip only hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
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
    """Get Cerbos audit logs to demonstrate authorization as a service."""
    try:
        log_output = read_cerbos_audit_log_output(lines)
        if not log_output.strip():
            return get_backend_authz_logs(lines)
        return parse_cerbos_log_output(log_output, lines)
    except Exception as e:
        logger.error(f"Error fetching Cerbos logs: {e}", exc_info=True)
        return get_backend_authz_logs(lines)


def read_cerbos_audit_log_output(lines: int) -> str:
    """Read recent Cerbos file-audit records from the shared audit volume."""
    import glob

    audit_path = os.getenv("CERBOS_AUDIT_LOG_PATH", "/audit/cerbos-audit.log")
    candidates = [
        path for path in glob.glob(f"{audit_path}*")
        if os.path.isfile(path)
    ]
    if not candidates:
        logger.info("No Cerbos audit log files found at %s", audit_path)
        return ""

    candidates.sort(key=lambda path: os.path.getmtime(path))
    records = []
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as audit_file:
                records.extend(line.rstrip("\n") for line in audit_file if line.strip())
        except OSError as exc:
            logger.warning("Failed reading Cerbos audit log file %s: %s", path, exc)

    return "\n".join(records[-lines:])


def parse_cerbos_log_output(log_output: str, lines: int) -> dict:
    import json

    log_lines = log_output.strip().split('\n')
    parsed_logs = []

    for line in log_lines:
        if not line.strip():
            continue

        timestamp = ""
        message = line
        if line.startswith("20") and "T" in line[:30]:
            parts = line.split(" ", 1)
            if len(parts) == 2:
                timestamp = parts[0]
                message = parts[1]

        try:
            log_entry = json.loads(message)
            cerbos_meta = log_entry.get("cerbos") or {}
            audit_metadata = extract_cerbos_audit_metadata(log_entry)
            parsed_log = {
                "timestamp": log_entry.get("@timestamp") or log_entry.get("ts") or log_entry.get("timestamp") or timestamp,
                "level": log_entry.get("log.level") or log_entry.get("level", "info"),
                "message": log_entry.get("message") or log_entry.get("msg") or summarize_cerbos_audit_entry(log_entry),
                "call_id": cerbos_meta.get("call_id") or log_entry.get("callID") or log_entry.get("callId", ""),
                "method": log_entry.get("grpc.method") or log_entry.get("method", ""),
                "raw": line,
                "type": "cerbos",
                "logger": log_entry.get("log.logger", ""),
                "log_kind": log_entry.get("log.kind", ""),
                "grpc_code": log_entry.get("grpc.code", ""),
                "grpc_time_ms": log_entry.get("grpc.time_ms", "")
            }
            parsed_log.update(audit_metadata)
            parsed_logs.append(parsed_log)
        except json.JSONDecodeError:
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

    backend_logs = get_backend_authz_logs(50)
    if backend_logs.get("logs"):
        parsed_logs.extend(backend_logs["logs"])

    parsed_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "logs": parsed_logs[:lines],
        "total": len(parsed_logs)
    }


def extract_cerbos_audit_metadata(log_entry: dict) -> dict:
    check_resources = log_entry.get("checkResources") or {}
    inputs = check_resources.get("inputs") or []
    outputs = check_resources.get("outputs") or []
    if not inputs or not outputs:
        return {}

    input_entry = inputs[0] or {}
    output_entry = outputs[0] or {}
    resource = input_entry.get("resource") or {}
    principal = input_entry.get("principal") or {}
    actions = output_entry.get("actions") or {}
    action = next(iter(actions.keys()), "")
    action_result = actions.get(action) or {}
    effect = action_result.get("effect", "")
    policy_id = action_result.get("policy", "")
    policy_source = ""
    effective_policies = ((log_entry.get("auditTrail") or {}).get("effectivePolicies") or {})
    if policy_id in effective_policies:
        policy_source = ((effective_policies[policy_id] or {}).get("attributes") or {}).get("source", "")

    policy_name = policy_id
    if policy_source:
        policy_name = os.path.splitext(os.path.basename(policy_source))[0]
    elif policy_id.startswith("resource."):
        parts = policy_id.split(".")
        if len(parts) >= 2:
            policy_name = parts[1]

    resource_attr = resource.get("attr") or {}
    return {
        "decision": "ALLOW" if effect == "EFFECT_ALLOW" else "DENY" if effect == "EFFECT_DENY" else effect,
        "allowed": effect == "EFFECT_ALLOW",
        "action": action,
        "user_id": principal.get("id", ""),
        "user_roles": principal.get("roles", []),
        "resource_kind": resource.get("kind", ""),
        "policy": policy_name,
        "policy_id": policy_id,
        "policy_source": policy_source,
        "query_preview": resource_attr.get("body"),
    }


def summarize_cerbos_audit_entry(log_entry: dict) -> str:
    metadata = extract_cerbos_audit_metadata(log_entry)
    if metadata:
        return (
            f"Cerbos Decision Audit: {metadata.get('decision')} | "
            f"User: {metadata.get('user_id')} | "
            f"Roles: {', '.join(metadata.get('user_roles') or [])} | "
            f"Resource: {metadata.get('resource_kind')} | "
            f"Action: {metadata.get('action')} | "
            f"Policy: {metadata.get('policy')}"
        )
    log_kind = log_entry.get("log.kind")
    method = log_entry.get("method") or log_entry.get("grpc.method")
    if log_kind:
        return f"Cerbos {log_kind} audit log{f': {method}' if method else ''}"
    return json.dumps(log_entry, sort_keys=True)


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
            "allowed": decision['allowed'],
            "action": decision['action'],
            "user_email": decision['user_email'],
            "user_id": decision['user_id'],
            "user_roles": decision['user_roles'],
            "resource_kind": decision['resource_kind'],
            "policy": policy_name,
            "reason": decision.get('reason'),
            "query_preview": decision.get('query_preview')
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
        user_roles = get_user_roles(db, current_user.id)
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="alert",
            resource_id="*",
            action="view"
        )
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="alert",
            action="view",
            allowed=allowed,
            reason=reason,
            policy=policy
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
        user_roles = get_user_roles(db, current_user.id)
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="alert",
            resource_id=str(alert_id),
            action="view"
        )
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="alert",
            action="view",
            allowed=allowed,
            reason=reason,
            policy=policy
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
        user_roles = get_user_roles(db, current_user.id)
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="alert",
            resource_id=str(alert_id),
            action="escalate"
        )
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="alert",
            action="escalate",
            allowed=allowed,
            reason=reason,
            policy=policy
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
        user_roles = get_user_roles(db, current_user.id)
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="case",
            resource_id="*",
            action="view"
        )
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="case",
            action="view",
            allowed=allowed,
            reason=reason,
            policy=policy
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
            user_roles = get_user_roles(db, current_user.id)
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                resource_id=str(case_id),
                action="view",
                attributes={"owner_user_id": case_owner, "status": row[1], "team": row[6] or ""}
            )
            # Log authorization decision (both allowed and denied)
            log_authorization_decision(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                action="view",
                allowed=allowed,
                reason=reason,
                policy=policy
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
            user_roles = get_user_roles(db, current_user.id)
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                resource_id=str(case_id),
                action="add_note",
                attributes={"owner_user_id": case_owner, "status": row[1]}
            )
            # Log authorization decision (both allowed and denied)
            log_authorization_decision(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                action="add_note",
                allowed=allowed,
                reason=reason,
                policy=policy
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
            user_roles = get_user_roles(db, current_user.id)
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="transaction",
                resource_id=f"case-{case_id}",
                action="graph_expand",
                attributes={"case_id": str(case_id), "owner_user_id": case_owner}
            )
            # Log authorization decision (both allowed and denied)
            log_authorization_decision(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="transaction",
                action="graph_expand",
                allowed=allowed,
                reason=reason,
                policy=policy
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
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="case",
            action="assign",
            allowed=allowed,
            reason=reason,
            policy=policy
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
            user_roles = get_user_roles(db, current_user.id)
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                resource_id=str(case_id),
                action="close",
                attributes={"owner_user_id": case_owner, "status": row[1]}
            )
            # Log authorization decision (both allowed and denied)
            log_authorization_decision(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                action="close",
                allowed=allowed,
                reason=reason,
                policy=policy
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
            user_roles = get_user_roles(db, current_user.id)
            allowed, reason, policy = cerbos_client.check_resource_access(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                resource_id=str(case_id),
                action="view",
                attributes={"owner_user_id": case_owner, "status": row[1]}
            )
            # Log authorization decision (both allowed and denied)
            log_authorization_decision(
                user_id=str(current_user.id),
                user_email=current_user.email,
                user_roles=user_roles,
                resource_kind="case",
                action="view",
                allowed=allowed,
                reason=reason,
                policy=policy
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
        user_roles = get_user_roles(db, current_user.id)
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            resource_id="*",
            action="view"
        )
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            action="view",
            allowed=allowed,
            reason=reason,
            policy=policy
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
        user_roles = get_user_roles(db, current_user.id)
        allowed, reason, policy = cerbos_client.check_resource_access(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            resource_id=str(sar_id),
            action="view"
        )
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            action="view",
            allowed=allowed,
            reason=reason,
            policy=policy
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
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            action="draft",
            allowed=allowed,
            reason=reason,
            policy=policy
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
        # Log authorization decision (both allowed and denied)
        log_authorization_decision(
            user_id=str(current_user.id),
            user_email=current_user.email,
            user_roles=user_roles,
            resource_kind="sar",
            action="submit",
            allowed=allowed,
            reason=reason,
            policy=policy
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
