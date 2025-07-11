import logging
from typing import Optional, List, Dict, Any
import json
import re

from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.core.exceptions import AzureError

from config.settings import AzureStorageSettings
from database.models import BlobFileInfo, ResearchOutput

logger = logging.getLogger(__name__)

class BlobStorageService:
    """Service for interacting with Azure Blob Storage."""
    
    def __init__(self, settings: AzureStorageSettings):
        """Initialize blob storage service with settings."""
        self.settings = settings
        self.blob_service_client: Optional[BlobServiceClient] = None
        self.container_client: Optional[ContainerClient] = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize Azure Storage clients."""
        try:
            if self.settings.connection_string:
                # Method 1: Connection string authentication
                logger.info("Initializing Azure Blob Storage with connection string")
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.settings.connection_string
                )
                
            elif self.settings.account_name and self.settings.sas_token:
                # Method 2: SAS token authentication
                logger.info("Initializing Azure Blob Storage with SAS token")
                account_url = f"https://{self.settings.account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(
                    account_url=account_url,
                    credential=self.settings.sas_token
                )
                
            else:
                raise ValueError(
                    "Azure Storage authentication not configured. "
                    "Provide either connection_string OR account_name+sas_token"
                )
            
            # Initialize container client
            self.container_client = self.blob_service_client.get_container_client(
                self.settings.container_name
            )
            
            logger.info(f"Azure Blob Storage clients initialized for container: {self.settings.container_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Storage clients: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test the Azure Blob Storage connection."""
        try:
            if not self.container_client:
                logger.error("Blob storage client not initialized")
                return False
            
            # Try to get container properties
            properties = self.container_client.get_container_properties()
            logger.info(f"Blob storage connection test passed for container: {properties.name}")
            return True
            
        except Exception as e:
            logger.error(f"Blob storage connection test failed: {e}")
            return False
    
    def find_email_files(self, date_folder: str, customer_id: str) -> Dict[str, Optional[BlobFileInfo]]:
        """Find email files for a specific customer in a date folder."""
        try:
            # Construct the expected path pattern
            # Expected structure: {date_folder}/{customer_id}/communication_output/
            communication_output_prefix = f"{date_folder}/{customer_id}/communication_output/"
            
            logger.info(f"Searching for email files in: {communication_output_prefix}")
            
            # List blobs with the prefix
            blobs = self.container_client.list_blobs(name_starts_with=communication_output_prefix)
            
            json_file = None
            html_file = None
            
            for blob in blobs:
                blob_name = blob.name
                logger.debug(f"Found blob: {blob_name}")
                
                # Check if this is the research output JSON file
                if blob_name.endswith('_research_output.json'):
                    json_file = BlobFileInfo(
                        container_name=self.settings.container_name,
                        blob_name=blob_name,
                        full_path=self._construct_blob_url(blob_name),
                        date_folder=date_folder,
                        customer_id=customer_id,
                        file_type='json'
                    )
                    logger.info(f"Found research output JSON: {blob_name}")
                
                # Check if this is the email HTML file
                elif blob_name.endswith('_email.html'):
                    html_file = BlobFileInfo(
                        container_name=self.settings.container_name,
                        blob_name=blob_name,
                        full_path=self._construct_blob_url(blob_name),
                        date_folder=date_folder,
                        customer_id=customer_id,
                        file_type='html'
                    )
                    logger.info(f"Found email HTML: {blob_name}")
            
            return {
                'json': json_file,
                'html': html_file
            }
            
        except Exception as e:
            logger.error(f"Error finding email files for customer {customer_id} in {date_folder}: {e}")
            return {'json': None, 'html': None}
    
    def _construct_blob_url(self, blob_name: str) -> str:
        """Construct blob URL based on authentication method."""
        try:
            if self.settings.connection_string:
                # For connection string auth, use account name from client
                account_name = self.blob_service_client.account_name
                return f"https://{account_name}.blob.core.windows.net/{self.settings.container_name}/{blob_name}"
            elif self.settings.account_name:
                # For SAS token auth, construct URL with SAS parameters
                base_url = f"https://{self.settings.account_name}.blob.core.windows.net/{self.settings.container_name}/{blob_name}"
                if self.settings.sas_token:
                    # Add SAS token (remove leading ? if present since we're adding it)
                    sas_token = self.settings.sas_token.lstrip('?')
                    return f"{base_url}?{sas_token}"
                return base_url
            else:
                # Fallback
                return f"https://unknown.blob.core.windows.net/{self.settings.container_name}/{blob_name}"
        except Exception as e:
            logger.error(f"Error constructing blob URL for {blob_name}: {e}")
            return f"https://unknown.blob.core.windows.net/{self.settings.container_name}/{blob_name}"
    
    def download_blob_content(self, blob_name: str) -> Optional[str]:
        """Download blob content as string."""
        try:
            if not self.container_client:
                raise RuntimeError("Blob storage client not initialized")
            
            blob_client = self.container_client.get_blob_client(blob_name)
            
            # Download blob content
            download_stream = blob_client.download_blob()
            content = download_stream.readall().decode('utf-8')
            
            logger.debug(f"Downloaded blob content: {blob_name} ({len(content)} chars)")
            return content
            
        except AzureError as e:
            logger.error(f"Azure error downloading blob {blob_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error downloading blob {blob_name}: {e}")
            return None
    
    def load_research_output(self, blob_name: str) -> Optional[ResearchOutput]:
        """Load and parse research output JSON from blob storage."""
        try:
            # Download the JSON content
            json_content = self.download_blob_content(blob_name)
            if not json_content:
                logger.error(f"Failed to download research output: {blob_name}")
                return None
            
            # Parse JSON
            data = json.loads(json_content)
            
            # Convert to ResearchOutput object
            research_output = ResearchOutput.from_dict(data)
            
            logger.info(f"Successfully loaded research output for customer: {research_output.customer_id}")
            return research_output
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in research output {blob_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading research output {blob_name}: {e}")
            return None
    
    def load_email_html(self, blob_name: str) -> Optional[str]:
        """Load email HTML content from blob storage."""
        try:
            # Download the HTML content
            html_content = self.download_blob_content(blob_name)
            if not html_content:
                logger.error(f"Failed to download email HTML: {blob_name}")
                return None
            
            # Clean up the HTML content
            cleaned_html = self._clean_html_content(html_content)
            
            logger.info(f"Successfully loaded email HTML: {blob_name}")
            return cleaned_html
            
        except Exception as e:
            logger.error(f"Error loading email HTML {blob_name}: {e}")
            return None
    
    def _clean_html_content(self, html_content: str) -> str:
        """Clean and process HTML content for email sending."""
        try:
            # Remove YAML frontmatter if present (like in the example file)
            if html_content.startswith('---'):
                parts = html_content.split('---', 2)
                if len(parts) >= 3:
                    html_content = parts[1].strip()  # Take the content between the --- markers
            
            # If the content is just a body fragment, wrap it in a complete HTML document
            if not html_content.strip().startswith('<!DOCTYPE') and not html_content.strip().startswith('<html'):
                # Extract subject from the body if present
                subject_match = re.search(r'<p><strong>Subject:</strong>\s*(.*?)</p>', html_content, re.IGNORECASE)
                if subject_match:
                    # Remove the subject paragraph from the body
                    html_content = re.sub(r'<p><strong>Subject:</strong>.*?</p>\s*', '', html_content, flags=re.IGNORECASE)
                
                # Wrap in complete HTML document
                html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #ffffff;
        }}
        p {{
            margin: 15px 0;
            line-height: 1.6;
        }}
        ul {{
            margin: 15px 0;
            padding-left: 20px;
        }}
        li {{
            margin: 8px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: underline;
        }}
        a:hover {{
            color: #004499;
        }}
        hr {{
            border: none;
            border-top: 1px solid #ddd;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
{html_content.strip()}
</body>
</html>"""
            
            return html_content.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning HTML content: {e}")
            return html_content
    
    def list_date_folders(self, limit: int = 100) -> List[str]:
        """List available date folders in the blob container."""
        try:
            if not self.container_client:
                raise RuntimeError("Blob storage client not initialized")
            
            # List blobs and extract unique date folder names
            blobs = self.container_client.list_blobs(name_starts_with="", delimiter="/")
            
            date_folders = []
            for blob in blobs:
                # Blob names should start with date folders like "20200707/"
                if hasattr(blob, 'name') and '/' in blob.name:
                    folder_name = blob.name.split('/')[0]
                    # Validate that it looks like a date folder (8 digits)
                    if folder_name.isdigit() and len(folder_name) == 8:
                        if folder_name not in date_folders:
                            date_folders.append(folder_name)
                            if len(date_folders) >= limit:
                                break
            
            date_folders.sort(reverse=True)  # Most recent first
            logger.info(f"Found {len(date_folders)} date folders")
            return date_folders
            
        except Exception as e:
            logger.error(f"Error listing date folders: {e}")
            return []
    
    def list_customer_folders(self, date_folder: str, limit: int = 1000) -> List[str]:
        """List customer folders within a specific date folder."""
        try:
            if not self.container_client:
                raise RuntimeError("Blob storage client not initialized")
            
            # List blobs with the date folder prefix
            prefix = f"{date_folder}/"
            blobs = self.container_client.list_blobs(name_starts_with=prefix)
            
            customer_ids = set()
            for blob in blobs:
                blob_name = blob.name
                # Extract customer ID from path like "20200707/10016125/communication_output/..."
                path_parts = blob_name.split('/')
                if len(path_parts) >= 3 and path_parts[0] == date_folder:
                    customer_id = path_parts[1]
                    if customer_id.isdigit():  # Validate customer ID format
                        customer_ids.add(customer_id)
                        if len(customer_ids) >= limit:
                            break
            
            customer_list = sorted(list(customer_ids))
            logger.info(f"Found {len(customer_list)} customer folders in {date_folder}")
            return customer_list
            
        except Exception as e:
            logger.error(f"Error listing customer folders in {date_folder}: {e}")
            return []