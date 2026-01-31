from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from query_models import Base
import os

# Query Results Database Configuration
QUERY_DB_USER = os.getenv("PG_SUPERUSER", "postgres")
QUERY_DB_PASS = os.getenv("PG_SUPERPASS", "postgres")
QUERY_DB_HOST = os.getenv("QUERY_DB_HOST", "query-results-db")
QUERY_DB_PORT = os.getenv("QUERY_DB_PORT", "5432")
QUERY_DB_NAME = os.getenv("QUERY_DB_NAME", "query_results")

# Create query results database URL
QUERY_DATABASE_URL = f"postgresql+psycopg2://{QUERY_DB_USER}:{QUERY_DB_PASS}@{QUERY_DB_HOST}:{QUERY_DB_PORT}/{QUERY_DB_NAME}"

# Create engine for query results database with improved connection pool settings
query_engine = create_engine(
    QUERY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,  # Increased from default 5
    max_overflow=30,  # Increased from default 10
    pool_timeout=60,  # Increased timeout to 60 seconds
    pool_recycle=3600,  # Recycle connections every hour
    pool_reset_on_return='commit'  # Reset connection state on return
)

# Create session factory
QuerySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=query_engine)

def get_query_db() -> Session:
    """Get database session for query results"""
    db = QuerySessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_query_db_sync() -> Session:
    """Get database session for query results (synchronous version)"""
    return QuerySessionLocal()

def create_query_tables():
    """Create all tables in the query results database"""
    Base.metadata.create_all(bind=query_engine)

def init_query_database():
    """Initialize the query results database"""
    try:
        create_query_tables()
        print("Query results database initialized successfully")
    except Exception as e:
        print(f"Error initializing query results database: {e}")
        raise 