"""
Custom exceptions for scenario tracking operations.
Provides specific error types for different failure modes.
"""

class ScenarioTrackingException(Exception):
    """Base exception for scenario tracking operations."""
    
    def __init__(self, message: str, error_code: str = None, context: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "SCENARIO_TRACKING_ERROR"
        self.context = context or {}

    def to_dict(self) -> dict:
        """Convert exception to dictionary for logging."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context
        }


class DatabaseConnectionError(ScenarioTrackingException):
    """Raised when database connection fails."""
    
    def __init__(self, message: str = "Database connection failed", **kwargs):
        super().__init__(message, error_code="DB_CONNECTION_ERROR", **kwargs)


class DataValidationError(ScenarioTrackingException):
    """Raised when data validation fails."""
    
    def __init__(self, message: str = "Data validation failed", field_errors: dict = None, **kwargs):
        super().__init__(message, error_code="DATA_VALIDATION_ERROR", **kwargs)
        self.field_errors = field_errors or {}
        self.context.update({"field_errors": self.field_errors})


class BatchProcessingError(ScenarioTrackingException):
    """Raised when batch processing fails."""
    
    def __init__(self, message: str = "Batch processing failed", failed_count: int = 0, 
                 total_count: int = 0, **kwargs):
        super().__init__(message, error_code="BATCH_PROCESSING_ERROR", **kwargs)
        self.failed_count = failed_count
        self.total_count = total_count
        self.context.update({
            "failed_count": failed_count,
            "total_count": total_count,
            "success_rate": (total_count - failed_count) / total_count if total_count > 0 else 0
        })


class TableInitializationError(ScenarioTrackingException):
    """Raised when table initialization fails."""
    
    def __init__(self, message: str = "Table initialization failed", table_name: str = None, **kwargs):
        super().__init__(message, error_code="TABLE_INIT_ERROR", **kwargs)
        self.table_name = table_name
        if table_name:
            self.context.update({"table_name": table_name})


class QueryExecutionError(ScenarioTrackingException):
    """Raised when query execution fails."""
    
    def __init__(self, message: str = "Query execution failed", query_type: str = None, 
                 execution_time_ms: int = None, **kwargs):
        super().__init__(message, error_code="QUERY_EXECUTION_ERROR", **kwargs)
        self.query_type = query_type
        self.execution_time_ms = execution_time_ms
        if query_type:
            self.context.update({"query_type": query_type})
        if execution_time_ms:
            self.context.update({"execution_time_ms": execution_time_ms})


class ServiceUnavailableError(ScenarioTrackingException):
    """Raised when service is temporarily unavailable."""
    
    def __init__(self, message: str = "Service temporarily unavailable", 
                 retry_after_seconds: int = None, **kwargs):
        super().__init__(message, error_code="SERVICE_UNAVAILABLE", **kwargs)
        self.retry_after_seconds = retry_after_seconds
        if retry_after_seconds:
            self.context.update({"retry_after_seconds": retry_after_seconds})