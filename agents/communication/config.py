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
        """Configure root logger and suppress Azure SDK logs."""
        # Configure root logger only once here
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

class CommunicationConfig:
    """Configuration settings for the communication agent."""
    
    def __init__(self):
        self.account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
        self.container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
        self.input_folder_name = os.getenv("AZURE_STORAGE_INPUT_FOLDER_NAME", "")
        self.output_folder_name = os.getenv("AZURE_STORAGE_OUTPUT_FOLDER_NAME", "communication_output/")
        self.output_custom_folder = os.getenv("AZURE_STORAGE_OUTPUT_CUSTOM_FOLDER", "")
        self.output_overwrite = os.getenv("AZURE_STORAGE_OUTPUT_OVERWRITE", "False").lower() == "true"
        self.max_iterations = 2
        
        # Sender details configuration
        self.sender_details = """Sender details : 
        Victoria Grant
        Manager, Account Expert Team
        On behalf of the Staples Expert Team
        Staplesexpertteam@staples.com
        """
    
    @property
    def output_folder_prefix(self):
        """Get the output folder prefix based on configuration."""
        from datetime import datetime
        if self.output_custom_folder:
            return self.output_custom_folder
        else:
            return datetime.now().strftime("%Y%m%d")
