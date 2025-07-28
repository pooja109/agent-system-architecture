"""
Salesforce Client
=================

Client for interacting with Salesforce API to create cases and update contacts
as part of the inbox monitoring scenarios.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

import httpx
import structlog
from pydantic import BaseModel, Field

try:
    from config.settings import SalesforceSettings
except ImportError:
    from ..config.settings import SalesforceSettings


class SalesforceTokenResponse(BaseModel):
    """Salesforce OAuth token response."""

    access_token: str = Field(..., description="Access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int | None = Field(default=3600, description="Token expiration in seconds")
    instance_url: str = Field(..., description="Salesforce instance URL")


class CaseCreateRequest(BaseModel):
    """Request model for creating a Salesforce case."""

    account_id: str = Field(..., description="Salesforce account ID")
    contact_id: str = Field(..., description="Salesforce contact ID")
    owner_id: str = Field(..., description="Case owner ID")
    subject: str = Field(..., description="Case subject")
    description: str = Field(..., description="Case description")
    origin: str = Field(default="AI Agent", description="Case origin")
    status: str = Field(default="New", description="Case status")
    priority: str = Field(default="Medium", description="Case priority")
    case_queue: str = Field(..., description="Case queue")


class CaseCreateResponse(BaseModel):
    """Response model for case creation."""

    id: str = Field(..., description="Created case ID")
    success: bool = Field(..., description="Whether creation was successful")
    errors: list[str] = Field(default_factory=list, description="Any errors encountered")


class ContactUpdateRequest(BaseModel):
    """Request model for updating a contact."""

    contact_id: str = Field(..., description="Contact ID to update")
    is_email_invalid: bool = Field(default=True, description="Boolean flag to mark email as invalid")



class SalesforceClient:
    """Client for Salesforce API operations."""

    def __init__(self, settings: SalesforceSettings):
        """Initialize the Salesforce client.

        Args:
            settings: Salesforce configuration settings
        """
        self.settings = settings
        self.logger = structlog.get_logger(__name__)
        self.client: httpx.AsyncClient | None = None
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def __aenter__(self) -> "SalesforceClient":
        """Async context manager entry."""
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

        # Create HTTPX client with HTTP/2 support (fallback to HTTP/1.1)
        try:
            self.client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=True,  # Enable HTTP/2
                verify=False,  # Disable SSL verification if needed
                follow_redirects=True,
            )
        except ImportError:
            # Fallback to HTTP/1.1 if h2 package is not installed
            self.client = httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                http2=False,  # Disable HTTP/2
                verify=False,  # Disable SSL verification if needed
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self.client:
            try:
                # HTTPX handles cleanup automatically and gracefully
                await self.client.aclose()

                # Small delay to ensure cleanup completes
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.warning("Error closing Salesforce client", error=str(e))
            finally:
                self.client = None


    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if necessary.

        Returns:
            Valid access token

        Raises:
            Exception: If token acquisition fails
        """
        # Check if we have a valid token
        if (
            self._access_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at - timedelta(minutes=5)
        ):
            return self._access_token

        # Request new token
        await self._refresh_token()
        if self._access_token is None:
            raise RuntimeError("Failed to obtain access token")
        return self._access_token

    async def _refresh_token(self) -> None:
        """Refresh the access token.

        Raises:
            Exception: If token refresh fails
        """
        if not self.client:
            raise RuntimeError("HTTP client not initialized. Use async context manager.")

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        data = {
            "grant_type": "client_credentials",
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }

        try:
            response = await self.client.post(
                self.settings.token_endpoint, headers=headers, data=data
            )
            if response.status_code != 200:
                raise Exception(
                    f"Token request failed with status {response.status_code}: {response.text}"
                )

            result = response.json()

            # Parse token response
            token_response = SalesforceTokenResponse(**result)

            self._access_token = token_response.access_token
            self._token_expires_at = datetime.utcnow() + timedelta(
                seconds=token_response.expires_in or 3600
            )

            self.logger.info(
                "Successfully refreshed Salesforce access token",
                expires_in=token_response.expires_in,
            )

        except httpx.HTTPError as e:
            raise Exception(f"HTTP client error during token refresh: {e!s}") from e
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse token response: {e!s}") from e

    async def create_case(self, case_request: CaseCreateRequest) -> CaseCreateResponse:
        """Create a new case in Salesforce.

        Args:
            case_request: Case creation request details

        Returns:
            CaseCreateResponse with creation results

        Raises:
            Exception: If case creation fails
        """
        try:
            access_token = await self._get_access_token()

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            # Prepare the case data
            case_data = {
                "AccountId": case_request.account_id,
                "ContactId": case_request.contact_id,
                "RecordTypeId": self.settings.case_record_type_id,
                "OwnerId": case_request.owner_id,
                "Status": case_request.status,
                "Priority": case_request.priority,
                "Origin": case_request.origin,
                "Subject": case_request.subject,
                "Description": case_request.description,
                "Case_Queue__c": case_request.case_queue,
            }

            # Construct API URL
            api_url = (
                f"{self.settings.base_url}/services/data/{self.settings.api_version}/sobjects/Case/"
            )

            if self.client is None:
                raise RuntimeError("Client not initialized. Use async context manager.")
            response = await self.client.post(api_url, headers=headers, json=case_data)
            result = response.json()

            if response.status_code == 201:
                # Success
                case_id = result.get("id")
                self.logger.info(
                    "Successfully created Salesforce case",
                    case_id=case_id,
                    account_id=case_request.account_id,
                    contact_id=case_request.contact_id,
                )

                return CaseCreateResponse(id=case_id, success=True, errors=[])
            else:
                # Error occurred
                errors = result if isinstance(result, list) else [result]

                self.logger.error(
                    "Failed to create Salesforce case",
                    status=response.status_code,
                    errors=errors,
                    account_id=case_request.account_id,
                    contact_id=case_request.contact_id,
                )

                return CaseCreateResponse(id="", success=False, errors=errors)

        except Exception as e:
            self.logger.error(
                "Exception during case creation",
                error=str(e),
                account_id=case_request.account_id,
                contact_id=case_request.contact_id,
            )
            raise

    async def update_contact_invalid_email(self, contact_update: ContactUpdateRequest) -> bool:
        """Update a contact's invalid email flag.

        Args:
            contact_update: Contact update request details

        Returns:
            True if update was successful, False otherwise

        Raises:
            Exception: If update fails
        """
        try:
            access_token = await self._get_access_token()

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            # Prepare the update data - using the new boolean field
            update_data = {"Is_Email_Invalid__c": contact_update.is_email_invalid}

            # For Salesforce, we need to use different approach since PATCH isn't supported
            # Use the composite API or REST API with proper method
            if not contact_update.contact_id:
                # If no contact ID, we need to find the contact by email first
                self.logger.warning("No contact ID provided for update")
                return False

            # Construct API URL for updating using proper PATCH method
            api_url = f"{self.settings.base_url}/services/data/{self.settings.api_version}/sobjects/Contact/{contact_update.contact_id}"

            if self.client is None:
                raise RuntimeError("Client not initialized. Use async context manager.")
            response = await self.client.patch(api_url, headers=headers, json=update_data)
            if response.status_code in [200, 204]:
                # Success (no content returned)
                self.logger.info(
                    "Successfully updated contact invalid email flag",
                    contact_id=contact_update.contact_id,
                    is_email_invalid=contact_update.is_email_invalid,
                )
                return True
            else:
                # Error occurred
                error_text = response.text
                self.logger.error(
                    "Failed to update contact invalid email flag",
                    status=response.status_code,
                    error=error_text,
                    contact_id=contact_update.contact_id,
                )
                return False

        except Exception as e:
            self.logger.error(
                "Exception during contact update",
                error=str(e),
                contact_id=contact_update.contact_id,
            )
            raise

    async def test_connection(self) -> bool:
        """Test the connection to Salesforce.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get an access token
            access_token = await self._get_access_token()

            # Test with a simple API call
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

            api_url = (
                f"{self.settings.base_url}/services/data/{self.settings.api_version}/sobjects/"
            )

            if self.client is None:
                raise RuntimeError("Client not initialized. Use async context manager.")
            response = await self.client.get(api_url, headers=headers)
            if response.status_code == 200:
                self.logger.info("Salesforce connection test successful")
                return True
            else:
                self.logger.error("Salesforce connection test failed", status=response.status_code)
                return False

        except Exception as e:
            self.logger.error("Salesforce connection test failed", error=str(e))
            return False

    async def get_contact_details(self, contact_id: str) -> dict[str, Any] | None:
        """Get contact details from Salesforce.

        Args:
            contact_id: Salesforce contact ID

        Returns:
            Contact details dictionary or None if not found

        Raises:
            Exception: If API call fails
        """
        try:
            access_token = await self._get_access_token()

            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

            # Select specific fields we need
            fields = "Id,Email,AccountId,Account.Name,FirstName,LastName,Account.OwnerId"
            api_url = f"{self.settings.base_url}/services/data/{self.settings.api_version}/sobjects/Contact/{contact_id}?fields={fields}"

            if self.client is None:
                raise RuntimeError("Client not initialized. Use async context manager.")
            response = await self.client.get(api_url, headers=headers)
            if response.status_code == 200:
                result = response.json()
                return result
            elif response.status_code == 404:
                self.logger.warning("Contact not found", contact_id=contact_id)
                return None
            else:
                raise Exception(
                    f"Failed to get contact details: {response.status_code} - {response.text}"
                )

        except Exception as e:
            self.logger.error(
                "Exception getting contact details", error=str(e), contact_id=contact_id
            )
            raise

    async def _authenticate(self):
        """Authenticate with Salesforce and get access token."""
        try:
            # Prepare authentication request
            auth_data = {
                "grant_type": "client_credentials",
                "client_id": self.settings.client_id,
                "client_secret": self.settings.client_secret,
            }

            # Make authentication request
            response = await self.client.post(
                self.settings.token_endpoint,
                data=auth_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if response.status_code == 200:
                token_data = response.json()
                self._access_token = token_data.get("access_token")

                # Calculate token expiration (default to 1 hour if not provided)
                expires_in = token_data.get("expires_in", 3600)
                self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

                self.logger.info("Successfully authenticated with Salesforce")
            else:
                raise Exception(
                    f"Salesforce authentication failed: {response.status_code} - {response.text}"
                )

        except Exception as e:
            self.logger.error("Failed to authenticate with Salesforce", error=str(e))
            raise
