"""
Configuration module for communication agent.
Contains logging configuration and other settings.
"""
import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class LoggingConfig:
    """Handles logging configuration for the communication agent."""
    
    @staticmethod
    def configure_logging():
        """
        Configure root logger and suppress Azure SDK logs.
        IMPORTANT: Call this at the very top of your main script, before any Azure SDK imports.
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                # Uncomment below for file logging in production
                #logging.FileHandler("app.log", encoding="utf-8"),
            ]
        )
        # Suppress Azure SDK info/debug logs
        logging.getLogger("azure").setLevel(logging.WARNING)
        logging.getLogger("azure.identity").setLevel(logging.WARNING)
        # Suppress Azure SDK HTTP logs
        logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(logging.WARNING)
        logging.getLogger("azure.storage").setLevel(logging.WARNING)
        logging.getLogger("azure").setLevel(logging.WARNING)
class CommunicationConfig:
    """Configuration settings for the communication agent."""
    
    def __init__(self):
        self.account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
        self.input_folder_name = os.getenv("AZURE_STORAGE_INPUT_FOLDER_NAME", "")
        self.output_folder_name = os.getenv("AZURE_STORAGE_OUTPUT_FOLDER_NAME", "communication_output/")
        self.output_custom_folder = os.getenv("AZURE_STORAGE_OUTPUT_CUSTOM_FOLDER", "")
        self.output_overwrite = os.getenv("AZURE_STORAGE_OUTPUT_OVERWRITE", "False").lower() == "true"
        self.max_iterations = int(os.getenv("REVIEW_EMAIL_MAX_ITERATIONS", "2"))
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.queue_name = os.getenv("AZURE_EMAIL_INPUT_QUEUE")
        self.dead_letter_queue = os.getenv("AZURE_EMAIL_INPUT_DLQ", None)
        # Sender details configuration
        self.sender_details = """Sender details : 
        Victoria Grant
        Manager, Account Expert Team
        On behalf of the Staples Expert Team
        Staplesexpertteam@staples.com
        """
    
    @property
    def output_folder_prefix(self):
        """Get the output folder prefix based on configuration and current date."""
        from datetime import datetime
        if self.output_custom_folder:
            return self.output_custom_folder
        else:
            return datetime.now().strftime("%Y%m%d")

    def get_output_folder_prefix_from_run_date(self, run_date):
        """
        Get the output folder prefix using a run_date (str or date) from the data object.
        If output_custom_folder is set, use that. Otherwise, use run_date formatted as YYYYMMDD.
        """
        from datetime import datetime, date
        if self.output_custom_folder:
            return self.output_custom_folder
        if isinstance(run_date, str):
            try:
                dt = datetime.fromisoformat(run_date)
            except Exception:
                dt = datetime.now()
        elif isinstance(run_date, date):
            dt = run_date
        else:
            dt = datetime.now()
        return dt.strftime("%Y%m%d")
