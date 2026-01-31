"""
Trino Client Utility Module
Handles all Trino operations using the official Python client
"""

from trino.dbapi import connect
from trino.exceptions import TrinoQueryError, TrinoUserError, TrinoDataError
from typing import Dict, List, Any, Optional, Tuple
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrinoClientManager:
    """Manages Trino connections and operations using the official Python client."""
    
    def __init__(self, host: str = "trino-coordinator", port: int = 8080):
        self.host = host
        self.port = port
        self._connection_pool = {}
    
    def get_connection(self, user: str, catalog: str = "postgres", schema: str = "public"):
        """Get or create a Trino connection for the specified user and catalog."""
        connection_key = f"{user}_{catalog}_{schema}"
        
        if connection_key not in self._connection_pool:
            logger.info(f"Creating new Trino connection for {connection_key}")
            connection = connect(
                host=self.host,
                port=self.port,
                user=user,
                catalog=catalog,
                schema=schema,
                http_scheme="http",
                verify=False,  # For development - enable SSL verification in production
                request_timeout=30
            )
            self._connection_pool[connection_key] = connection
        else:
            logger.debug(f"Reusing existing Trino connection for {connection_key}")
        
        return self._connection_pool[connection_key]
    
    @contextmanager
    def execute_query(self, user: str, catalog: str, schema: str, query: str):
        """
        Execute a query using the Trino client with automatic result handling.
        
        Yields:
            Tuple of (success: bool, data: List, columns: List, error: str)
        """
        connection = None
        try:
            # Get connection
            connection = self.get_connection(user, catalog, schema)
            
            # Execute query
            logger.info(f"Executing query for user {user} on {catalog}.{schema}")
            logger.debug(f"Query: {query}")
            
            cursor = connection.cursor()
            cursor.execute(query)
            
            # Get results
            if cursor.description:
                # Query returned data
                columns = [{"name": desc[0], "type": str(desc[1])} for desc in cursor.description]
                data = cursor.fetchall()
                
                logger.info(f"Query completed successfully. Rows: {len(data)}, Columns: {len(columns)}")
                yield True, data, columns, None
                
            else:
                # DDL/DML query (CREATE, INSERT, UPDATE, DELETE, etc.)
                logger.info("DDL/DML query completed successfully")
                yield True, [], [], None
                
        except TrinoQueryError as e:
            error_msg = f"Trino query error: {str(e)}"
            logger.error(error_msg)
            yield False, [], [], error_msg
            
        except TrinoUserError as e:
            error_msg = f"Trino user error: {str(e)}"
            logger.error(error_msg)
            yield False, [], [], error_msg
            
        except TrinoDataError as e:
            error_msg = f"Trino data error: {str(e)}"
            logger.error(error_msg)
            yield False, [], [], error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error executing query: {str(e)}"
            logger.error(error_msg)
            yield False, [], [], error_msg
            
        finally:
            if connection:
                try:
                    cursor.close()
                except:
                    pass
    
    def test_connection(self, user: str = "admin", catalog: str = "postgres", schema: str = "public") -> bool:
        """Test if we can connect to Trino and execute a simple query."""
        try:
            with self.execute_query(user, catalog, schema, "SELECT 1 as test") as (success, data, columns, error):
                return success and len(data) > 0
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_catalogs(self, user: str = "admin") -> List[str]:
        """Get list of available catalogs."""
        try:
            with self.execute_query(user, "system", "information_schema", "SHOW CATALOGS") as (success, data, columns, error):
                if success:
                    return [row[0] for row in data]
                return []
        except Exception as e:
            logger.error(f"Failed to get catalogs: {e}")
            return []
    
    def get_schemas(self, user: str, catalog: str) -> List[str]:
        """Get list of available schemas for a catalog."""
        try:
            with self.execute_query(user, catalog, "information_schema", f"SHOW SCHEMAS FROM {catalog}") as (success, data, columns, error):
                if success:
                    return [row[0] for row in data]
                return []
        except Exception as e:
            logger.error(f"Failed to get schemas for {catalog}: {e}")
            return []
    
    def get_tables(self, user: str, catalog: str, schema: str) -> List[str]:
        """Get list of available tables for a schema."""
        try:
            with self.execute_query(user, catalog, schema, f"SHOW TABLES FROM {catalog}.{schema}") as (success, data, columns, error):
                if success:
                    return [row[0] for row in data]
                return []
        except Exception as e:
            logger.error(f"Failed to get tables for {catalog}.{schema}: {e}")
            return []

# Global Trino client manager instance
trino_client = TrinoClientManager()

def get_trino_client() -> TrinoClientManager:
    """Get the global Trino client manager instance."""
    return trino_client 