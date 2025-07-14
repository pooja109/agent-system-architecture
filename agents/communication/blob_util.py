"""
Blob utility class for Azure Blob Storage operations.
"""
import json
import time
import logging
import sys
import os
from typing import Any
from azure.storage.blob.aio import BlobServiceClient
from azure.identity.aio import DefaultAzureCredential

# Add current directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

logger = logging.getLogger(__name__)

class BlobUtil:
    """Utility class for Azure Blob Storage operations."""
    
    def __init__(self, account_url: str, container_name: str):
        self.account_url = account_url
        self.container_name = container_name
        self.credential = DefaultAzureCredential()
        self.blob_service_client = BlobServiceClient(account_url=account_url, credential=self.credential)
        self.container_client = self.blob_service_client.get_container_client(container_name)
    
    async def save_string_to_blob(self, folder: str, blob_name: str, content: Any) -> None:
        """Save a string as a blob in Azure Blob Storage, under a specified folder, and log the time taken."""
        start_time = time.time()
        if folder and not folder.endswith("/"):
            folder = folder + "/"
        full_blob_name = f"{folder}{blob_name}" if folder else blob_name
        try:
            # Ensure content is a string before uploading
            if not isinstance(content, str):
                # If it's a Pydantic model, use .model_dump() to get a dict
                if hasattr(content, 'model_dump'):
                    content = json.dumps(content.model_dump(), ensure_ascii=False, indent=2)
                else:
                    content = json.dumps(content, ensure_ascii=False, indent=2)
            blob_client = self.container_client.get_blob_client(full_blob_name)
            await blob_client.upload_blob(content, overwrite=True)
            elapsed = time.time() - start_time
            logger.info("Saved content to blob: %s in %.3f seconds", full_blob_name, elapsed)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error("Failed to save to blob %s after %.3f seconds: %s", full_blob_name, elapsed, e)

    async def output_blob_exists(self, blob_name: str) -> bool:
        """Check if a blob exists in the container."""
        blob_client = self.container_client.get_blob_client(blob_name)
        try:
            await blob_client.get_blob_properties()
            return True
        except Exception:
            return False

    async def read_from_blob(self, blob_name: str) -> str:
        """Asynchronously read the content of a blob from Azure Blob Storage."""
        blob_client = self.container_client.get_blob_client(blob_name)
        stream = await blob_client.download_blob()
        file_content = await stream.readall()
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8")
        customer_research = file_content if file_content else ""
        return customer_research

    def list_blobs(self, name_starts_with: str = ""):
        """List blobs in the container with optional prefix filter."""
        return self.container_client.list_blobs(name_starts_with=name_starts_with)

    async def close(self):
        """Clean up resources to prevent unclosed client sessions."""
        try:
            await self.blob_service_client.close()
            await self.credential.close()
        except Exception as cleanup_error:
            logger.exception("Error during blob client cleanup: %s", cleanup_error)
