import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, List
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from auth_models import User, Role, Permission, TokenData, UserAttributes

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate a password hash."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        if email is None:
            return None
        return TokenData(email=email, user_id=user_id)
    except jwt.PyJWTError:
        return None

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get a user by email address."""
    return db.query(User).filter(User.email == email).first()

def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user with email and password."""
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user

def get_user_roles(db: Session, user_id: int) -> List[str]:
    """Get all role names for a user."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    return [role.name for role in user.roles]

def get_user_permissions(db: Session, user_id: int) -> List[Permission]:
    """Get all permissions for a user through their roles."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return []
    
    permissions = set()
    for role in user.roles:
        for permission in role.permissions:
            permissions.add(permission)
    
    return list(permissions)

def check_permission(db: Session, user_id: int, resource_type: str, 
                    resource_name: Optional[str] = None, 
                    field_name: Optional[str] = None, 
                    action: str = "query") -> bool:
    """
    Check if a user has permission to access a specific resource.
    
    Args:
        db: Database session
        user_id: ID of the user
        resource_type: Type of resource ('postgres', 'iceberg', 'field')
        resource_name: Name of the specific resource (table, etc.)
        field_name: Name of the specific field
        action: Action being performed ('query', 'read', 'write')
    
    Returns:
        bool: True if user has permission, False otherwise
    """
    permissions = get_user_permissions(db, user_id)
    
    for permission in permissions:
        # Check if permission matches the requested access
        if (permission.resource_type == resource_type and 
            permission.action == action):
            
            # For field-level permissions
            if resource_type == "field":
                if (permission.field_name == field_name or 
                    permission.field_name == "*"):
                    return True
            
            # For table-level permissions
            elif resource_type in ["postgres", "iceberg"]:
                if (permission.resource_name == resource_name or 
                    permission.resource_name == "*"):
                    return True
    
    return False

def can_access_postgres(db: Session, user_id: int) -> bool:
    """Check if user can access postgres data."""
    return check_permission(db, user_id, "postgres", "*", None, "query")

def can_access_iceberg(db: Session, user_id: int) -> bool:
    """Check if user can access iceberg data."""
    return check_permission(db, user_id, "iceberg", "*", None, "query")

def can_access_field(db: Session, user_id: int, field_name: str) -> bool:
    """Check if user can access a specific field (e.g., SSN)."""
    return check_permission(db, user_id, "field", "*", field_name, "query")

def is_admin(db: Session, user_id: int) -> bool:
    """Check if user has admin role."""
    roles = get_user_roles(db, user_id)
    return "admin" in roles

def get_user_attributes(db: Session, user_id: int) -> dict:
    """
    Get user attributes for Cerbos principal.
    
    Args:
        db: Database session
        user_id: User ID
        
    Returns:
        Dictionary of user attributes (team, region, clearance_level, department, is_active)
        Returns dict with defaults if user has no attributes record
    """
    user_attrs = db.query(UserAttributes).filter(UserAttributes.user_id == user_id).first()
    
    if user_attrs:
        return {
            "team": user_attrs.team,
            "region": user_attrs.region,
            "clearance_level": user_attrs.clearance_level or 1,
            "department": user_attrs.department,
            "is_active": True  # Can be derived from User model if needed
        }
    else:
        # Return defaults if no attributes record exists
        return {
            "team": None,
            "region": None,
            "clearance_level": 1,
            "department": None,
            "is_active": True
        }