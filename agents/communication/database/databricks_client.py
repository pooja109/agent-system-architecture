import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid

from databricks import sql
from databricks.sql.client import Connection, Cursor
from models import DatabricksSettings

logger = logging.getLogger(__name__)

class DatabricksClient:
    """Client for interacting with Databricks SQL Warehouse."""
    
    def __init__(self, settings: DatabricksSettings):
        """Initialize Databricks client with settings."""
        self.settings = settings
        self.connection: Optional[Connection] = None
        self._table_name = f"`{settings.catalog}`.`{settings.schema}`.`email_communication_pipeline{settings.table_suffix}`"
        
    def connect(self) -> bool:
        """Establish connection to Databricks."""
        try:
            self.connection = sql.connect(
                server_hostname=self.settings.server_hostname,
                http_path=self.settings.http_path,
                access_token=self.settings.access_token
            )
            logger.info("Successfully connected to Databricks")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Databricks: {e}")
            return False
    
    def disconnect(self):
        """Close Databricks connection."""
        if self.connection:
            try:
                self.connection.close()
                logger.info("Disconnected from Databricks")
            except Exception as e:
                logger.error(f"Error disconnecting from Databricks: {e}")
            finally:
                self.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def execute_query(self, query: str, parameters: Optional[List] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results."""
        if not self.connection:
            raise RuntimeError("Not connected to Databricks. Call connect() first.")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, parameters or [])
                
                # Get column names
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                
                # Fetch all rows
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                results = []
                for row in rows:
                    row_dict = dict(zip(columns, row))
                    results.append(row_dict)
                
                logger.debug(f"Query executed successfully, returned {len(results)} rows")
                return results
                
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    def execute_update(self, query: str, parameters: Optional[List] = None) -> int:
        """Execute an update/insert/delete query and return affected row count.
        
        Note: Databricks SQL connector may return -1 for rowcount on UPDATE statements.
        This method returns 1 to indicate successful execution if no exception occurs.
        """
        if not self.connection:
            raise RuntimeError("Not connected to Databricks. Call connect() first.")
        
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, parameters or [])
                
                # Databricks SQL connector often returns -1 for UPDATE statements
                # If no exception occurred, assume the update was successful
                affected_rows = cursor.rowcount
                
                if affected_rows == -1:
                    # Databricks limitation - assume success if no exception
                    logger.debug(f"Update query executed (Databricks returned -1 rowcount, assuming success)")
                    return 1  # Return 1 to indicate successful execution
                else:
                    logger.debug(f"Update query executed successfully, affected {affected_rows} rows")
                    return affected_rows
                
        except Exception as e:
            logger.error(f"Error executing update query: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Parameters: {parameters}")
            raise
    
    
    
    
    
    def test_connection(self) -> bool:
        """Test the Databricks connection."""
        try:
            query = "SELECT 1 as test"
            result = self.execute_query(query)
            return len(result) == 1 and result[0]['test'] == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False