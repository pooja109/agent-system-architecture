"""
Inbox Monitor Databricks Client - Core Implementation (Phases 1-3)
==================================================================

Databricks client service specifically for the inbox monitor scenario tracking system.
Provides high-performance, reliable storage and retrieval of scenario processing data
as specified in Phase 6 requirements.
"""

import asyncio
import json
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Union
import uuid
from contextlib import asynccontextmanager

import structlog
from pydantic import BaseModel

try:
    from services.scenario_tracking_client import ScenarioTrackingClient
    from database.scenario_tracking_models import (
        ScenarioProcessingRecord,
        ScenarioTrackingConfiguration,
        ScenarioType
    )
    from services.scenario_tracking_exceptions import (
        DatabaseConnectionError,
        DataValidationError,
        BatchProcessingError,
        QueryExecutionError,
        ServiceUnavailableError,
        TableInitializationError
    )
except ImportError:
    from .scenario_tracking_client import ScenarioTrackingClient
    from ..database.scenario_tracking_models import (
        ScenarioProcessingRecord,
        ScenarioTrackingConfiguration,
        ScenarioType
    )
    from .scenario_tracking_exceptions import (
        DatabaseConnectionError,
        DataValidationError,
        BatchProcessingError,
        QueryExecutionError,
        ServiceUnavailableError,
        TableInitializationError
    )

logger = structlog.get_logger(__name__)


class InboxMonitorDatabricksClient:
    """
    Inbox Monitor Databricks Client for Phase 6 compliance.
    
    This class provides the exact interface specified in the Phase 6 prompt
    while internally using the robust ScenarioTrackingClient implementation.
    """
    
    def __init__(self, table_suffix: str = "", config: ScenarioTrackingConfiguration = None):
        """Initialize the Inbox Monitor Databricks client.
        
        Args:
            table_suffix: Table suffix for environment isolation
            config: Optional configuration override
        """
        self.table_suffix = table_suffix
        self.config = config or ScenarioTrackingConfiguration()
        
        # Update config with table suffix if provided
        if table_suffix:
            # Set environment variable for the underlying client
            import os
            os.environ["DATABRICKS_TABLE_SUFFIX"] = table_suffix
        
        # Initialize the underlying scenario tracking client
        self._client = ScenarioTrackingClient(config=self.config)
        self.logger = structlog.get_logger(__name__)
        
        # Track whether we're in a context manager
        self._in_context = False
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self._client.__aenter__()
        self._in_context = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self._client.__aexit__(exc_type, exc_val, exc_tb)
        self._in_context = False
    
    async def store_scenario_processing_record(
        self, 
        record: ScenarioProcessingRecord
    ) -> bool:
        """Store a scenario processing record.
        
        Args:
            record: The scenario processing record to store
            
        Returns:
            True if storage was successful, False otherwise
            
        Raises:
            DataValidationError: If the record fails validation
            DatabaseConnectionError: If database connection fails
        """
        # Input validation
        if not isinstance(record, ScenarioProcessingRecord):
            raise DataValidationError(f"Expected ScenarioProcessingRecord, got {type(record)}")
        
        # Validate critical fields
        if not record.processing_id or not record.processing_id.strip():
            raise DataValidationError("processing_id cannot be empty")
        
        if not record.email_id or not record.email_id.strip():
            raise DataValidationError("email_id cannot be empty")
            
        if not record.sender_email or not record.sender_email.strip():
            raise DataValidationError("sender_email cannot be empty")
            
        # Validate email format (basic check)
        if "@" not in record.sender_email or "." not in record.sender_email:
            self.logger.warning("Potentially invalid sender email format", extra={"email": record.sender_email})
        
        try:
            # Ensure the client is properly initialized
            if not self._in_context:
                self.logger.warning(
                    "store_scenario_processing_record called outside context manager - "
                    "initializing client automatically"
                )
                await self._client.initialize_table()
            
            # Use the underlying client's store method
            result = await self._client.store_scenario_result(record)
            
            if result:
                self.logger.debug(
                    "Scenario processing record stored successfully",
                    processing_id=record.processing_id,
                    email_id=record.email_id,
                    scenario_type=record.scenario_type.value if record.scenario_type else None
                )
            else:
                self.logger.warning(
                    "Failed to store scenario processing record",
                    processing_id=record.processing_id,
                    email_id=record.email_id
                )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Error storing scenario processing record",
                error=str(e),
                process_id=getattr(record, 'process_id', 'unknown'),
                email_id=getattr(record, 'email_id', 'unknown')
            )
            # Return False instead of raising to maintain non-blocking behavior
            return False
    
    async def get_recent_scenario_records(
        self, 
        limit: int = 100
    ) -> List[ScenarioProcessingRecord]:
        """Get recent scenario processing records.
        
        Args:
            limit: Maximum number of records to retrieve (1-10000)
            
        Returns:
            List of recent scenario processing records
            
        Raises:
            DataValidationError: If limit is invalid
        """
        # Input validation
        if not isinstance(limit, int):
            raise DataValidationError(f"limit must be integer, got {type(limit)}")
            
        if limit <= 0:
            raise DataValidationError(f"limit must be positive, got {limit}")
            
        if limit > 10000:
            raise DataValidationError(f"limit too large: {limit} (max 10000)")
        try:
            # Ensure the client is properly initialized
            if not self._in_context:
                self.logger.warning(
                    "get_recent_scenario_records called outside context manager - "
                    "initializing client automatically"
                )
                await self._client.initialize_table()
            
            # Use the underlying client's query methods to get recent records
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                # Query for recent records
                query = f"""
                    SELECT *
                    FROM inbox_monitor_scenario_processing{self.table_suffix}
                    WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 7 DAYS
                    ORDER BY processed_at DESC
                    LIMIT {limit}
                """
                
                result = await connection.execute_query(query, {})
                rows = result.fetchall()
                
                # Convert database rows to ScenarioProcessingRecord objects
                records = []
                for row in rows:
                    try:
                        # Create record from database row
                        record_dict = dict(row)
                        # Convert datetime strings back to datetime objects if needed
                        if 'received_datetime' in record_dict and isinstance(record_dict['received_datetime'], str):
                            record_dict['received_datetime'] = datetime.fromisoformat(record_dict['received_datetime'].replace('Z', '+00:00'))
                        if 'processed_at' in record_dict and isinstance(record_dict['processed_at'], str):
                            record_dict['processed_at'] = datetime.fromisoformat(record_dict['processed_at'].replace('Z', '+00:00'))
                        
                        # Convert scenario_type string to enum if needed
                        if 'scenario_type' in record_dict and isinstance(record_dict['scenario_type'], str):
                            record_dict['scenario_type'] = ScenarioType(record_dict['scenario_type'])
                        
                        # Handle JSON fields
                        for json_field in ['recipient_emails', 'emails_forwarded', 'agent_actions_log', 'external_operations_status']:
                            if json_field in record_dict and isinstance(record_dict[json_field], str):
                                try:
                                    record_dict[json_field] = json.loads(record_dict[json_field])
                                except (json.JSONDecodeError, TypeError):
                                    record_dict[json_field] = [] if json_field != 'external_operations_status' else {}
                        
                        record = ScenarioProcessingRecord(**record_dict)
                        records.append(record)
                        
                    except Exception as row_error:
                        self.logger.warning(
                            "Failed to create ScenarioProcessingRecord from database row",
                            error=str(row_error),
                            process_id=row.get('process_id', 'unknown')
                        )
                        continue
                
                self.logger.info(
                    "Retrieved recent scenario records",
                    record_count=len(records),
                    limit=limit
                )
                
                return records
            
        except Exception as e:
            self.logger.error(
                "Error retrieving recent scenario records",
                error=str(e),
                limit=limit
            )
            return []
    
    async def get_scenario_records_by_email_id(
        self, 
        email_id: str
    ) -> List[ScenarioProcessingRecord]:
        """Get scenario records for a specific email ID.
        
        Args:
            email_id: The email ID to search for (non-empty string)
            
        Returns:
            List of scenario processing records for the email
            
        Raises:
            DataValidationError: If email_id is invalid
        """
        # Input validation
        if not isinstance(email_id, str):
            raise DataValidationError(f"email_id must be string, got {type(email_id)}")
            
        if not email_id or not email_id.strip():
            raise DataValidationError("email_id cannot be empty")
            
        if len(email_id.strip()) > 500:
            raise DataValidationError(f"email_id too long: {len(email_id)} chars (max 500)")
        try:
            # Ensure the client is properly initialized
            if not self._in_context:
                self.logger.warning(
                    "get_scenario_records_by_email_id called outside context manager - "
                    "initializing client automatically"
                )
                await self._client.initialize_table()
            
            # Use the underlying client's query methods
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                # Query for records with specific email ID
                query = f"""
                    SELECT *
                    FROM inbox_monitor_scenario_processing{self.table_suffix}
                    WHERE email_id = ?
                    ORDER BY processed_at DESC
                """
                
                result = await connection.execute_query(query, [email_id])
                rows = result.fetchall()
                
                # Convert database rows to ScenarioProcessingRecord objects
                records = []
                for row in rows:
                    try:
                        # Create record from database row
                        record_dict = dict(row)
                        # Convert datetime strings back to datetime objects if needed
                        if 'received_datetime' in record_dict and isinstance(record_dict['received_datetime'], str):
                            record_dict['received_datetime'] = datetime.fromisoformat(record_dict['received_datetime'].replace('Z', '+00:00'))
                        if 'processed_at' in record_dict and isinstance(record_dict['processed_at'], str):
                            record_dict['processed_at'] = datetime.fromisoformat(record_dict['processed_at'].replace('Z', '+00:00'))
                        
                        # Convert scenario_type string to enum if needed
                        if 'scenario_type' in record_dict and isinstance(record_dict['scenario_type'], str):
                            record_dict['scenario_type'] = ScenarioType(record_dict['scenario_type'])
                        
                        # Handle JSON fields
                        for json_field in ['recipient_emails', 'emails_forwarded', 'agent_actions_log', 'external_operations_status']:
                            if json_field in record_dict and isinstance(record_dict[json_field], str):
                                try:
                                    record_dict[json_field] = json.loads(record_dict[json_field])
                                except (json.JSONDecodeError, TypeError):
                                    record_dict[json_field] = [] if json_field != 'external_operations_status' else {}
                        
                        record = ScenarioProcessingRecord(**record_dict)
                        records.append(record)
                        
                    except Exception as row_error:
                        self.logger.warning(
                            "Failed to create ScenarioProcessingRecord from database row",
                            error=str(row_error),
                            process_id=row.get('process_id', 'unknown')
                        )
                        continue
                
                self.logger.info(
                    "Retrieved scenario records by email ID",
                    email_id=email_id,
                    record_count=len(records)
                )
                
                return records
            
        except Exception as e:
            self.logger.error(
                "Error retrieving scenario records by email ID",
                error=str(e),
                email_id=email_id
            )
            return []
    
    async def get_scenario_records_by_sender(
        self, 
        sender_email: str
    ) -> List[ScenarioProcessingRecord]:
        """Get scenario records for a specific sender.
        
        Args:
            sender_email: The sender email to search for (valid email format)
            
        Returns:
            List of scenario processing records from the sender
            
        Raises:
            DataValidationError: If sender_email is invalid
        """
        # Input validation
        if not isinstance(sender_email, str):
            raise DataValidationError(f"sender_email must be string, got {type(sender_email)}")
            
        if not sender_email or not sender_email.strip():
            raise DataValidationError("sender_email cannot be empty")
            
        # Basic email format validation
        email_cleaned = sender_email.strip().lower()
        if "@" not in email_cleaned or "." not in email_cleaned:
            raise DataValidationError(f"Invalid email format: {sender_email}")
            
        if len(email_cleaned) > 320:  # RFC 5321 limit
            raise DataValidationError(f"sender_email too long: {len(email_cleaned)} chars (max 320)")
        try:
            # Ensure the client is properly initialized
            if not self._in_context:
                self.logger.warning(
                    "get_scenario_records_by_sender called outside context manager - "
                    "initializing client automatically"
                )
                await self._client.initialize_table()
            
            # Use the underlying client's query methods
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                # Query for records with specific sender email
                query = f"""
                    SELECT *
                    FROM inbox_monitor_scenario_processing{self.table_suffix}
                    WHERE sender_email = ?
                    ORDER BY processed_at DESC
                    LIMIT 100
                """
                
                result = await connection.execute_query(query, [sender_email])
                rows = result.fetchall()
                
                # Convert database rows to ScenarioProcessingRecord objects
                records = []
                for row in rows:
                    try:
                        # Create record from database row
                        record_dict = dict(row)
                        # Convert datetime strings back to datetime objects if needed
                        if 'received_datetime' in record_dict and isinstance(record_dict['received_datetime'], str):
                            record_dict['received_datetime'] = datetime.fromisoformat(record_dict['received_datetime'].replace('Z', '+00:00'))
                        if 'processed_at' in record_dict and isinstance(record_dict['processed_at'], str):
                            record_dict['processed_at'] = datetime.fromisoformat(record_dict['processed_at'].replace('Z', '+00:00'))
                        
                        # Convert scenario_type string to enum if needed
                        if 'scenario_type' in record_dict and isinstance(record_dict['scenario_type'], str):
                            record_dict['scenario_type'] = ScenarioType(record_dict['scenario_type'])
                        
                        # Handle JSON fields
                        for json_field in ['recipient_emails', 'emails_forwarded', 'agent_actions_log', 'external_operations_status']:
                            if json_field in record_dict and isinstance(record_dict[json_field], str):
                                try:
                                    record_dict[json_field] = json.loads(record_dict[json_field])
                                except (json.JSONDecodeError, TypeError):
                                    record_dict[json_field] = [] if json_field != 'external_operations_status' else {}
                        
                        record = ScenarioProcessingRecord(**record_dict)
                        records.append(record)
                        
                    except Exception as row_error:
                        self.logger.warning(
                            "Failed to create ScenarioProcessingRecord from database row",
                            error=str(row_error),
                            process_id=row.get('process_id', 'unknown')
                        )
                        continue
                
                self.logger.info(
                    "Retrieved scenario records by sender",
                    sender_email=sender_email,
                    record_count=len(records)
                )
                
                return records
            
        except Exception as e:
            self.logger.error(
                "Error retrieving scenario records by sender",
                error=str(e),
                sender_email=sender_email
            )
            return []
    
    async def test_connection(self) -> bool:
        """Test the database connection.
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            health = await self._client.health_check()
            return health.get("status") in ["healthy", "degraded"]
            
        except Exception as e:
            self.logger.error(
                "Database connection test failed",
                error=str(e)
            )
            return False
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status of the client.
        
        Returns:
            Dictionary with health status information
        """
        try:
            health = await self._client.health_check()
            
            # Add client-specific information
            health["client_type"] = "InboxMonitorDatabricksClient"
            health["table_suffix"] = self.table_suffix
            health["in_context_manager"] = self._in_context
            
            return health
            
        except Exception as e:
            return {
                "client_type": "InboxMonitorDatabricksClient",
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check and return status.
        
        Returns:
            Dictionary with health check results
        """
        # Alias for get_health_status to match test expectations
        return await self.get_health_status()
    
    async def flush_pending_operations(self):
        """Flush any pending async operations."""
        try:
            await self._client.flush_pending_inserts()
            self.logger.debug("Flushed pending operations successfully")
            
        except Exception as e:
            self.logger.error(
                "Error flushing pending operations",
                error=str(e)
            )
    
    @property
    def metrics(self):
        """Get performance metrics from the underlying client."""
        return self._client.metrics
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        try:
            return await self._client.get_performance_metrics()
        except Exception as e:
            self.logger.error(
                "Error retrieving performance metrics",
                error=str(e)
            )
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def store_scenario_processing_records_batch(
        self, 
        records: List[ScenarioProcessingRecord]
    ) -> Dict[str, Any]:
        """Store multiple scenario processing records in batch.
        
        Args:
            records: List of scenario processing records to store
            
        Returns:
            Dictionary with batch processing results
            
        Raises:
            DataValidationError: If any records fail validation
            BatchProcessingError: If batch processing fails
        """
        # Input validation
        if not isinstance(records, list):
            raise DataValidationError(f"Expected list of records, got {type(records)}")
            
        if not records:
            raise DataValidationError("Cannot process empty record list")
            
        if len(records) > 1000:  # Reasonable batch size limit
            raise DataValidationError(f"Batch size too large: {len(records)} (max 1000)")
        
        # Validate each record
        validation_errors = []
        for i, record in enumerate(records):
            try:
                if not isinstance(record, ScenarioProcessingRecord):
                    validation_errors.append(f"Record {i}: Expected ScenarioProcessingRecord, got {type(record)}")
                    continue
                    
                if not record.processing_id or not record.processing_id.strip():
                    validation_errors.append(f"Record {i}: processing_id cannot be empty")
                    
                if not record.email_id or not record.email_id.strip():
                    validation_errors.append(f"Record {i}: email_id cannot be empty")
                    
            except Exception as e:
                validation_errors.append(f"Record {i}: Validation error - {str(e)}")
        
        if validation_errors:
            error_summary = "; ".join(validation_errors[:5])  # Show first 5 errors
            if len(validation_errors) > 5:
                error_summary += f" and {len(validation_errors) - 5} more errors"
            raise DataValidationError(f"Batch validation failed: {error_summary}")
        
        try:
            # Ensure the client is properly initialized
            if not self._in_context:
                self.logger.warning(
                    "store_scenario_processing_records_batch called outside context manager - "
                    "initializing client automatically"
                )
                await self._client.initialize_table()
            
            # Use the underlying client's batch store method
            result = await self._client.store_scenario_results_batch(records)
            
            self.logger.info(
                "Batch scenario processing records stored",
                batch_size=len(records),
                successful_records=result.get("successful_records", 0),
                failed_records=result.get("failed_records", 0)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Error storing batch scenario processing records",
                error=str(e),
                batch_size=len(records)
            )
            # Return error result format
            return {
                "successful_records": 0,
                "failed_records": len(records),
                "error": str(e)
            }


# Alias for backward compatibility and easier imports
DatabricksClient = InboxMonitorDatabricksClient