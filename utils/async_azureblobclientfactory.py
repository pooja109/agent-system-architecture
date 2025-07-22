import os
import asyncio
from azure.storage.blob.aio import BlobServiceClient, ContainerClient, BlobClient
from azure.identity.aio import DefaultAzureCredential

class AsyncBlobClientFactory:
    _client_instance = None
    _lock = asyncio.Lock()

    @classmethod
    async def get_blob_service_client(cls) -> BlobServiceClient:
        if cls._client_instance is None:
            async with cls._lock:
                if cls._client_instance is None:
                    conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
                    if conn_str:
                        # Use connection string if available
                        cls._client_instance = BlobServiceClient.from_connection_string(conn_str)
                    else:
                        # Fall back to managed identity/default credentials
                        storage_account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
                        if not storage_account_url:
                            # Try to construct URL from account name if provided
                            storage_account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
                            if not storage_account_name:
                                raise ValueError(
                                    "Either AZURE_STORAGE_CONNECTION_STRING or AZURE_STORAGE_ACCOUNT_URL "
                                    "or AZURE_STORAGE_ACCOUNT_NAME environment variable must be set. "
                                    "For managed identity, provide the storage account URL or name."
                                )
                            storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
                        
                        credential = DefaultAzureCredential()
                        cls._client_instance = BlobServiceClient(
                            account_url=storage_account_url,
                            credential=credential
                        )
        return cls._client_instance

    @classmethod
    async def get_container_client(cls, container_name: str) -> ContainerClient:
        client = await cls.get_blob_service_client()
        return client.get_container_client(container_name)

    @classmethod
    async def get_blob_client(cls, container_name: str, blob_name: str) -> BlobClient:
        client = await cls.get_blob_service_client()
        return client.get_blob_client(container=container_name, blob=blob_name)