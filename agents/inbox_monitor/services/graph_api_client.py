"""
Microsoft Graph API Client
==========================

Client for interacting with Microsoft Graph API to manage emails.
Uses MSAL for authentication with client credentials flow.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Any

import httpx
import structlog
from msal import ConfidentialClientApplication

try:
    # Try absolute imports first (for direct script execution)
    from config.settings import GraphAPISettings
    from models.email import (
        Email,
        EmailAddress,
        EmailBody,
        EmailImportance,
        EmailRecipients,
        ProcessingMetadata,
    )

    from utils.retry import retry_with_backoff
except ImportError:
    # Fall back to relative imports (for module execution)
    from ..config.settings import GraphAPISettings
    from ..models.email import (
        Email,
        EmailAddress,
        EmailBody,
        EmailImportance,
        EmailRecipients,
        ProcessingMetadata,
    )
    from ..utils.retry import retry_with_backoff


class GraphAPIClient:
    """Client for Microsoft Graph API operations."""

    def __init__(self, settings: GraphAPISettings):
        """Initialize Graph API client.

        Args:
            settings: Graph API configuration settings
        """
        self.settings = settings
        self.logger = structlog.get_logger(__name__)

        # Initialize MSAL application
        self.msal_app = ConfidentialClientApplication(
            self.settings.client_id,
            authority=f"{self.settings.authority_url}/{self.settings.tenant_id}",
            client_credential=self.settings.client_secret,
        )

        self._token_cache: dict[str, Any] | None = None
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize the Graph API client."""
        # Configure HTTPX client with proper timeouts and connection limits
        timeout = httpx.Timeout(
            connect=10.0,  # Connection timeout
            read=10.0,  # Read timeout
            write=10.0,  # Write timeout
            pool=30.0,  # Pool timeout
        )

        # Configure connection limits
        limits = httpx.Limits(
            max_connections=5,  # Total connection pool size
            max_keepalive_connections=2,  # Keepalive connections
            keepalive_expiry=5.0,  # Keepalive expiry time
        )

        # Create HTTPX client with HTTP/2 support
        try:
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=True,  # Enable HTTP/2
                verify=False,  # Disable SSL verification if needed
                follow_redirects=True,
            )
        except ImportError:
            # Fallback to HTTP/1.1 if h2 package is not installed
            self._client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=False,  # Disable HTTP/2
                verify=False,  # Disable SSL verification if needed
                follow_redirects=True,
            )
        self.logger.info("Graph API client initialized")

    async def cleanup(self) -> None:
        """Cleanup resources."""
        if self._client:
            try:
                # HTTPX handles cleanup automatically and gracefully
                await self._client.aclose()

                # Small delay to ensure cleanup completes
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.warning("Error closing Graph API client", error=str(e))
            finally:
                self._client = None
        self.logger.info("Graph API client cleaned up")

    def _get_access_token(self) -> str:
        """Get access token using MSAL.

        Returns:
            Access token string

        Raises:
            Exception: If token acquisition fails
        """
        # Try to get token from cache
        if (
            self._token_cache
            and self._token_cache.get("expires_at", 0) > datetime.utcnow().timestamp()
        ):
            return self._token_cache["access_token"]

        # Acquire new token
        result = self.msal_app.acquire_token_for_client(scopes=self.settings.scopes)

        if "access_token" not in result:
            error_msg = result.get("error_description", "Unknown error acquiring token")
            self.logger.error("Failed to acquire token", error=error_msg)
            raise Exception(f"Failed to acquire token: {error_msg}")

        # Cache the token
        self._token_cache = {
            "access_token": result["access_token"],
            "expires_at": datetime.utcnow().timestamp() + result.get("expires_in", 3600),
        }

        self.logger.debug("Successfully acquired new access token")
        return result["access_token"]

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated request to Graph API.

        Args:
            method: HTTP method
            endpoint: API endpoint (relative to base URL)
            json_data: JSON body data
            params: Query parameters

        Returns:
            Response data as dictionary

        Raises:
            Exception: If request fails
        """
        if not self._client:
            raise Exception("Client not initialized. Call initialize() first.")

        url = f"{self.settings.graph_api_endpoint}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

        self.logger.debug(
            "Making Graph API request", method=method, endpoint=endpoint, params=params
        )

        response = await self._client.request(
            method, url, headers=headers, json=json_data, params=params
        )
        response_text = response.text

        if response.status_code >= 400:
            self.logger.error(
                "Graph API request failed",
                status_code=response.status_code,
                response=response_text,
            )
            raise Exception(f"Graph API request failed: {response.status_code} - {response_text}")

        if response_text:
            return response.json()
        return {}

    @retry_with_backoff(max_attempts=3, delay_seconds=30)
    async def get_inbox_messages(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get messages from the inbox.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of message dictionaries
        """
        endpoint = f"/users/{self.settings.monitored_email}/mailFolders/Inbox/messages"
        params = {
            "$top": limit,
            "$orderby": "receivedDateTime desc",
            "$select": "id,conversationId,subject,bodyPreview,body,from,toRecipients,ccRecipients,bccRecipients,receivedDateTime,sentDateTime,hasAttachments,importance,categories,isRead,isDraft,internetMessageHeaders",
        }

        self.logger.info(
            "Fetching inbox messages", email=self.settings.monitored_email, limit=limit
        )

        response = await self._make_request("GET", endpoint, params=params)
        messages = response.get("value", [])

        self.logger.info("Retrieved inbox messages", count=len(messages))

        return messages

    @retry_with_backoff(max_attempts=3, delay_seconds=30)
    async def create_folder(self, folder_name: str) -> dict[str, Any]:
        """Create a new mail folder.

        Args:
            folder_name: Name of the folder to create

        Returns:
            Created folder information
        """
        endpoint = f"/users/{self.settings.monitored_email}/mailFolders"
        data = {"displayName": folder_name}

        self.logger.info("Creating mail folder", folder_name=folder_name)

        try:
            folder = await self._make_request("POST", endpoint, json_data=data)
            self.logger.info(
                "Mail folder created",
                folder_name=folder_name,
                folder_id=folder.get("id"),
            )
            return folder
        except Exception as e:
            # Check if folder already exists
            if "already exists" in str(e).lower():
                self.logger.info(
                    "Folder already exists, fetching existing folder",
                    folder_name=folder_name,
                )
                return await self.get_folder_by_name(folder_name)
            raise

    async def get_folder_by_name(self, folder_name: str) -> dict[str, Any]:
        """Get folder by display name.

        Args:
            folder_name: Name of the folder

        Returns:
            Folder information or None if not found
        """
        endpoint = f"/users/{self.settings.monitored_email}/mailFolders"
        params = {"$filter": f"displayName eq '{folder_name}'"}

        response = await self._make_request("GET", endpoint, params=params)
        folders = response.get("value", [])

        if folders:
            return folders[0]
        return {}

    @retry_with_backoff(max_attempts=3, delay_seconds=30)
    async def move_message(self, message_id: str, destination_folder_id: str) -> dict[str, Any]:
        """Move a message to a different folder.

        Args:
            message_id: ID of the message to move
            destination_folder_id: ID of the destination folder

        Returns:
            Updated message information
        """
        endpoint = f"/users/{self.settings.monitored_email}/messages/{message_id}/move"
        data = {"destinationId": destination_folder_id}

        self.logger.info(
            "Moving message",
            message_id=message_id,
            destination_folder_id=destination_folder_id,
        )

        moved_message = await self._make_request("POST", endpoint, json_data=data)

        self.logger.info("Message moved successfully", message_id=message_id)

        return moved_message

    def _parse_email_address(self, address_data: dict[str, Any]) -> EmailAddress:
        """Parse email address from Graph API format.

        Args:
            address_data: Address data from Graph API

        Returns:
            EmailAddress model
        """
        email_address = address_data.get("emailAddress", {})
        return EmailAddress(email=email_address.get("address", ""), name=email_address.get("name"))

    def _parse_recipients(self, message: dict[str, Any]) -> EmailRecipients:
        """Parse recipients from Graph API message.

        Args:
            message: Message data from Graph API

        Returns:
            EmailRecipients model
        """
        return EmailRecipients(
            to=[self._parse_email_address(r) for r in message.get("toRecipients", [])],
            cc=[self._parse_email_address(r) for r in message.get("ccRecipients", [])],
            bcc=[self._parse_email_address(r) for r in message.get("bccRecipients", [])],
        )

    def _parse_importance(self, importance: str) -> EmailImportance:
        """Parse importance level.

        Args:
            importance: Importance string from Graph API

        Returns:
            EmailImportance enum value
        """
        importance_map = {
            "low": EmailImportance.LOW,
            "normal": EmailImportance.NORMAL,
            "high": EmailImportance.HIGH,
        }
        return importance_map.get(importance.lower(), EmailImportance.NORMAL)

    def convert_to_email_model(
        self, message: dict[str, Any], processing_id: str, version: str = "1.0.0"
    ) -> Email:
        """Convert Graph API message to Email model.

        Args:
            message: Message data from Graph API
            processing_id: Unique processing ID
            version: Inbox monitor version

        Returns:
            Email model instance
        """
        # Parse body content
        body_data = message.get("body", {})
        body = EmailBody(
            content_type=body_data.get("contentType", "text/plain"),
            content=body_data.get("content", ""),
        )

        # Parse dates
        received_dt = datetime.fromisoformat(message["receivedDateTime"].replace("Z", "+00:00"))
        sent_dt = None
        if message.get("sentDateTime"):
            sent_dt = datetime.fromisoformat(message["sentDateTime"].replace("Z", "+00:00"))

        # Parse headers
        headers = {}
        for header in message.get("internetMessageHeaders", []):
            headers[header.get("name", "")] = header.get("value", "")

        # Count attachments
        attachment_count = 0
        if message.get("hasAttachments"):
            # Would need additional API call to get exact count
            attachment_count = 1  # At least one

        # Create processing metadata
        processing_metadata = ProcessingMetadata(
            inbox_monitor_version=version,
            processing_id=processing_id,
            processing_timestamp=datetime.utcnow(),
        )

        return Email(
            id=message["id"],
            conversation_id=message.get("conversationId"),
            received_datetime=received_dt,
            sent_datetime=sent_dt,
            sender=self._parse_email_address(message.get("from", {})),
            recipients=self._parse_recipients(message),
            subject=message.get("subject", ""),
            body=body,
            body_preview=message.get("bodyPreview", ""),
            importance=self._parse_importance(message.get("importance", "normal")),
            has_attachments=message.get("hasAttachments", False),
            attachment_count=attachment_count,
            categories=message.get("categories", []),
            is_read=message.get("isRead", False),
            is_draft=message.get("isDraft", False),
            internet_message_headers=headers,
            processing_metadata=processing_metadata,
        )

    async def send_email(self, message_data: dict[str, Any]) -> tuple[bool, str | None, str | None]:
        """Send an email via Graph API.

        Args:
            message_data: Message data in Graph API format

        Returns:
            Tuple of (success, message_id, error)
        """
        try:
            # Send email using the monitored email account
            endpoint = f"/users/{self.settings.monitored_email}/sendMail"

            response = await self._make_request("POST", endpoint, json_data=message_data)

            # sendMail returns 202 Accepted with no body on success
            if response is not None:
                # Extract message ID if available
                message_id = response.get("id", str(uuid.uuid4()))
                return True, message_id, None
            else:
                # No response body means success
                return True, str(uuid.uuid4()), None

        except Exception as e:
            self.logger.error("Failed to send email", error=str(e))
            return False, None, str(e)
