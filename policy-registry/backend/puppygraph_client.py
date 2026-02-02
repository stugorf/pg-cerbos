"""
PuppyGraph Client

This module provides a client for querying PuppyGraph graph database.
PuppyGraph allows querying PostgreSQL data as a graph using openCypher or Gremlin.

PuppyGraph uses:
- Bolt protocol (port 7687) for Cypher queries
- Gremlin server (port 8182) for Gremlin queries
- Web UI (port 8081) for administration
"""
import os
import logging
import requests
from typing import Optional, Dict, Any, List
from requests.auth import HTTPBasicAuth

# Try to import Neo4j driver for Bolt protocol support
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    logging.warning("Neo4j driver not available. Install with: pip install neo4j")

logger = logging.getLogger(__name__)

# PuppyGraph configuration
PUPPYGRAPH_URL = os.getenv("PUPPYGRAPH_URL", "http://puppygraph:8081")
PUPPYGRAPH_USER = os.getenv("PUPPYGRAPH_USER", "puppygraph")
PUPPYGRAPH_PASSWORD = os.getenv("PUPPYGRAPH_PASSWORD", "puppygraph123")


class PuppyGraphClient:
    """Client for querying PuppyGraph."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize PuppyGraph client.
        
        Args:
            base_url: PuppyGraph base URL (defaults to PUPPYGRAPH_URL env var)
            username: PuppyGraph username (defaults to PUPPYGRAPH_USER env var)
            password: PuppyGraph password (defaults to PUPPYGRAPH_PASSWORD env var)
        """
        self.base_url = (base_url or PUPPYGRAPH_URL).rstrip('/')
        self.username = username or PUPPYGRAPH_USER
        self.password = password or PUPPYGRAPH_PASSWORD
        self.auth = HTTPBasicAuth(self.username, self.password)
        self.session = requests.Session()
        self.session.auth = self.auth
        
        logger.info(f"PuppyGraph client initialized with URL: {self.base_url}")
    
    def execute_cypher(self, query: str) -> Dict[str, Any]:
        """
        Execute an openCypher query using Bolt protocol.
        
        PuppyGraph uses Bolt protocol on port 7687 for Cypher queries.
        
        Args:
            query: openCypher query string
            
        Returns:
            Query results as dictionary
        """
        # Extract host from base_url for Bolt connection
        # Use Docker service name "puppygraph" when connecting from container
        if "://" in self.base_url:
            host = self.base_url.split("://")[1].split(":")[0]
        else:
            host = self.base_url.split(":")[0] if ":" in self.base_url else self.base_url
        
        # Use Docker service name if base_url contains "puppygraph" or use extracted host
        if "puppygraph" in host or host == "localhost" or host.startswith("127."):
            bolt_host = "puppygraph"  # Docker service name
        else:
            bolt_host = host
        
        bolt_uri = f"bolt://{bolt_host}:7687"
        
        if NEO4J_AVAILABLE:
            try:
                # Use Neo4j driver for Bolt protocol
                driver = GraphDatabase.driver(
                    bolt_uri,
                    auth=(self.username, self.password)
                )
                with driver.session() as session:
                    result = session.run(query)
                    records = [dict(record) for record in result]
                    driver.close()
                    return {"results": records, "columns": list(records[0].keys()) if records else []}
            except Exception as e:
                logger.error(f"Bolt protocol query failed: {e}")
                raise Exception(f"PuppyGraph Bolt query failed: {str(e)}")
        else:
            # Fallback: Try HTTP endpoint (may not work)
            try:
                url = f"{self.base_url}/api/query"
                response = self.session.post(
                    url,
                    json={"query": query, "language": "cypher"},
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                if response.status_code == 200:
                    return response.json()
                raise Exception(f"HTTP endpoint returned {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"PuppyGraph HTTP query failed: {e}")
                raise Exception(f"PuppyGraph query failed. Install neo4j driver for Bolt protocol support: {str(e)}")
    
    def execute_gremlin(self, query: str) -> Dict[str, Any]:
        """
        Execute a Gremlin query.
        
        Args:
            query: Gremlin query string
            
        Returns:
            Query results as dictionary
        """
        try:
            # PuppyGraph query endpoint (used by Web UI)
            url = f"{self.base_url}/api/query"
            response = self.session.post(
                url,
                json={"query": query, "language": "gremlin"},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
            
            # If that fails, try alternative endpoint
            url = f"{self.base_url}/query"
            response = self.session.post(
                url,
                json={"query": query, "language": "gremlin"},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"PuppyGraph gremlin query failed: {e}")
            raise Exception(f"PuppyGraph query failed: {str(e)}")
    
    def health_check(self) -> bool:
        """
        Check if PuppyGraph is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            url = f"{self.base_url}/api/health"
            response = self.session.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"PuppyGraph health check failed: {e}")
            return False


# Global instance (will be initialized on first use)
_puppygraph_client: Optional[PuppyGraphClient] = None


def get_puppygraph_client() -> PuppyGraphClient:
    """Get or create PuppyGraph client instance."""
    global _puppygraph_client
    if _puppygraph_client is None:
        _puppygraph_client = PuppyGraphClient()
    return _puppygraph_client
