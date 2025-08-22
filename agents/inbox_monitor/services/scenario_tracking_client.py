"""
Databricks client service for scenario tracking operations.
Provides high-performance, reliable storage and retrieval of scenario processing data.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Union
import uuid
from contextlib import asynccontextmanager
import json

import structlog
from pydantic import BaseModel

try:
    from services.pooled_service_base import PooledServiceBase
    from services.databricks_oauth_client import DatabricksOAuthClient
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
    from services.scenario_tracking_metrics import (
        get_metrics_instance,
        record_operation_metric
    )
except ImportError:
    from ..services.pooled_service_base import PooledServiceBase
    from ..services.databricks_oauth_client import DatabricksOAuthClient
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
    from .scenario_tracking_metrics import (
        get_metrics_instance,
        record_operation_metric
    )

logger = structlog.get_logger(__name__)


class ScenarioAnalyticsResult(BaseModel):
    """Result structure for scenario analytics queries."""
    total_processed: int
    success_rate: float
    scenario_breakdown: Dict[str, int]
    expert_assignments: Dict[str, int]
    processing_time_stats: Dict[str, float]
    time_period: str


class CustomerInteractionHistory(BaseModel):
    """Customer interaction history result."""
    customer_email: str
    total_interactions: int
    scenario_types: List[str]
    last_interaction: datetime
    success_rate: float
    interactions: List[Dict[str, Any]]


class ExpertWorkloadStats(BaseModel):
    """Expert workload statistics."""
    expert_name: str
    expert_email: str
    total_assignments: int
    active_assignments: int
    success_rate: float
    average_processing_time: float
    last_assignment: Optional[datetime]


class ScenarioTrackingClient(PooledServiceBase):
    """
    High-performance Databricks client for scenario tracking operations.
    Provides reliable storage, retrieval, and analytics for scenario processing data.
    """
    
    def __init__(self, config: ScenarioTrackingConfiguration = None):
        """Initialize scenario tracking client with configuration.
        
        Args:
            config: Configuration for tracking operations
        """
        super().__init__()
        self.config = config or ScenarioTrackingConfiguration()
        self.metrics = get_metrics_instance()
        self._table_name: Optional[str] = None
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = None
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 300  # 5 minutes
        
        # Initialize logging
        self.logger = structlog.get_logger(__name__)
        
        # Reset circuit breaker on startup for fresh start
        self.reset_circuit_breaker()
        
        # Performance optimization settings
        self._batch_insert_queue: List[ScenarioProcessingRecord] = []
        self._batch_insert_lock = asyncio.Lock()
        self._background_batch_task: Optional[asyncio.Task] = None
        
        if self.config.async_insert:
            # Don't start background processing immediately - defer until first async operation
            # This avoids RuntimeError when no event loop is running during initialization
            pass
    
    async def _ensure_table_name(self):
        """Ensure table name is initialized with current configuration."""
        if self._table_name is None:
            try:
                from config.settings import get_settings
                import os
                settings = await get_settings()
                schema_name = settings.databricks_oauth.schema_name
                catalog = settings.databricks_oauth.catalog
                # Use DATABRICKS_TABLE_SUFFIX environment variable directly
                suffix = os.getenv("DATABRICKS_TABLE_SUFFIX", "")
                self._table_name = f"`{catalog}`.`{schema_name}`.`inbox_monitor_scenario_processing{suffix}`"
            except Exception as e:
                self.logger.error("Failed to initialize table name", extra={"error": str(e)})
                raise ServiceUnavailableError("Could not initialize service configuration")
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open."""
        if self._circuit_breaker_failures < self._circuit_breaker_threshold:
            return False
        
        if self._circuit_breaker_last_failure is None:
            return False
        
        time_since_failure = time.time() - self._circuit_breaker_last_failure
        return time_since_failure < self._circuit_breaker_timeout
    
    def _record_circuit_breaker_failure(self):
        """Record a failure for circuit breaker logic."""
        self._circuit_breaker_failures += 1
        self._circuit_breaker_last_failure = time.time()
        
        if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
            self.logger.warning(
                "Circuit breaker activated",
                extra={
                    "failures": self._circuit_breaker_failures,
                    "threshold": self._circuit_breaker_threshold
                }
            )
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker after successful operation."""
        if self._circuit_breaker_failures > 0:
            self.logger.info("Circuit breaker reset after successful operation")
            self._circuit_breaker_failures = 0
            self._circuit_breaker_last_failure = None
    
    def reset_circuit_breaker(self):
        """Public method to reset circuit breaker - useful for startup/recovery."""
        self.logger.info("Manually resetting circuit breaker")
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = None
    
    async def _ensure_background_processing_started(self):
        """Ensure background batch processing is started when event loop is available."""
        if (self.config.async_insert and 
            self._background_batch_task is None and 
            not self._is_circuit_breaker_open()):
            
            try:
                self._start_background_batch_processing()
                self.logger.debug("Background batch processing started")
            except Exception as e:
                self.logger.warning("Failed to start background processing", extra={"error": str(e)})
    
    async def initialize_table(self) -> bool:
        """Initialize the scenario tracking table if it doesn't exist.
        
        Returns:
            True if table exists or was created successfully
            
        Raises:
            ServiceUnavailableError: If initialization fails
        """
        if self._is_circuit_breaker_open():
            raise ServiceUnavailableError("Service circuit breaker is open")
        
        start_time = time.time()
        
        try:
            await self._ensure_table_name()
            
            # Read schema SQL file
            import os
            from pathlib import Path
            
            current_dir = Path(__file__).parent.parent
            schema_file = current_dir / "database" / "scenario_tracking_schema.sql"
            
            if not schema_file.exists():
                raise TableInitializationError(f"Schema file not found: {schema_file}")
            
            with open(schema_file, 'r') as f:
                schema_sql = f.read()
            
            # Replace placeholders with actual configuration
            from config.settings import get_settings
            settings = await get_settings()
            
            formatted_sql = schema_sql.format(
                catalog=settings.databricks_oauth.catalog,
                schema=settings.databricks_oauth.schema_name,
                table_suffix=settings.databricks_oauth.table_suffix
            )
            
            # Execute table creation
            result = await self.execute_with_connection(
                self._execute_table_initialization,
                formatted_sql
            )
            
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("initialize_table", duration_ms, success=result)
            
            if result:
                self._reset_circuit_breaker()
                self.logger.info("Scenario tracking table initialized successfully")
                return True
            else:
                self._record_circuit_breaker_failure()
                raise ServiceUnavailableError("Table initialization failed")
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("initialize_table", duration_ms, success=False, 
                                         error_type=type(e).__name__)
            self._record_circuit_breaker_failure()
            self.logger.error("Failed to initialize table", extra={"error": str(e)})
            if isinstance(e, (ServiceUnavailableError, TableInitializationError)):
                raise
            raise TableInitializationError(f"Table initialization failed: {e}")
    
    async def _execute_table_initialization(self, connection: DatabricksOAuthClient, 
                                          schema_sql: str) -> bool:
        """Execute table initialization SQL."""
        try:
            # Split SQL into individual statements
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement:
                    await connection.execute_sql(statement)
                    self.logger.debug("Executed schema statement", extra={"statement": statement[:50] + "..."})
            
            return True
            
        except Exception as e:
            self.logger.error("Table initialization failed", extra={"error": str(e)})
            return False
    
    async def store_scenario_result(
        self,
        record: ScenarioProcessingRecord,
        force_sync: bool = False
    ) -> bool:
        """Store a single scenario processing result.
        
        Args:
            record: Scenario processing record to store
            force_sync: Force synchronous storage (bypass async batching)
            
        Returns:
            True if storage successful (or queued for async)
            
        Raises:
            DataValidationError: If record validation fails
            ServiceUnavailableError: If service is unavailable
        """
        if self._is_circuit_breaker_open():
            raise ServiceUnavailableError("Service circuit breaker is open")
        
        start_time = time.time()
        
        try:
            # Validate record
            if not isinstance(record, ScenarioProcessingRecord):
                raise DataValidationError("Invalid record type provided")
            
            # Validate record data
            try:
                record_dict = record.to_databricks_dict()
            except Exception as e:
                raise DataValidationError(f"Record validation failed: {e}")
            
            # Handle async vs sync storage
            if self.config.async_insert and not force_sync:
                return await self._queue_for_batch_insert(record)
            else:
                return await self._store_single_record_sync(record)
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("store_scenario_result", duration_ms, 
                                         success=False, error_type=type(e).__name__)
            if not isinstance(e, (DataValidationError, ServiceUnavailableError)):
                self._record_circuit_breaker_failure()
            raise
    
    async def _queue_for_batch_insert(self, record: ScenarioProcessingRecord) -> bool:
        """Queue record for async batch insertion."""
        # Start background processing if not already started
        await self._ensure_background_processing_started()
        
        async with self._batch_insert_lock:
            self._batch_insert_queue.append(record)
            
            # Trigger immediate batch if queue is full
            if len(self._batch_insert_queue) >= self.config.batch_insert_size:
                await self._process_batch_queue()
        
        return True
    
    async def _store_single_record_sync(self, record: ScenarioProcessingRecord) -> bool:
        """Store single record synchronously."""
        await self._ensure_table_name()
        
        start_time = time.time()
        
        try:
            result = await self.execute_with_connection(
                self._execute_single_insert,
                record
            )
            
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("store_single_sync", duration_ms, success=result)
            
            if result:
                self._reset_circuit_breaker()
                return True
            else:
                self._record_circuit_breaker_failure()
                return False
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("store_single_sync", duration_ms, 
                                         success=False, error_type=type(e).__name__)
            self._record_circuit_breaker_failure()
            raise QueryExecutionError(f"Failed to store record: {e}")
    
    async def _execute_single_insert(self, connection: DatabricksOAuthClient,
                                   record: ScenarioProcessingRecord) -> bool:
        """Execute single record insertion."""
        try:
            record_dict = record.to_databricks_dict()
            
            # DEBUG: Check specific boolean fields
            for bool_field in ['process_success', 'has_attachments', 'test_mode', 'email_deleted']:
                if bool_field in record_dict:
                    self.logger.debug(f"Boolean field {bool_field}: value={record_dict[bool_field]}, type={type(record_dict[bool_field])}")
            
            # Separate array fields from scalar fields for special handling
            array_fields = ["recipient_emails", "agent_actions_log", "email_intent_detected_phrases", 
                           "emails_forwarded", "customer_scenario_history"]
            struct_array_fields = ["status_updates"]  # Arrays of structs need special handling
            map_fields = ["external_operations_status", "test_email_substitutions"]
            
            # Build parameters dict without array/map fields
            parameters = {}
            query_values = []
            column_names = []
            
            for col, value in record_dict.items():
                column_names.append(f"`{col}`")
                
                if col in array_fields:
                    # Handle arrays as literal SQL arrays
                    if value is None or (isinstance(value, list) and len(value) == 0):
                        query_values.append("ARRAY()")
                    else:
                        # CRITICAL FIX: Properly escape single quotes in array items
                        escaped_items = []
                        for item in value:
                            if item:
                                # Escape single quotes by doubling them
                                escaped_item = str(item).replace("'", "''")
                                escaped_items.append(f"'{escaped_item}'")
                            else:
                                escaped_items.append("''")
                        query_values.append(f"ARRAY({', '.join(escaped_items)})")
                elif col in struct_array_fields:
                    # Handle arrays of structs (like status_updates) - convert to empty array for now
                    query_values.append("ARRAY()")
                elif col in map_fields:
                    # Handle maps as literal SQL maps
                    if value is None or (isinstance(value, dict) and len(value) == 0):
                        query_values.append("MAP()")
                    else:
                        # CRITICAL FIX: Create proper SQL MAP literal instead of JSON string
                        if isinstance(value, dict):
                            map_pairs = []
                            for k, v in value.items():
                                # Escape single quotes in both keys and values
                                escaped_key = str(k).replace("'", "''")
                                escaped_value = str(v).replace("'", "''")
                                map_pairs.append(f"'{escaped_key}', '{escaped_value}'")
                            if map_pairs:
                                query_values.append(f"MAP({', '.join(map_pairs)})")
                            else:
                                query_values.append("MAP()")
                        else:
                            query_values.append("MAP()")
                else:
                    # Regular parameterized value - handle None values
                    if value is None:
                        query_values.append("NULL")
                    else:
                        # CRITICAL FIX: Ensure boolean values are converted to integers at parameter level
                        if isinstance(value, bool):
                            parameters[col] = 1 if value else 0
                            self.logger.debug(f"PARAMETER BOOLEAN FIX {col}: {value} -> {parameters[col]}")
                        else:
                            parameters[col] = value
                        query_values.append(f":{col}")
            
            column_names_str = ", ".join(column_names)
            values_str = ", ".join(query_values)
            
            query = f"""
            INSERT INTO {self._table_name}
            ({column_names_str})
            VALUES ({values_str})
            """
            
            # DEBUG: Check specific problematic parameters
            if 'process_success' in parameters:
                self.logger.debug(f"PARAMETER process_success: value={parameters['process_success']}, type={type(parameters['process_success'])}")
            
            self.logger.debug("Using parameterized query execution", 
                            extra={"attempt": 1, "parameter_count": len(parameters)})
            
            result = await connection.execute_sql(query, parameters)
            
            self.logger.debug(
                "Single record insert result",
                extra={
                    "processing_id": record.processing_id,
                    "email_id": record.email_id,
                    "insert_result": str(result),
                    "insert_result_type": type(result).__name__
                }
            )
            
            # NOTE: In Databricks, single INSERT statements are auto-committed
            # No explicit COMMIT needed for single inserts
            
            self.logger.debug(
                "Single record inserted successfully (auto-committed)",
                extra={
                    "processing_id": record.processing_id,
                    "email_id": record.email_id,
                    "auto_commit": True
                }
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Single record insertion failed",
                extra={
                    "error": str(e),
                    "processing_id": record.processing_id,
                    "email_id": record.email_id
                }
            )
            return False
    
    async def store_scenario_results_batch(
        self,
        records: List[ScenarioProcessingRecord]
    ) -> Dict[str, Any]:
        """Store multiple scenario processing results in a batch operation.
        
        Args:
            records: List of scenario processing records to store
            
        Returns:
            Dictionary with batch processing results
            
        Raises:
            BatchProcessingError: If batch processing fails significantly
        """
        if self._is_circuit_breaker_open():
            raise ServiceUnavailableError("Service circuit breaker is open")
        
        if not records:
            return {"successful_records": 0, "failed_records": 0, "total_records": 0}
        
        start_time = time.time()
        total_records = len(records)
        
        try:
            await self._ensure_table_name()
            
            # Validate all records first
            validated_records = []
            validation_errors = []
            
            for i, record in enumerate(records):
                try:
                    if not isinstance(record, ScenarioProcessingRecord):
                        raise DataValidationError(f"Record {i} is not a ScenarioProcessingRecord")
                    
                    # Validate serialization
                    record.to_databricks_dict()
                    validated_records.append(record)
                    
                except Exception as e:
                    validation_errors.append({"record_index": i, "error": str(e)})
            
            if validation_errors:
                self.logger.warning(
                    "Some records failed validation",
                    extra={
                        "failed_count": len(validation_errors),
                        "total_count": total_records,
                        "errors": validation_errors[:5]  # Log first 5 errors
                    }
                )
            
            # Process validated records in chunks
            chunk_size = min(self.config.batch_insert_size, len(validated_records))
            successful_records = 0
            failed_records = len(validation_errors)
            
            for i in range(0, len(validated_records), chunk_size):
                chunk = validated_records[i:i + chunk_size]
                
                try:
                    chunk_result = await self.execute_with_connection(
                        self._execute_batch_insert,
                        chunk
                    )
                    
                    if chunk_result:
                        successful_records += len(chunk)
                    else:
                        failed_records += len(chunk)
                        
                except Exception as e:
                    self.logger.error(f"Batch chunk failed: {e}")
                    failed_records += len(chunk)
            
            # Record batch metrics
            total_duration_ms = (time.time() - start_time) * 1000
            await self.metrics.record_batch_operation(
                batch_size=total_records,
                total_duration_ms=total_duration_ms,
                successful_records=successful_records,
                failed_records=failed_records
            )
            
            success_rate = successful_records / total_records if total_records > 0 else 0
            
            # Reset circuit breaker on good success rate
            if success_rate >= 0.8:
                self._reset_circuit_breaker()
            elif success_rate < 0.5:
                self._record_circuit_breaker_failure()
            
            result = {
                "successful_records": successful_records,
                "failed_records": failed_records,
                "total_records": total_records,
                "success_rate": success_rate,
                "processing_duration_ms": total_duration_ms,
                "validation_errors": validation_errors
            }
            
            # Raise exception if failure rate is too high
            if success_rate < 0.5 and total_records > 1:
                raise BatchProcessingError(
                    f"Batch processing had high failure rate: {success_rate:.1%}",
                    failed_count=failed_records,
                    total_count=total_records
                )
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("store_batch", duration_ms, 
                                         success=False, error_type=type(e).__name__)
            self._record_circuit_breaker_failure()
            
            if not isinstance(e, BatchProcessingError):
                raise BatchProcessingError(
                    f"Batch processing failed: {e}",
                    failed_count=total_records,
                    total_count=total_records
                )
            raise
    
    async def _execute_batch_insert(self, connection: DatabricksOAuthClient,
                                  records: List[ScenarioProcessingRecord]) -> bool:
        """Execute batch record insertion with transaction management."""
        if not records:
            return True
        
        # Start transaction for batch operation
        try:
            await connection.execute_sql("BEGIN")
            self.logger.debug("Started transaction for batch insert")
            
            # Convert all records to dict format
            record_dicts = []
            for record in records:
                record_dict = record.to_databricks_dict()
                record_dicts.append(record_dict)
            
            if not record_dicts:
                # No records to insert, operation complete
                return True
            
            # Get column names from first record
            columns = list(record_dicts[0].keys())
            column_names = ", ".join([f"`{col}`" for col in columns])
            
            # Build VALUES clause with proper NULL handling
            values_clauses = []
            for record_dict in record_dicts:
                values = []
                for col in columns:
                    value = record_dict.get(col)
                    if value is None:
                        values.append("NULL")
                    elif isinstance(value, str):
                        # Escape single quotes
                        escaped_value = value.replace("'", "''")
                        values.append(f"'{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        values.append(str(value))
                    elif isinstance(value, bool):
                        values.append("true" if value else "false")
                    elif isinstance(value, list):
                        # Convert list to JSON string for array columns
                        json_str = json.dumps(value).replace("'", "''")
                        values.append(f"'{json_str}'")
                    elif isinstance(value, dict):
                        # Convert dict to JSON string for map columns
                        json_str = json.dumps(value).replace("'", "''")
                        values.append(f"'{json_str}'")
                    else:
                        # Convert to string and escape
                        str_value = str(value).replace("'", "''")
                        values.append(f"'{str_value}'")
                
                values_clauses.append(f"({', '.join(values)})")
            
            # Build and execute insert query within transaction
            values_sql = ",\n    ".join(values_clauses)
            query = f"""
            INSERT INTO {self._table_name}
            ({column_names})
            VALUES
                {values_sql}
            """
            
            await connection.execute_sql(query)
            
            # NOTE: Databricks auto-commits batch inserts
            self.logger.info(
                "Batch insert completed successfully (auto-committed)",
                extra={
                    "record_count": len(records),
                    "table": self._table_name,
                    "auto_commit": True
                }
            )
            
            return True
            
        except Exception as e:
            # Rollback transaction on failure
            try:
                await connection.execute_sql("ROLLBACK")
                self.logger.warning(
                    "Transaction rolled back due to batch insert failure",
                    extra={
                        "error": str(e),
                        "record_count": len(records)
                    }
                )
            except Exception as rollback_error:
                self.logger.error(
                    "Failed to rollback transaction",
                    extra={
                        "rollback_error": str(rollback_error),
                        "original_error": str(e)
                    }
                )
            
            self.logger.error(
                "Batch insert failed",
                extra={
                    "error": str(e),
                    "record_count": len(records)
                }
            )
            return False
    
    def _start_background_batch_processing(self):
        """Start background task for batch processing."""
        async def batch_processor():
            while True:
                try:
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                    if self._batch_insert_queue:
                        async with self._batch_insert_lock:
                            if len(self._batch_insert_queue) >= 10:  # Process if 10+ items
                                await self._process_batch_queue()
                    
                except Exception as e:
                    self.logger.error("Background batch processor error", extra={"error": str(e)})
        
        self._background_batch_task = asyncio.create_task(batch_processor())
    
    async def _process_batch_queue(self):
        """Process queued records in batch."""
        if not self._batch_insert_queue:
            return
        
        # Take current queue contents
        queue_copy = self._batch_insert_queue.copy()
        self._batch_insert_queue.clear()
        
        try:
            result = await self.store_scenario_results_batch(queue_copy)
            self.logger.debug(
                "Background batch processed",
                extra={
                    "successful": result["successful_records"],
                    "failed": result["failed_records"]
                }
            )
            
        except Exception as e:
            self.logger.error("Background batch processing failed", extra={"error": str(e)})
            # Re-queue failed records (up to a limit)
            if len(self._batch_insert_queue) < self.config.batch_insert_size * 2:
                self._batch_insert_queue.extend(queue_copy)
    
    async def flush_pending_inserts(self):
        """Flush any pending async inserts immediately."""
        if self._batch_insert_queue:
            async with self._batch_insert_lock:
                await self._process_batch_queue()
    
    async def get_scenario_analytics(
        self,
        days_back: int = 30,
        scenario_types: Optional[List[ScenarioType]] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> ScenarioAnalyticsResult:
        """Get aggregated scenario analytics.
        
        Args:
            days_back: Number of days to look back
            scenario_types: Specific scenario types to analyze
            limit: Maximum number of results to return (None for unlimited)
            offset: Number of results to skip for pagination
            
        Returns:
            ScenarioAnalyticsResult with analytics data
        """
        start_time = time.time()
        
        try:
            await self._ensure_table_name()
            
            result = await self.execute_with_connection(
                self._execute_scenario_analytics,
                days_back,
                scenario_types,
                limit,
                offset
            )
            
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("get_scenario_analytics", duration_ms, success=True)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("get_scenario_analytics", duration_ms, 
                                         success=False, error_type=type(e).__name__)
            raise QueryExecutionError(f"Failed to get scenario analytics: {e}")
    
    async def _execute_scenario_analytics(self, connection: DatabricksOAuthClient,
                                        days_back: int, scenario_types: Optional[List[ScenarioType]],
                                        limit: Optional[int], offset: int) -> ScenarioAnalyticsResult:
        """Execute scenario analytics query."""
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        
        scenario_filter = ""
        if scenario_types:
            scenario_list = "', '".join([s.value for s in scenario_types])
            scenario_filter = f"AND scenario_type IN ('{scenario_list}')"
        
        # Add pagination clauses
        pagination_clause = ""
        if limit is not None:
            pagination_clause = f"LIMIT {limit}"
            if offset > 0:
                pagination_clause += f" OFFSET {offset}"
        elif offset > 0:
            # If only offset is provided, use a large limit
            pagination_clause = f"LIMIT 10000 OFFSET {offset}"
        
        query = f"""
        SELECT 
            COUNT(*) as total_processed,
            AVG(CASE WHEN process_success THEN 1.0 ELSE 0.0 END) as success_rate,
            scenario_type,
            COUNT(*) as scenario_count,
            expert_assigned,
            AVG(processing_duration_ms) as avg_processing_time,
            PERCENTILE(processing_duration_ms, 0.5) as median_processing_time,
            PERCENTILE(processing_duration_ms, 0.95) as p95_processing_time
        FROM {self._table_name}
        WHERE processed_at >= '{cutoff_date}'
        {scenario_filter}
        GROUP BY scenario_type, expert_assigned
        ORDER BY scenario_count DESC
        {pagination_clause}
        """
        
        result = await connection.execute_sql_fetchall(query)
        
        total_processed = sum(row.get('scenario_count', 0) for row in result)
        success_rate = sum(row.get('success_rate', 0) * row.get('scenario_count', 0) for row in result) / total_processed if total_processed > 0 else 0
        
        scenario_breakdown = {}
        expert_assignments = {}
        
        for row in result:
            scenario_type = row.get('scenario_type', 'unknown')
            scenario_count = row.get('scenario_count', 0)
            expert = row.get('expert_assigned')
            
            if scenario_type not in scenario_breakdown:
                scenario_breakdown[scenario_type] = 0
            scenario_breakdown[scenario_type] += scenario_count
            
            if expert:
                if expert not in expert_assignments:
                    expert_assignments[expert] = 0
                expert_assignments[expert] += scenario_count
        
        processing_time_stats = {
            "average_ms": sum(row.get('avg_processing_time', 0) * row.get('scenario_count', 0) for row in result) / total_processed if total_processed > 0 else 0,
            "median_ms": sum(row.get('median_processing_time', 0) * row.get('scenario_count', 0) for row in result) / total_processed if total_processed > 0 else 0,
            "p95_ms": max(row.get('p95_processing_time', 0) for row in result) if result else 0
        }
        
        return ScenarioAnalyticsResult(
            total_processed=total_processed,
            success_rate=success_rate * 100,
            scenario_breakdown=scenario_breakdown,
            expert_assignments=expert_assignments,
            processing_time_stats=processing_time_stats,
            time_period=f"last_{days_back}_days"
        )
    
    async def get_customer_interaction_history(
        self,
        customer_email: str,
        days_back: int = 90,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> CustomerInteractionHistory:
        """Get customer interaction history.
        
        Args:
            customer_email: Customer email address
            days_back: Number of days to look back
            limit: Maximum number of interactions to return (None for unlimited)
            offset: Number of interactions to skip for pagination
            
        Returns:
            CustomerInteractionHistory with customer data
        """
        start_time = time.time()
        
        try:
            await self._ensure_table_name()
            
            result = await self.execute_with_connection(
                self._execute_customer_history,
                customer_email.lower(),
                days_back,
                limit,
                offset
            )
            
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("get_customer_history", duration_ms, success=True)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("get_customer_history", duration_ms, 
                                         success=False, error_type=type(e).__name__)
            raise QueryExecutionError(f"Failed to get customer history: {e}")
    
    async def _execute_customer_history(self, connection: DatabricksOAuthClient,
                                      customer_email: str, days_back: int,
                                      limit: Optional[int], offset: int) -> CustomerInteractionHistory:
        """Execute customer history query."""
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        
        # Add pagination clauses
        pagination_clause = ""
        if limit is not None:
            pagination_clause = f"LIMIT {limit}"
            if offset > 0:
                pagination_clause += f" OFFSET {offset}"
        elif offset > 0:
            # If only offset is provided, use a large limit
            pagination_clause = f"LIMIT 10000 OFFSET {offset}"
        
        query = f"""
        SELECT 
            processing_id,
            email_id,
            scenario_type,
            processed_at,
            process_success,
            subject,
            agent_actions_log,
            expert_assigned
        FROM {self._table_name}
        WHERE LOWER(sender_email) = '{customer_email}'
        AND processed_at >= '{cutoff_date}'
        ORDER BY processed_at DESC
        {pagination_clause}
        """
        
        rows = await connection.execute_sql_fetchall(query)
        
        if not rows:
            return CustomerInteractionHistory(
                customer_email=customer_email,
                total_interactions=0,
                scenario_types=[],
                last_interaction=datetime.now(timezone.utc),
                success_rate=0.0,
                interactions=[]
            )
        
        total_interactions = len(rows)
        scenario_types = list(set(row.get('scenario_type', 'unknown') for row in rows))
        last_interaction = datetime.fromisoformat(rows[0]['processed_at'].replace('Z', '+00:00')) if rows[0].get('processed_at') else datetime.now(timezone.utc)
        
        successful = sum(1 for row in rows if row.get('process_success'))
        success_rate = (successful / total_interactions * 100) if total_interactions > 0 else 0
        
        interactions = []
        for row in rows:
            interactions.append({
                "process_id": row.get('processing_id'),
                "email_id": row.get('email_id'),
                "scenario_type": row.get('scenario_type'),
                "timestamp": row.get('processed_at'),
                "success": row.get('process_success'),
                "subject": row.get('subject'),
                "agent_actions_log": row.get('agent_actions_log', []),
                "expert_assigned": row.get('expert_assigned')
            })
        
        return CustomerInteractionHistory(
            customer_email=customer_email,
            total_interactions=total_interactions,
            scenario_types=scenario_types,
            last_interaction=last_interaction,
            success_rate=success_rate,
            interactions=interactions
        )
    
    async def get_expert_workload_stats(
        self, 
        expert_email: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[ExpertWorkloadStats]:
        """Get expert workload statistics.
        
        Args:
            expert_email: Specific expert email (optional)
            limit: Maximum number of experts to return (None for unlimited)
            offset: Number of experts to skip for pagination
            
        Returns:
            List of ExpertWorkloadStats
        """
        start_time = time.time()
        
        try:
            await self._ensure_table_name()
            
            result = await self.execute_with_connection(
                self._execute_expert_stats,
                expert_email,
                limit,
                offset
            )
            
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("get_expert_stats", duration_ms, success=True)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            await record_operation_metric("get_expert_stats", duration_ms, 
                                         success=False, error_type=type(e).__name__)
            raise QueryExecutionError(f"Failed to get expert stats: {e}")
    
    async def _execute_expert_stats(self, connection: DatabricksOAuthClient,
                                   expert_email: Optional[str],
                                   limit: Optional[int], offset: int) -> List[ExpertWorkloadStats]:
        """Execute expert statistics query."""
        expert_filter = ""
        if expert_email:
            expert_filter = f"AND LOWER(expert_email) = '{expert_email.lower()}'"
        
        # Add pagination clauses
        pagination_clause = ""
        if limit is not None:
            pagination_clause = f"LIMIT {limit}"
            if offset > 0:
                pagination_clause += f" OFFSET {offset}"
        elif offset > 0:
            # If only offset is provided, use a large limit
            pagination_clause = f"LIMIT 10000 OFFSET {offset}"
        
        query = f"""
        SELECT 
            expert_assigned,
            expert_email,
            COUNT(*) as total_assignments,
            COUNT(CASE WHEN process_success THEN 1 END) as successful_assignments,
            AVG(processing_duration_ms) as avg_processing_time,
            MAX(processed_at) as last_assignment
        FROM {self._table_name}
        WHERE expert_assigned IS NOT NULL 
        AND expert_email IS NOT NULL
        {expert_filter}
        GROUP BY expert_assigned, expert_email
        ORDER BY total_assignments DESC
        {pagination_clause}
        """
        
        rows = await connection.execute_sql_fetchall(query)
        
        results = []
        for row in rows:
            total_assignments = row.get('total_assignments', 0)
            successful_assignments = row.get('successful_assignments', 0)
            success_rate = (successful_assignments / total_assignments * 100) if total_assignments > 0 else 0
            
            last_assignment = None
            if row.get('last_assignment'):
                try:
                    last_assignment = datetime.fromisoformat(row['last_assignment'].replace('Z', '+00:00'))
                except:
                    last_assignment = None
            
            results.append(ExpertWorkloadStats(
                expert_name=row.get('expert_assigned', ''),
                expert_email=row.get('expert_email', ''),
                total_assignments=total_assignments,
                active_assignments=0,  # Would need additional query for active assignments
                success_rate=success_rate,
                average_processing_time=row.get('avg_processing_time', 0.0),
                last_assignment=last_assignment
            ))
        
        return results
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check of the service.
        
        Returns:
            Dictionary with health check results
        """
        health_result = {
            "service_name": "scenario_tracking_client",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {},
            "metrics": {},
            "circuit_breaker": {
                "failures": self._circuit_breaker_failures,
                "is_open": self._is_circuit_breaker_open()
            }
        }
        
        # Check database connectivity
        try:
            start_time = time.time()
            await self._ensure_table_name()
            
            # Simple connectivity test
            result = await self.execute_with_connection(self._execute_health_query)
            connectivity_time = (time.time() - start_time) * 1000
            
            health_result["checks"]["database_connectivity"] = {
                "status": "healthy" if result else "unhealthy",
                "response_time_ms": connectivity_time,
                "table_name": self._table_name
            }
            
        except Exception as e:
            health_result["checks"]["database_connectivity"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            health_result["status"] = "unhealthy"
        
        # Check async batch queue status
        queue_size = len(self._batch_insert_queue)
        health_result["checks"]["batch_queue"] = {
            "status": "healthy" if queue_size < self.config.batch_insert_size * 2 else "warning",
            "queue_size": queue_size,
            "max_size": self.config.batch_insert_size * 2
        }
        
        # Include service metrics
        health_result["metrics"] = self.metrics.get_summary_metrics()
        
        # Check for performance alerts
        alerts = self.metrics.get_performance_alerts()
        if alerts:
            health_result["alerts"] = alerts
            if any(alert["severity"] == "high" for alert in alerts):
                health_result["status"] = "degraded"
        
        return health_result
    
    async def _execute_health_query(self, connection: DatabricksOAuthClient) -> bool:
        """Execute simple health check query."""
        try:
            result = await connection.execute_sql_fetchone("SELECT 1 as health_check")
            return result is not None and result.get("health_check") == 1
        except Exception:
            return False
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get service performance metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        return self.metrics.get_summary_metrics()
    
    async def close(self):
        """Close the service and cleanup resources."""
        # Cancel background batch processing task
        if self._background_batch_task:
            self._background_batch_task.cancel()
            try:
                await self._background_batch_task
            except asyncio.CancelledError:
                pass
        
        # Flush any pending inserts
        if self._batch_insert_queue:
            try:
                await self.flush_pending_inserts()
                self.logger.info(
                    "Flushed pending inserts during shutdown",
                    extra={"count": len(self._batch_insert_queue)}
                )
            except Exception as e:
                self.logger.error("Failed to flush pending inserts", extra={"error": str(e)})
        
        # Close parent resources if method exists
        if hasattr(super(), 'close'):
            await super().close()
        
        self.logger.info("Scenario tracking client closed successfully")