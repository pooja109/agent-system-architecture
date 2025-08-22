"""
Email Processor Error Condition Tests
====================================
Tests for error conditions and failure scenarios in EmailProcessor.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import httpx

from services.email_processor import EmailProcessor


class TestEmailProcessorErrorConditions:
    """Test error conditions for EmailProcessor."""
    
    @pytest.fixture
    def processor(self, mock_settings, mock_graph_client):
        """Create email processor instance."""
        return EmailProcessor(mock_settings, mock_graph_client)
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_process_inbox_with_graph_api_failure(self, processor, mock_graph_client):
        """Test inbox processing when Graph API fails."""
        mock_graph_client.get_inbox_messages.side_effect = Exception("Graph API unavailable")
        results = await processor.process_inbox()
        assert results["success"] is False
        assert results["processed_count"] == 0
        assert results["failed_count"] == 0
        assert "Graph API unavailable" in results["errors"][0]
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_process_inbox_with_authentication_failure(self, processor, mock_graph_client):
        """Test inbox processing with authentication failure."""
        mock_graph_client.get_inbox_messages.side_effect = Exception(
            "Authentication failed: Invalid credentials"
        )
        results = await processor.process_inbox()
        assert results["success"] is False
        assert "Authentication failed" in results["errors"][0]
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_process_inbox_with_network_timeout(self, processor, mock_graph_client):
        """Test inbox processing with network timeout."""
        mock_graph_client.get_inbox_messages.side_effect = asyncio.TimeoutError("Network timeout")
        results = await processor.process_inbox()
        assert results["success"] is False
        assert "Network timeout" in results["errors"][0]
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_process_inbox_with_rate_limiting(self, processor, mock_graph_client):
        """Test inbox processing with rate limiting."""
        mock_graph_client.get_inbox_messages.side_effect = Exception(
            "Rate limit exceeded: 429 Too Many Requests"
        )
        results = await processor.process_inbox()
        assert results["success"] is False
        assert "Rate limit exceeded" in results["errors"][0]
    
    @pytest.mark.medium
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_process_inbox_with_folder_creation_permission_denied(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test inbox processing when folder creation is denied."""
        mock_graph_client.get_inbox_messages.return_value = [mock_graph_message]
        mock_graph_client.get_folder_by_name.return_value = None
        mock_graph_client.create_folder.side_effect = Exception(
            "Insufficient permissions to create folder"
        )
        results = await processor.process_inbox()
        assert results["success"] is False
        assert "Failed to create/get processed folder" in results["errors"][0]
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_store_email_with_invalid_storage_type(self, processor, mock_email_model):
        """Test email storage with invalid storage type."""
        processor.settings.output.storage_type = "invalid-type"
        with pytest.raises(ValueError, match="Unsupported storage type"):
            await processor._store_email(mock_email_model)
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_store_email_file_with_invalid_path(self, processor, mock_email_model):
        """Test file storage with invalid path."""
        # Set output directory to an invalid path
        processor.settings.output.output_directory = "/invalid/path/that/does/not/exist"
        with pytest.raises(FileNotFoundError):
            await processor._store_email_file(mock_email_model)
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_store_email_api_without_endpoint(self, processor, mock_email_model):
        """Test API storage without endpoint configuration."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = None
        with pytest.raises(ValueError, match="API endpoint not configured"):
            await processor._store_email_api(mock_email_model)
    
    @pytest.mark.medium
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_store_email_api_with_server_error(self, processor, mock_email_model):
        """Test API storage with server error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"
        
        with patch("httpx.AsyncClient") as mock_client_class:
            # Create a proper mock response with status_code as integer
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            
            # Mock the async context manager properly
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = False
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            with pytest.raises(Exception, match="API request failed: 500"):
                await processor._store_email_api(mock_email_model)
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.azure
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_store_email_api_with_connection_error(self, processor, mock_email_model):
        """Test API storage with connection error."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"
        
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            with pytest.raises(httpx.ConnectError):
                await processor._store_email_api(mock_email_model)
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_ensure_processed_folder_with_graph_api_error(self, processor, mock_graph_client):
        """Test folder creation with Graph API error."""
        mock_graph_client.get_folder_by_name.side_effect = Exception("Graph API error")
        # The method doesn't handle exceptions, so it should raise
        with pytest.raises(Exception, match="Graph API error"):
            await processor._ensure_processed_folder("Test Folder")
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.ci_safe
    @pytest.mark.asyncio
    async def test_process_single_email_with_json_serialization_error(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with JSON serialization error."""
        # Mock email conversion to return non-serializable object
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.side_effect = TypeError("Object is not JSON serializable")
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.process_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email
        
        result = await processor._process_single_email(
            mock_graph_message, "folder-id", "Test Folder"
        )
        assert result.success is False
        assert "Object is not JSON serializable" in result.error
    
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    @pytest.mark.asyncio
    async def test_process_single_email_with_unicode_error(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test single email processing with Unicode encoding error."""
        # Mock email conversion
        mock_email = Mock()
        mock_email.id = "test-message-id"
        mock_email.to_ai_format.return_value = {"id": "test-message-id"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.process_id = "test-processing-id"
        mock_graph_client.convert_to_email_model.return_value = mock_email
        
        # Mock file writing to fail with encoding error
        with patch(
            "builtins.open",
            side_effect=UnicodeEncodeError("utf-8", "test", 0, 1, "invalid character"),
        ):
            result = await processor._process_single_email(
                mock_graph_message, "folder-id", "Test Folder"
            )
        
        assert result.success is False
        assert "utf-8" in result.error and "invalid character" in result.error