#!/usr/bin/env python3
"""
Environment Configuration Validator for Inbox Monitor
=====================================================

Validates that all required environment variables are set and have valid values.
"""

import os
import sys
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class ValidationLevel(Enum):
    """Validation severity levels."""
    CRITICAL = "critical"  # Must be set for service to function
    RECOMMENDED = "recommended"  # Should be set for production
    OPTIONAL = "optional"  # Nice to have, has defaults


@dataclass
class EnvVariable:
    """Environment variable definition."""
    name: str
    level: ValidationLevel
    description: str
    validator: Optional[callable] = None
    default: Optional[str] = None


class EnvironmentValidator:
    """Validates environment configuration for Inbox Monitor."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.hint = None  # Store validation hints
        
    def validate(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate all environment variables.
        
        Returns:
            Tuple of (is_valid, issues_dict)
        """
        variables = self._get_variable_definitions()
        
        for var in variables:
            value = os.getenv(var.name, var.default)
            self.hint = None  # Reset hint for each variable
            
            if var.level == ValidationLevel.CRITICAL and not value:
                self.errors.append(f"{var.name}: {var.description} (REQUIRED)")
            elif var.level == ValidationLevel.RECOMMENDED and not value:
                self.warnings.append(f"{var.name}: {var.description} (RECOMMENDED)")
            elif value and var.validator:
                try:
                    if not var.validator(value):
                        error_msg = f"{var.name}: Invalid value '{value}'"
                        if self.hint:
                            error_msg += f" - {self.hint}"
                        self.errors.append(error_msg)
                except Exception as e:
                    self.errors.append(f"{var.name}: Validation error - {str(e)}")
            
            if value:
                self.info.append(f"{var.name}: Set ✓")
        
        return len(self.errors) == 0, {
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info
        }
    
    def _validate_with_hint(self, value: str, is_valid: bool, hint: str) -> bool:
        """Validate with helpful hint on failure."""
        if not is_valid:
            self.hint = hint  # Store hint for error message
        return is_valid
    
    def _get_variable_definitions(self) -> List[EnvVariable]:
        """Get all environment variable definitions with comprehensive coverage."""
        return [
            # Critical variables
            EnvVariable(
                "AZURE_KEY_VAULT_URL",
                ValidationLevel.CRITICAL,
                "Azure Key Vault URL for secrets",
                lambda x: self._validate_with_hint(x, x.startswith("https://") and ".vault.azure.net" in x,
                    "Must be format: https://your-vault.vault.azure.net/")
            ),
            EnvVariable(
                "AZURE_TENANT_ID",
                ValidationLevel.CRITICAL,
                "Azure Tenant ID for authentication",
                lambda x: self._validate_with_hint(x, len(x) == 36 and "-" in x,
                    "Must be a valid UUID (e.g., 12345678-1234-1234-1234-123456789012)")
            ),
            EnvVariable(
                "AZURE_CLIENT_ID",
                ValidationLevel.CRITICAL,
                "Azure Client ID for service principal",
                lambda x: self._validate_with_hint(x, len(x) == 36 and "-" in x,
                    "Must be a valid UUID (e.g., 87654321-4321-4321-4321-210987654321)")
            ),
            EnvVariable(
                "AZURE_CLIENT_SECRET",
                ValidationLevel.CRITICAL,
                "Azure Client Secret for authentication",
                lambda x: self._validate_with_hint(x, len(x) >= 8,
                    "Must be at least 8 characters long for security")
            ),
            EnvVariable(
                "GRAPH_API_MONITORED_EMAIL",
                ValidationLevel.CRITICAL,
                "Email address to monitor",
                lambda x: self._validate_with_hint(x, "@" in x and "." in x,
                    "Must be a valid email address (e.g., inbox@example.com)")
            ),
            EnvVariable(
                "DATABRICKS_SERVER_HOSTNAME",
                ValidationLevel.CRITICAL,
                "Databricks server hostname",
                lambda x: self._validate_with_hint(x, ".azuredatabricks.net" in x,
                    "Must be format: adb-xxxxx.azuredatabricks.net")
            ),
            EnvVariable(
                "DATABRICKS_HTTP_PATH",
                ValidationLevel.CRITICAL,
                "Databricks HTTP path",
                lambda x: self._validate_with_hint(x, x.startswith("/sql/"),
                    "Must start with /sql/ (e.g., /sql/1.0/warehouses/xxxxx)")
            ),
            
            # Recommended variables
            EnvVariable(
                "SERVICE_NAME",
                ValidationLevel.RECOMMENDED,
                "Service identification name",
                lambda x: len(x) > 0,
                "inbox-monitor"
            ),
            EnvVariable(
                "ENVIRONMENT",
                ValidationLevel.RECOMMENDED,
                "Deployment environment",
                lambda x: self._validate_with_hint(x, x in ["development", "staging", "production"],
                    "Must be one of: development, staging, production"),
                "development"
            ),
            EnvVariable(
                "DATABRICKS_CATALOG",
                ValidationLevel.RECOMMENDED,
                "Databricks catalog name",
                lambda x: len(x) > 0
            ),
            EnvVariable(
                "DATABRICKS_SCHEMA",
                ValidationLevel.RECOMMENDED,
                "Databricks schema name",
                lambda x: len(x) > 0
            ),
            EnvVariable(
                "DATABRICKS_TABLE_SUFFIX",
                ValidationLevel.OPTIONAL,
                "Table suffix for environments",
                None,
                ""
            ),
            EnvVariable(
                "LOG_LEVEL",
                ValidationLevel.RECOMMENDED,
                "Logging level",
                lambda x: self._validate_with_hint(x, x in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                    "Must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL"),
                "INFO"
            ),
            EnvVariable(
                "LOG_FORMAT",
                ValidationLevel.OPTIONAL,
                "Logging format",
                lambda x: x in ["json", "standard"],
                "json"
            ),
            EnvVariable(
                "INBOX_MONITOR_TEST_EMAIL",
                ValidationLevel.RECOMMENDED,
                "Test email for scenarios",
                lambda x: "@" in x and "." in x
            ),
            EnvVariable(
                "SCENARIO_VICTORIA_GRANT_EMAIL",
                ValidationLevel.RECOMMENDED,
                "Victoria Grant email for scenarios",
                lambda x: "@" in x and "." in x
            ),
            EnvVariable(
                "SCENARIO_ACCOUNT_TEAM_EMAIL",
                ValidationLevel.RECOMMENDED,
                "Account team email for scenarios",
                lambda x: "@" in x and "." in x
            ),
            
            # Key Vault Secret Names (All Recommended for production)
            EnvVariable(
                "KEY_VAULT_TENANT_ID_SECRET",
                ValidationLevel.RECOMMENDED,
                "Key Vault secret name for tenant ID",
                lambda x: len(x) > 0,
                "sales-engagement-service-principal-tenantid"
            ),
            EnvVariable(
                "KEY_VAULT_CLIENT_ID_SECRET",
                ValidationLevel.RECOMMENDED,
                "Key Vault secret name for client ID",
                lambda x: len(x) > 0,
                "sales-engagement-service-principal-clientid"
            ),
            EnvVariable(
                "KEY_VAULT_CLIENT_SECRET_SECRET",
                ValidationLevel.RECOMMENDED,
                "Key Vault secret name for client secret",
                lambda x: len(x) > 0,
                "sales-engagement-service-principal-secretid"
            ),
            EnvVariable(
                "KEY_VAULT_GRAPH_API_TENANT_ID_SECRET",
                ValidationLevel.OPTIONAL,
                "Graph API tenant ID secret name",
                lambda x: len(x) > 0,
                "graph-api-tenant-id"
            ),
            EnvVariable(
                "KEY_VAULT_GRAPH_API_CLIENT_ID_SECRET",
                ValidationLevel.OPTIONAL,
                "Graph API client ID secret name",
                lambda x: len(x) > 0,
                "graph-api-client-id"
            ),
            EnvVariable(
                "KEY_VAULT_GRAPH_API_CLIENT_SECRET_SECRET",
                ValidationLevel.OPTIONAL,
                "Graph API client secret name",
                lambda x: len(x) > 0,
                "graph-api-client-secret"
            ),
            EnvVariable(
                "KEY_VAULT_AZURE_AI_FOUNDRY_ENDPOINT_SECRET",
                ValidationLevel.OPTIONAL,
                "AI Foundry endpoint secret name",
                lambda x: len(x) > 0,
                "azure-ai-foundry-endpoint"
            ),
            EnvVariable(
                "KEY_VAULT_AZURE_AI_FOUNDRY_TENANT_ID_SECRET",
                ValidationLevel.OPTIONAL,
                "AI Foundry tenant ID secret name",
                lambda x: len(x) > 0,
                "azure-ai-foundry-tenant-id"
            ),
            EnvVariable(
                "KEY_VAULT_AZURE_AI_FOUNDRY_CLIENT_ID_SECRET",
                ValidationLevel.OPTIONAL,
                "AI Foundry client ID secret name",
                lambda x: len(x) > 0,
                "azure-ai-foundry-client-id"
            ),
            EnvVariable(
                "KEY_VAULT_AZURE_AI_FOUNDRY_CLIENT_SECRET_SECRET",
                ValidationLevel.OPTIONAL,
                "AI Foundry client secret name",
                lambda x: len(x) > 0,
                "azure-ai-foundry-client-secret"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_BASE_URL_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce base URL secret name",
                lambda x: len(x) > 0,
                "sf-base-url"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_CLIENT_ID_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce client ID secret name",
                lambda x: len(x) > 0,
                "sf-client-id"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_CLIENT_SECRET_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce client secret name",
                lambda x: len(x) > 0,
                "sf-client-secret"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_TOKEN_ENDPOINT_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce token endpoint secret name",
                lambda x: len(x) > 0,
                "sf-token-endpoint"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_API_VERSION_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce API version secret name",
                lambda x: len(x) > 0,
                "sf-api-version"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_CASE_RECORD_TYPE_ID_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce case type ID secret name",
                lambda x: len(x) > 0,
                "sf-case-record-type-id"
            ),
            EnvVariable(
                "KEY_VAULT_SALESFORCE_CASE_QUEUE_SECRET",
                ValidationLevel.OPTIONAL,
                "Salesforce case queue secret name",
                lambda x: len(x) > 0,
                "sf-case-queue"
            ),
            
            # Test Mode Variables
            EnvVariable(
                "TEST_MODE",
                ValidationLevel.OPTIONAL,
                "Enable test mode",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
            EnvVariable(
                "TEST_MODE_EMAIL",
                ValidationLevel.OPTIONAL,
                "Enable email test mode",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
            EnvVariable(
                "TEST_EMAIL_SENDER",
                ValidationLevel.OPTIONAL,
                "Test sender email address",
                lambda x: not x or ("@" in x and "." in x),
                ""
            ),
            EnvVariable(
                "TEST_SALESFORCE_EMAIL",
                ValidationLevel.OPTIONAL,
                "Test Salesforce email",
                lambda x: not x or ("@" in x and "." in x),
                ""
            ),
            EnvVariable(
                "TEST_FORCE_SCENARIO",
                ValidationLevel.OPTIONAL,
                "Force specific scenario",
                lambda x: not x or (x.isdigit() and int(x) in [5, 6, 7, 8, 9, 10, 11]),
                ""
            ),
            EnvVariable(
                "FORCE_SCENARIO_9",
                ValidationLevel.OPTIONAL,
                "Force scenario 9 (email invalid)",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
            
            # Processing Configuration
            EnvVariable(
                "INBOX_MONITOR_POLLING_INTERVAL",
                ValidationLevel.OPTIONAL,
                "Polling interval in seconds",
                lambda x: self._validate_with_hint(x, x.isdigit() and int(x) > 0,
                    "Must be a positive number of seconds"),
                "300"
            ),
            EnvVariable(
                "INBOX_MONITOR_BATCH_SIZE",
                ValidationLevel.OPTIONAL,
                "Batch processing size",
                lambda x: self._validate_with_hint(x, x.isdigit() and 1 <= int(x) <= 100,
                    "Must be between 1 and 100"),
                "10"
            ),
            EnvVariable(
                "INBOX_MONITOR_MAX_RETRY_ATTEMPTS",
                ValidationLevel.OPTIONAL,
                "Maximum retry attempts",
                lambda x: x.isdigit() and 0 <= int(x) <= 10,
                "3"
            ),
            EnvVariable(
                "INBOX_MONITOR_RETRY_DELAY",
                ValidationLevel.OPTIONAL,
                "Retry delay in seconds",
                lambda x: x.isdigit() and int(x) >= 0,
                "30"
            ),
            EnvVariable(
                "INBOX_MONITOR_PROCESSED_FOLDER_PREFIX",
                ValidationLevel.OPTIONAL,
                "Processed folder prefix",
                lambda x: len(x) > 0,
                "Processed"
            ),
            EnvVariable(
                "INBOX_MONITOR_OUTPUT_TYPE",
                ValidationLevel.OPTIONAL,
                "Output storage type",
                lambda x: x in ["file", "blob", "api"],
                "file"
            ),
            EnvVariable(
                "INBOX_MONITOR_OUTPUT_DIR",
                ValidationLevel.OPTIONAL,
                "Output directory path",
                lambda x: len(x) > 0,
                "./output"
            ),
            EnvVariable(
                "INBOX_MONITOR_API_ENDPOINT",
                ValidationLevel.OPTIONAL,
                "API endpoint URL",
                lambda x: not x or x.startswith("http"),
                ""
            ),
            EnvVariable(
                "INBOX_MONITOR_API_KEY",
                ValidationLevel.OPTIONAL,
                "API authentication key",
                None,
                ""
            ),
            EnvVariable(
                "INBOX_MONITOR_DRY_RUN",
                ValidationLevel.OPTIONAL,
                "Run in dry-run mode",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
            
            # Health Monitoring
            EnvVariable(
                "HEALTH_CHECK_PORT",
                ValidationLevel.OPTIONAL,
                "Health check endpoint port",
                lambda x: self._validate_with_hint(x, x.isdigit() and 1 <= int(x) <= 65535,
                    "Must be a port number between 1 and 65535"),
                "8080"
            ),
            EnvVariable(
                "HEALTH_CHECK_ENABLED",
                ValidationLevel.OPTIONAL,
                "Enable health check endpoints",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "METRICS_COLLECTION_INTERVAL",
                ValidationLevel.OPTIONAL,
                "Metrics collection interval in seconds",
                lambda x: x.isdigit() and int(x) > 0,
                "60"
            ),
            EnvVariable(
                "CONNECTION_POOL_HEALTH_CHECK_INTERVAL",
                ValidationLevel.OPTIONAL,
                "Connection pool health check interval",
                lambda x: x.isdigit() and int(x) > 0,
                "30"
            ),
            EnvVariable(
                "OAUTH_HEALTH_CHECK_INTERVAL",
                ValidationLevel.OPTIONAL,
                "OAuth health check interval",
                lambda x: x.isdigit() and int(x) > 0,
                "120"
            ),
            
            # Content Formatting
            EnvVariable(
                "CONTENT_FORMAT",
                ValidationLevel.OPTIONAL,
                "Content formatting type",
                lambda x: self._validate_with_hint(x, x in ["raw", "clean_text", "structured"],
                    "Must be one of: raw, clean_text, structured"),
                "structured"
            ),
            EnvVariable(
                "CONTENT_MAX_DESCRIPTION_LENGTH",
                ValidationLevel.OPTIONAL,
                "Maximum description length",
                lambda x: x.isdigit() and int(x) > 0,
                "30000"
            ),
            EnvVariable(
                "CONTENT_PRESERVE_SIGNATURE",
                ValidationLevel.OPTIONAL,
                "Preserve email signatures",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "CONTENT_INCLUDE_METADATA",
                ValidationLevel.OPTIONAL,
                "Include metadata in content",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "CONTENT_TRUNCATE_HTML_FALLBACK",
                ValidationLevel.OPTIONAL,
                "Truncate HTML on fallback",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            
            # Prompt Management
            EnvVariable(
                "PROMPTS_BASE_PATH",
                ValidationLevel.OPTIONAL,
                "Base path for prompt files",
                lambda x: len(x) > 0,
                "prompts"
            ),
            EnvVariable(
                "PROMPT_CACHE_TTL_SECONDS",
                ValidationLevel.OPTIONAL,
                "Prompt cache TTL in seconds",
                lambda x: x.isdigit() and int(x) >= 0,
                "300"
            ),
            EnvVariable(
                "PROMPT_ENABLE_HOT_RELOAD",
                ValidationLevel.OPTIONAL,
                "Enable prompt hot reload",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
            EnvVariable(
                "PROMPT_SCHEMA_VALIDATION",
                ValidationLevel.OPTIONAL,
                "Enable prompt schema validation",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "PROMPT_MAX_CACHE_SIZE",
                ValidationLevel.OPTIONAL,
                "Maximum prompt cache size",
                lambda x: x.isdigit() and int(x) > 0,
                "100"
            ),
            EnvVariable(
                "PROMPT_PRELOAD_LIST",
                ValidationLevel.OPTIONAL,
                "Comma-separated list of prompts to preload",
                None,
                "email_classification,email_forwarding"
            ),
            EnvVariable(
                "PROMPT_PERFORMANCE_MONITORING",
                ValidationLevel.OPTIONAL,
                "Enable prompt performance monitoring",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "PROMPT_FALLBACK_ENABLED",
                ValidationLevel.OPTIONAL,
                "Enable prompt fallback",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            
            # Scenario Tracking
            EnvVariable(
                "SCENARIO_TRACKING_ENABLED",
                ValidationLevel.OPTIONAL,
                "Enable scenario tracking",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_TABLE_SUFFIX",
                ValidationLevel.OPTIONAL,
                "Scenario tracking table suffix",
                None,
                ""
            ),
            EnvVariable(
                "SCENARIO_TRACKING_BATCH_SIZE",
                ValidationLevel.OPTIONAL,
                "Scenario tracking batch size",
                lambda x: x.isdigit() and 1 <= int(x) <= 1000,
                "100"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_ASYNC_INSERT",
                ValidationLevel.OPTIONAL,
                "Enable async insert for tracking",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_RETRY_ATTEMPTS",
                ValidationLevel.OPTIONAL,
                "Tracking retry attempts",
                lambda x: x.isdigit() and 0 <= int(x) <= 10,
                "3"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_RETRY_DELAY",
                ValidationLevel.OPTIONAL,
                "Tracking retry delay",
                lambda x: self._validate_with_hint(x, 
                    x.replace(".", "").isdigit() and float(x) >= 0,
                    "Must be a positive number (seconds)"),
                "2.0"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_CONNECTION_TIMEOUT",
                ValidationLevel.OPTIONAL,
                "Tracking connection timeout",
                lambda x: x.isdigit() and int(x) > 0,
                "30"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_PERFORMANCE_MONITORING",
                ValidationLevel.OPTIONAL,
                "Enable tracking performance monitoring",
                lambda x: x.lower() in ["true", "false"],
                "true"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_SLOW_QUERY_THRESHOLD",
                ValidationLevel.OPTIONAL,
                "Slow query threshold in ms",
                lambda x: x.isdigit() and int(x) > 0,
                "5000"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_HEALTH_CHECK_INTERVAL",
                ValidationLevel.OPTIONAL,
                "Tracking health check interval",
                lambda x: x.isdigit() and int(x) > 0,
                "300"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_DATA_RETENTION_DAYS",
                ValidationLevel.OPTIONAL,
                "Data retention in days",
                lambda x: x.isdigit() and int(x) > 0,
                "365"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_ARCHIVE_AFTER_DAYS",
                ValidationLevel.OPTIONAL,
                "Archive after days",
                lambda x: x.isdigit() and int(x) > 0,
                "90"
            ),
            EnvVariable(
                "SCENARIO_TRACKING_CLEANUP_ENABLED",
                ValidationLevel.OPTIONAL,
                "Enable tracking cleanup",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
        ]
    
    def print_report(self):
        """Print validation report to console."""
        is_valid, issues = self.validate()
        
        print("\n" + "="*60)
        print("INBOX MONITOR ENVIRONMENT VALIDATION REPORT")
        print("="*60)
        
        if self.errors:
            print("\n❌ ERRORS (Must Fix):")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS (Should Fix):")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if self.info:
            print("\n✅ CONFIGURED:")
            configured_count = len(self.info)
            print(f"   {configured_count} variables properly configured")
        
        print("\n" + "="*60)
        if is_valid:
            print("✅ VALIDATION PASSED - Ready for deployment")
        else:
            print("❌ VALIDATION FAILED - Fix errors before deployment")
        print("="*60 + "\n")
        
        return is_valid


def main():
    """Run environment validation."""
    # Load .env file if it exists
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print(f"Loaded environment from: {env_file}")
        except ImportError:
            print("Note: python-dotenv not installed. Using system environment variables only.")
            print("To load .env files, install with: pip install python-dotenv")
    else:
        print(f"No .env file found at: {env_file}")
        print("Using system environment variables only")
    
    validator = EnvironmentValidator()
    is_valid = validator.print_report()
    
    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()