#!/usr/bin/env python3
"""
Environment Configuration Validator for Email Agent
===================================================

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
    CRITICAL = "critical"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


@dataclass
class EnvVariable:
    """Environment variable definition."""
    name: str
    level: ValidationLevel
    description: str
    validator: Optional[callable] = None
    default: Optional[str] = None


class EnvironmentValidator:
    """Validates environment configuration for Email Agent."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.hint = None  # Store validation hints
        
    def validate(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Validate all environment variables."""
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
        
        # Special validation for storage authentication
        self._validate_storage_auth()
        
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
    
    def _validate_storage_auth(self):
        """Validate Azure Storage authentication configuration."""
        conn_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
        sas_token = os.getenv("AZURE_STORAGE_SAS_TOKEN")
        
        if not conn_string and not (account_name and sas_token):
            self.errors.append(
                "Azure Storage: Either AZURE_STORAGE_CONNECTION_STRING OR both "
                "AZURE_STORAGE_ACCOUNT_NAME and AZURE_STORAGE_SAS_TOKEN must be provided. "
                "Example connection string: DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=key==;EndpointSuffix=core.windows.net"
            )
        elif conn_string and (account_name or sas_token):
            self.warnings.append(
                "Azure Storage: Both connection string and SAS token provided. "
                "Connection string will be used. Consider using only one authentication method."
            )
    
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
                "email-agent"
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
                "BLOB_CONTAINER_NAME",
                ValidationLevel.RECOMMENDED,
                "Azure Blob container name",
                lambda x: len(x) > 0,
                "lowtouch"
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
            
            # Key Vault Secret Names
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
                "KEY_VAULT_ACS_CONNECTION_STRING_SECRET",
                ValidationLevel.OPTIONAL,
                "ACS connection string secret name",
                lambda x: len(x) > 0,
                "azure-communication-connection-string"
            ),
            EnvVariable(
                "KEY_VAULT_ACS_SENDER_EMAIL_SECRET",
                ValidationLevel.OPTIONAL,
                "ACS sender email secret name",
                lambda x: len(x) > 0,
                "azure-communication-sender-email"
            ),
            
            # Processing Configuration
            EnvVariable(
                "PROCESSING_INTERVAL_MINUTES",
                ValidationLevel.OPTIONAL,
                "Processing interval in minutes",
                lambda x: self._validate_with_hint(x, x.isdigit() and int(x) > 0,
                    "Must be a positive number of minutes"),
                "5"
            ),
            EnvVariable(
                "MAX_RETRY_ATTEMPTS",
                ValidationLevel.OPTIONAL,
                "Maximum retry attempts",
                lambda x: self._validate_with_hint(x, x.isdigit() and 0 <= int(x) <= 10,
                    "Must be between 0 and 10"),
                "3"
            ),
            EnvVariable(
                "BATCH_SIZE",
                ValidationLevel.OPTIONAL,
                "Batch processing size",
                lambda x: self._validate_with_hint(x, x.isdigit() and 1 <= int(x) <= 100,
                    "Must be between 1 and 100"),
                "10"
            ),
            
            # Test Mode Configuration
            EnvVariable(
                "TEST_MODE",
                ValidationLevel.OPTIONAL,
                "Enable test mode",
                lambda x: x.lower() in ["true", "false"],
                "false"
            ),
            EnvVariable(
                "TEST_EMAIL_OVERRIDE",
                ValidationLevel.OPTIONAL,
                "Email override for test mode",
                lambda x: not x or ("@" in x and "." in x) if x else True,
                ""
            ),
            
            # Health Monitoring
            EnvVariable(
                "HEALTH_CHECK_PORT",
                ValidationLevel.OPTIONAL,
                "Health check endpoint port",
                lambda x: self._validate_with_hint(x, x.isdigit() and 1 <= int(x) <= 65535,
                    "Must be a port number between 1 and 65535"),
                "8081"
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
            
            # Connection Pool Configuration
            EnvVariable(
                "CONNECTION_POOL_MIN_CONNECTIONS",
                ValidationLevel.OPTIONAL,
                "Minimum connections in pool",
                lambda x: self._validate_with_hint(x, x.isdigit() and int(x) >= 1,
                    "Must be at least 1"),
                "2"
            ),
            EnvVariable(
                "CONNECTION_POOL_MAX_CONNECTIONS",
                ValidationLevel.OPTIONAL,
                "Maximum connections in pool",
                lambda x: self._validate_with_hint(x, x.isdigit() and int(x) >= 1,
                    "Must be at least 1"),
                "5"
            ),
            EnvVariable(
                "CONNECTION_POOL_TIMEOUT_SECONDS",
                ValidationLevel.OPTIONAL,
                "Connection timeout in seconds",
                lambda x: x.isdigit() and int(x) > 0,
                "30"
            ),
            EnvVariable(
                "CONNECTION_POOL_MAX_AGE_SECONDS",
                ValidationLevel.OPTIONAL,
                "Maximum connection age",
                lambda x: x.isdigit() and int(x) > 0,
                "3600"
            ),
            EnvVariable(
                "CONNECTION_POOL_IDLE_TIMEOUT_SECONDS",
                ValidationLevel.OPTIONAL,
                "Idle connection timeout",
                lambda x: x.isdigit() and int(x) > 0,
                "1800"
            ),
            EnvVariable(
                "CONNECTION_POOL_WARMUP_TIMEOUT_SECONDS",
                ValidationLevel.OPTIONAL,
                "Connection warmup timeout",
                lambda x: x.isdigit() and int(x) > 0,
                "60"
            ),
            EnvVariable(
                "CONNECTION_POOL_RETRY_ATTEMPTS",
                ValidationLevel.OPTIONAL,
                "Connection retry attempts",
                lambda x: x.isdigit() and 0 <= int(x) <= 10,
                "3"
            ),
            EnvVariable(
                "CONNECTION_POOL_RETRY_DELAY_SECONDS",
                ValidationLevel.OPTIONAL,
                "Connection retry delay",
                lambda x: self._validate_with_hint(x,
                    x.replace(".", "").isdigit() and float(x) >= 0,
                    "Must be a positive number (seconds)"),
                "1.0"
            ),
            
            # Azure Storage (validated separately in _validate_storage_auth)
            EnvVariable(
                "AZURE_STORAGE_CONNECTION_STRING",
                ValidationLevel.OPTIONAL,
                "Azure Storage connection string",
                lambda x: not x or "AccountName=" in x,
                ""
            ),
            EnvVariable(
                "AZURE_STORAGE_ACCOUNT_NAME",
                ValidationLevel.OPTIONAL,
                "Azure Storage account name",
                lambda x: not x or len(x) > 0,
                ""
            ),
            EnvVariable(
                "AZURE_STORAGE_SAS_TOKEN",
                ValidationLevel.OPTIONAL,
                "Azure Storage SAS token",
                lambda x: not x or x.startswith("?") or x.startswith("sv="),
                ""
            ),
        ]
    
    def print_report(self):
        """Print validation report to console."""
        is_valid, issues = self.validate()
        
        print("\n" + "="*60)
        print("EMAIL AGENT ENVIRONMENT VALIDATION REPORT")
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