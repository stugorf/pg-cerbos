"""
PuppyGraph Client

This module provides a client for querying PuppyGraph graph database.
PuppyGraph allows querying PostgreSQL data as a graph using openCypher or Gremlin.
"""
import os
import logging
import requests
from typing import Optional, Dict, Any, List
from requests.auth import HTTPBasicAuth

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
        Execute an openCypher query.
        
        Args:
            query: openCypher query string
            
        Returns:
            Query results as dictionary
        """
        try:
            # PuppyGraph openCypher endpoint (Bolt protocol over HTTP)
            url = f"{self.base_url}/api/cypher"
            response = self.session.post(
                url,
                json={"query": query},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"PuppyGraph cypher query failed: {e}")
            raise Exception(f"PuppyGraph query failed: {str(e)}")
    
    def execute_gremlin(self, query: str) -> Dict[str, Any]:
        """
        Execute a Gremlin query.
        
        Args:
            query: Gremlin query string
            
        Returns:
            Query results as dictionary
        """
        try:
            # PuppyGraph Gremlin endpoint
            url = f"{self.base_url}/api/gremlin"
            response = self.session.post(
                url,
                json={"query": query},
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
