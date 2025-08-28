"""
Core Production Configuration (Phases 1-3)
==========================================

Configuration for the core scenario tracking system components.
This configuration is used by the Phase 6 deployment and testing infrastructure.
"""

import os
from typing import Dict, Any

# Core production configuration as specified in Phase 6 prompt
CORE_PRODUCTION_CONFIG: Dict[str, Any] = {
    "DATABRICKS_CONFIG": {
        "host": os.getenv("DATABRICKS_HOST"),
        "warehouse_id": os.getenv("DATABRICKS_WAREHOUSE_ID"),
        "oauth_client_id": os.getenv("DATABRICKS_OAUTH_CLIENT_ID"),
        "oauth_client_secret": os.getenv("DATABRICKS_OAUTH_CLIENT_SECRET"),
        "catalog": os.getenv("DATABRICKS_CATALOG", "inbox_monitor"),
        "schema": os.getenv("DATABRICKS_SCHEMA", "scenario_tracking"),
        "connection_pool": {
            "max_connections": int(os.getenv("DATABRICKS_MAX_CONNECTIONS", "8")),
            "connection_timeout": int(os.getenv("DATABRICKS_CONNECTION_TIMEOUT", "30")),
            "retry_attempts": int(os.getenv("DATABRICKS_RETRY_ATTEMPTS", "3"))
        }
    },
    
    "SCENARIO_TRACKING_CONFIG": {
        "enabled": os.getenv("SCENARIO_TRACKING_ENABLED", "true").lower() == "true",
        "table_suffix": os.getenv("SCENARIO_TRACKING_TABLE_SUFFIX", ""),
        "batch_insert_size": int(os.getenv("SCENARIO_TRACKING_BATCH_SIZE", "50")),
        "async_insert": os.getenv("SCENARIO_TRACKING_ASYNC", "true").lower() == "true",
        "retry_attempts": int(os.getenv("SCENARIO_TRACKING_RETRY_ATTEMPTS", "3")),
        "connection_timeout_seconds": int(os.getenv("SCENARIO_TRACKING_TIMEOUT", "30")),
        "performance_monitoring": os.getenv("SCENARIO_TRACKING_MONITORING", "true").lower() == "true"
    },
    
    "CORE_DEPLOYMENT": {
        "log_directory": os.getenv("SCENARIO_TRACKING_LOG_DIR", "/var/log/scenario_tracking"),
        "data_retention_days": int(os.getenv("SCENARIO_TRACKING_RETENTION_DAYS", "365")),
        "backup_enabled": os.getenv("SCENARIO_TRACKING_BACKUP", "true").lower() == "true"
    }
}

# Core database configuration for legacy compatibility
CORE_DATABASE_CONFIG = CORE_PRODUCTION_CONFIG["DATABRICKS_CONFIG"]

# Core scenario tracking configuration for legacy compatibility
CORE_SCENARIO_TRACKING_CONFIG = CORE_PRODUCTION_CONFIG["SCENARIO_TRACKING_CONFIG"]