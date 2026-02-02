"""
AML (Anti-Money Laundering) Data Models

Pydantic models for AML API requests and responses.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


# Request Models
class GraphExpandRequest(BaseModel):
    """Request to expand transaction network from a case."""
    depth: int = Field(default=2, ge=1, le=5, description="Graph traversal depth")
    direction: str = Field(default="both", pattern="^(both|incoming|outgoing)$")


class CaseNoteCreate(BaseModel):
    """Request to create a case note."""
    text: str = Field(..., min_length=1, max_length=5000, description="Note text")


class CaseAssignRequest(BaseModel):
    """Request to assign a case to an analyst."""
    owner_user_id: str = Field(..., description="User ID of the assigned analyst")
    team: Optional[str] = Field(None, description="Team assignment")


class SARCreate(BaseModel):
    """Request to create a SAR."""
    case_id: int = Field(..., description="Case ID this SAR is associated with")


# Response Models
class CustomerResponse(BaseModel):
    """Customer information."""
    customer_id: int
    name: str
    risk_rating: str
    pep_flag: bool
    created_at: datetime
    updated_at: datetime


class AccountResponse(BaseModel):
    """Account information."""
    account_id: int
    customer_id: int
    type: str
    status: str
    created_at: datetime
    updated_at: datetime


class TransactionResponse(BaseModel):
    """Transaction information."""
    txn_id: int
    from_account_id: int
    to_account_id: int
    amount: float
    timestamp: datetime
    channel: Optional[str]
    country: Optional[str]
    created_at: datetime


class AlertResponse(BaseModel):
    """Alert information."""
    alert_id: int
    alert_type: str
    created_at: datetime
    severity: str
    status: str
    primary_customer_id: Optional[int]
    primary_account_id: Optional[int]


class CaseResponse(BaseModel):
    """Case information."""
    case_id: int
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    owner_user_id: Optional[str]
    team: Optional[str]
    source_alert_id: Optional[int]


class CaseNoteResponse(BaseModel):
    """Case note information."""
    note_id: int
    case_id: int
    author_user_id: str
    created_at: datetime
    text: str


class SARResponse(BaseModel):
    """SAR information."""
    sar_id: int
    case_id: int
    status: str
    created_at: datetime
    submitted_at: Optional[datetime]


class GraphNode(BaseModel):
    """Graph node representation."""
    label: str
    id: Any
    properties: Dict[str, Any]


class GraphEdge(BaseModel):
    """Graph edge representation."""
    label: str
    from_id: Any
    to_id: Any
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphResponse(BaseModel):
    """Graph query response."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    query: str
    execution_time_ms: Optional[float] = None
