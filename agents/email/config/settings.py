import os
from typing import Optional
from pydantic import BaseModel, Field, model_validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AzureCommunicationSettings(BaseModel):
    connection_string: str = Field(..., description="Azure Communication Services connection string")
    sender_email: str = Field(..., description="Sender email address")
    reply_to_email: str = Field(..., description="Reply-to email address")

class AzureStorageSettings(BaseModel):
    connection_string: Optional[str] = Field(None, description="Azure Storage connection string")
    account_name: Optional[str] = Field(None, description="Azure Storage account name (for SAS token auth)")
    sas_token: Optional[str] = Field(None, description="Azure Storage SAS token")
    container_name: str = Field(default="lowtouch", description="Blob container name")
    
    @model_validator(mode='after')
    def validate_authentication(self):
        """Validate that either connection_string or account_name+sas_token is provided."""
        if not self.connection_string and not (self.account_name and self.sas_token):
            raise ValueError(
                "Either connection_string OR both account_name and sas_token must be provided"
            )
        if self.connection_string and (self.account_name or self.sas_token):
            raise ValueError(
                "Cannot use both connection_string and SAS token authentication. Choose one method."
            )
        return self

class DatabricksSettings(BaseModel):
    server_hostname: str = Field(..., description="Databricks server hostname")
    http_path: str = Field(..., description="Databricks HTTP path")
    access_token: str = Field(..., description="Databricks access token")
    catalog: str = Field(..., description="Databricks catalog name")
    schema: str = Field(..., description="Databricks schema name")
    table_suffix: str = Field(default="", description="Table suffix for environments")

class ProcessingSettings(BaseModel):
    interval_minutes: int = Field(default=5, description="Processing interval in minutes")
    max_retry_attempts: int = Field(default=3, description="Maximum retry attempts for failed operations")
    batch_size: int = Field(default=10, description="Number of records to process in each batch")

class LoggingSettings(BaseModel):
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(default="json", description="Logging format")

class TestModeSettings(BaseModel):
    test_mode: bool = Field(default=False, description="Enable test mode to override email addresses")
    test_email_override: Optional[str] = Field(None, description="Email address to use in test mode")

class AppSettings(BaseModel):
    azure_communication: AzureCommunicationSettings
    azure_storage: AzureStorageSettings
    databricks: DatabricksSettings
    processing: ProcessingSettings
    logging: LoggingSettings
    test_mode: TestModeSettings
    environment: str = Field(default="development", description="Application environment")

def get_settings() -> AppSettings:
    """Get application settings from environment variables."""
    return AppSettings(
        azure_communication=AzureCommunicationSettings(
            connection_string=os.getenv("ACS_CONNECTION_STRING", ""),
            sender_email=os.getenv("ACS_SENDER_EMAIL", ""),
            reply_to_email=os.getenv("ACS_REPLY_TO_EMAIL", "")
        ),
        azure_storage=AzureStorageSettings(
            connection_string=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
            account_name=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
            sas_token=os.getenv("AZURE_STORAGE_SAS_TOKEN"),
            container_name=os.getenv("BLOB_CONTAINER_NAME", "lowtouch")
        ),
        databricks=DatabricksSettings(
            server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME", ""),
            http_path=os.getenv("DATABRICKS_HTTP_PATH", ""),
            access_token=os.getenv("DATABRICKS_ACCESS_TOKEN", ""),
            catalog=os.getenv("DATABRICKS_CATALOG", ""),
            schema=os.getenv("DATABRICKS_SCHEMA", ""),
            table_suffix=os.getenv("DATABRICKS_TABLE_SUFFIX", "")
        ),
        processing=ProcessingSettings(
            interval_minutes=int(os.getenv("PROCESSING_INTERVAL_MINUTES", "5")),
            max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            batch_size=int(os.getenv("BATCH_SIZE", "10"))
        ),
        logging=LoggingSettings(
            level=os.getenv("LOG_LEVEL", "INFO"),
            format=os.getenv("LOG_FORMAT", "json")
        ),
        test_mode=TestModeSettings(
            test_mode=os.getenv("TEST_MODE", "false").lower() == "true",
            test_email_override=os.getenv("TEST_EMAIL_OVERRIDE")
        ),
        environment=os.getenv("ENVIRONMENT", "development")
    )

def validate_settings(settings: AppSettings) -> bool:
    """Validate that all required settings are present."""
    missing_fields = []
    
    # Validate Azure Communication Services
    if not settings.azure_communication.connection_string:
        missing_fields.append("ACS_CONNECTION_STRING")
    if not settings.azure_communication.sender_email:
        missing_fields.append("ACS_SENDER_EMAIL")
    
    # Validate Azure Storage (either connection string OR account name + SAS token)
    if not settings.azure_storage.connection_string:
        if not settings.azure_storage.account_name:
            missing_fields.append("AZURE_STORAGE_ACCOUNT_NAME (required when not using connection string)")
        if not settings.azure_storage.sas_token:
            missing_fields.append("AZURE_STORAGE_SAS_TOKEN (required when not using connection string)")
    
    # Validate Databricks
    required_databricks = [
        (settings.databricks.server_hostname, "DATABRICKS_SERVER_HOSTNAME"),
        (settings.databricks.http_path, "DATABRICKS_HTTP_PATH"),
        (settings.databricks.access_token, "DATABRICKS_ACCESS_TOKEN"),
        (settings.databricks.catalog, "DATABRICKS_CATALOG"),
        (settings.databricks.schema, "DATABRICKS_SCHEMA")
    ]
    
    for field, name in required_databricks:
        if not field:
            missing_fields.append(name)
    
    # Validate test mode settings
    if settings.test_mode.test_mode and not settings.test_mode.test_email_override:
        missing_fields.append("TEST_EMAIL_OVERRIDE (required when TEST_MODE=true)")
    
    if missing_fields:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_fields)}")
    
    return True