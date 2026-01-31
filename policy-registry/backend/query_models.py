from sqlalchemy import Column, Integer, String, Text, DateTime, BigInteger, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

Base = declarative_base()

class Query(Base):
    """Model for storing query metadata"""
    __tablename__ = "queries"
    
    id = Column(String(100), primary_key=True)
    user_id = Column(Integer, nullable=False)
    user_email = Column(String(255), nullable=False)
    sql_query = Column(Text, nullable=False)
    catalog = Column(String(100))
    schema = Column(String(100))
    status = Column(String(50), nullable=False, default='QUEUED')
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    execution_time_ms = Column(BigInteger)
    rows_returned = Column(Integer, default=0)
    bytes_processed = Column(BigInteger, default=0)
    trino_next_uri = Column(Text)
    trino_info_uri = Column(Text)
    trino_query_id = Column(String(100))  # Store Trino's query ID separately
    
    # Relationships
    columns = relationship("QueryColumn", back_populates="query", cascade="all, delete-orphan")
    results = relationship("QueryResult", back_populates="query", cascade="all, delete-orphan")
    stats = relationship("QueryStat", back_populates="query", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert query to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_email": self.user_email,
            "sql_query": self.sql_query,
            "catalog": self.catalog,
            "schema": self.schema,
            "status": self.status,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
            "rows_returned": self.rows_returned,
            "bytes_processed": self.bytes_processed,
            "trino_next_uri": self.trino_next_uri,
            "trino_info_uri": self.trino_info_uri,
            "trino_query_id": self.trino_query_id
        }

class QueryColumn(Base):
    """Model for storing query result columns"""
    __tablename__ = "query_columns"
    
    id = Column(Integer, primary_key=True)
    query_id = Column(String(100), ForeignKey("queries.id"), nullable=False)
    column_name = Column(String(255), nullable=False)
    column_type = Column(String(100))
    column_position = Column(Integer, nullable=False)
    
    # Relationships
    query = relationship("Query", back_populates="columns")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert column to dictionary"""
        return {
            "id": self.id,
            "query_id": self.query_id,
            "column_name": self.column_name,
            "column_type": self.column_type,
            "column_position": self.column_position
        }

class QueryResult(Base):
    """Model for storing query result data"""
    __tablename__ = "query_results"
    
    id = Column(Integer, primary_key=True)
    query_id = Column(String(100), ForeignKey("queries.id"), nullable=False)
    row_number = Column(Integer, nullable=False)
    column_position = Column(Integer, nullable=False)
    cell_value = Column(Text)
    
    # Relationships
    query = relationship("Query", back_populates="results")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary"""
        return {
            "id": self.id,
            "query_id": self.query_id,
            "row_number": self.row_number,
            "column_position": self.column_position,
            "cell_value": self.cell_value
        }

class QueryStat(Base):
    """Model for storing query statistics"""
    __tablename__ = "query_stats"
    
    id = Column(Integer, primary_key=True)
    query_id = Column(String(100), ForeignKey("queries.id"), nullable=False)
    stat_name = Column(String(100), nullable=False)
    stat_value = Column(Text)
    stat_type = Column(String(50), default='string')
    
    # Relationships
    query = relationship("Query", back_populates="stats")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stat to dictionary"""
        return {
            "id": self.id,
            "query_id": self.query_id,
            "stat_name": self.stat_name,
            "stat_value": self.stat_value,
            "stat_type": self.stat_type
        }

# Pydantic schemas for API requests/responses
from pydantic import BaseModel
from typing import List, Optional

class QueryCreate(BaseModel):
    sql_query: str
    catalog: Optional[str] = None
    schema: Optional[str] = None

class QueryResponse(BaseModel):
    success: bool
    query_id: str
    status: str
    message: str
    next_uri: Optional[str] = None
    info_uri: Optional[str] = None

class QueryResultResponse(BaseModel):
    success: bool
    status: str
    data: Optional[List[List[Any]]] = None
    columns: Optional[List[Dict[str, Any]]] = None
    stats: Optional[Dict[str, Any]] = None
    message: str
    error: Optional[str] = None
    code: Optional[str] = None

class QueryListResponse(BaseModel):
    success: bool
    queries: List[Dict[str, Any]]
    total: int
    page: int
    per_page: int 