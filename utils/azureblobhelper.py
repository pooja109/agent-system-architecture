import os
import json
import logging
# from azure.storage.queue import QueueClient
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AzureBlobHelper:
    def __init__(self, connection_string: str, container_name: str):
        self.connection_string = connection_string
        self.container_name = container_name
        self.blob_client = None
        self.container_client = None
        self.blob_service_client = None

        if connection_string and connection_string.strip() and container_name and container_name.strip():
            self.blob_client = BlobServiceClient.from_connection_string(connection_string)
            self.container_client = self.blob_client.get_container_client(container_name)
        else:
            account_url = "https://mld01storagene0.blob.core.windows.net/"             # Staples Subscription
            # account_url = "https://mssampledata.blob.core.windows.net/"                 # My Subscription
            credential = DefaultAzureCredential()
        
            print(f"🔗 Connecting to storage account: {account_url}")
            print(f"📁 Container: {container_name}")
            #print(f"📄 Reading file: {blob_name}")
            self.blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)

            logger.warning("AzureBlobHelper initialized without valid connection_string or container_name.")

    async def upload_blob(self, blob_name: str, data: bytes):
        try:
            await self.container_client.upload_blob(blob_name, data)
            logger.info(f"Uploaded blob: {blob_name}")
        except AzureError as e:
            logger.error(f"Error uploading blob: {e}")

    async def download_blob(self, blob_name: str) -> bytes:
        try:
            blob_data = await self.container_client.download_blob(blob_name)
            return await blob_data.readall()
        except AzureError as e:
            logger.error(f"Error downloading blob: {e}")
            return b""

    async def delete_blob(self, blob_name: str):
        try:
            await self.container_client.delete_blob(blob_name)
            logger.info(f"Deleted blob: {blob_name}")
        except AzureError as e:
            logger.error(f"Error deleting blob: {e}")
    
    def read_blob_file_content(self, blob_name: str, container_name: str = "lowtouch") -> str:
        """
        Reads the content of a specific file from Azure Blob Storage.
    
        Args:
            blob_name (str): The name of the blob file to read (e.g., "447797.md")
            container_name (str): The name of the container (default: "lowtouch")
        
        Returns:
            str: The content of the file as a string, or None if error occurs
        """
        try:
            # account_url = "https://mld01storagene0.blob.core.windows.net/"             # Staples Subscription
            # # account_url = "https://mssampledata.blob.core.windows.net/"                 # My Subscription
            # credential = DefaultAzureCredential()
        
            # print(f"🔗 Connecting to storage account: {account_url}")
            # print(f"📁 Container: {container_name}")
            # print(f"📄 Reading file: {blob_name}")
        
            # Create BlobServiceClient
            #blob_service_client = BlobServiceClient(account_url=account_url, credential=credential) # todo - use a singleton instantiation of BlobServiceClient
        
            # Get blob client directly
            blob_client = self.blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
            # Check if blob exists
            if not blob_client.exists():
                print(f"❌ File '{blob_name}' does not exist in container '{container_name}'")
                return None
        
            # Download and read the blob content
            print("📥 Downloading blob content...")
            blob_data = blob_client.download_blob().readall()
        
            # Decode the content to string
            content = blob_data.decode('utf-8')
        
            print(f"✅ Successfully read {len(content)} characters from '{blob_name}'")
            return content
        
        except Exception as e:
            print(f"❌ Error reading blob file '{blob_name}': {e}")
            return None

    def list_blobs_in_container(self, container_name: str = "lowtouch", prefix: str = "") -> list:
        """
        Lists all blobs in the specified container.
    
        Args:
            container_name (str): The name of the container (default: "lowtouch")
            prefix (str): Optional prefix to filter blobs (e.g., "bingsearch/")
        
        Returns:
            list: List of blob names, or empty list if error occurs
        """
        try:
            # account_url = "https://mld01storagene0.blob.core.windows.net/"             # Staples Subscription
            # #account_url = "https://mssampledata.blob.core.windows.net/"                 # My Subscription
            # credential = DefaultAzureCredential()
        
            # # Create BlobServiceClient
            # #blob_service_client = BlobServiceClient(account_url=account_url, credential=credential)
            # print(f"[DEBUG] Using container: {container_name}, type: {type(container_name)}")
            # Get container client
            container_client = self.blob_service_client.get_container_client("lowtouch") # todo - use container_name variable

            print(f"📁 Listing blobs in container '{container_name}'")
            if prefix:
                print(f"🔍 Filtering with prefix: '{prefix}'")
        
            # List blobs with optional prefix
            blob_list = container_client.list_blobs(name_starts_with="research_output/20250703/") #todo - use prefix variable
        
            blobs = []
            print("\n" + "="*60)
            print("BLOB STORAGE CONTENTS")
            print("="*60)
            blob_content = []
            for blob in blob_list:
                blobs.append(blob.name)
                print(f"📄 {blob.name}")
                print(f"   Size: {blob.size:,} bytes")
                print(f"   Last Modified: {blob.last_modified}")
                print()
                blob_content.append(self.read_blob_file_content(blob.name, "lowtouch")) # todo - use container_name variable")
        
            print(f"✅ Found {len(blobs)} blobs in container '{container_name}'")
            return blob_content
        
        except Exception as e:
            print(f"❌ Error listing blobs in container '{container_name}': {e}")
            return [] 