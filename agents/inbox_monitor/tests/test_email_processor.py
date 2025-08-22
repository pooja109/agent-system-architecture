"""
Tests for Email Processor Service
=================================
Unit tests for email processing functionality.
"""
import os
import sys
from unittest.mock import AsyncMock, Mock, mock_open, patch
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.email_processor import EmailProcessor  # noqa: E402
class TestEmailProcessor:
    """Test EmailProcessor class."""
    @pytest.fixture
    def processor(self, mock_settings, mock_graph_client):
        """Create email processor instance."""
        with patch('services.email_processor.ScenarioProcessor') as mock_scenario_class:
            # Mock the ScenarioProcessor to avoid Key Vault authentication
            mock_scenario_instance = Mock()
            mock_scenario_instance.__aenter__ = AsyncMock(return_value=mock_scenario_instance)
            mock_scenario_instance.__aexit__ = AsyncMock(return_value=None)
            
            # Set up default mock for process_email_scenario
            mock_scenario_result = Mock()
            mock_scenario_result.scenario_type.value = "scenario_1"
            mock_scenario_result.success = True  # Ensure scenario processing succeeds
            mock_scenario_result.agent_actions_log = ["test_action"]
            mock_scenario_result.expert_assigned = None  # Proper None value
            mock_scenario_result.case_created = None  # Proper None value
            mock_scenario_result.emails_sent = []  # Proper list value
            mock_scenario_instance.process_email_scenario = AsyncMock(return_value=mock_scenario_result)
            
            mock_scenario_class.return_value = mock_scenario_instance
            
            processor = EmailProcessor(mock_settings, mock_graph_client)
            # Replace the scenario processor with our mock
            processor.scenario_processor = mock_scenario_instance
            # Store the mock for tests to access
            processor._mock_scenario_processor = mock_scenario_instance
            return processor
    
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.smoke
    async def test_process_inbox_no_messages(self, processor, mock_graph_client):
        """Test processing inbox with no messages."""
        mock_graph_client.get_inbox_messages.return_value = []
        results = await processor.process_inbox()
        assert results["success"] is True
        assert results["processed_count"] == 0
        assert results["failed_count"] == 0
        assert len(results["errors"]) == 0
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.email
    async def test_process_inbox_with_messages(
        self, processor, mock_graph_client, mock_graph_message, mock_folder
    ):
        """Test processing inbox with messages."""
        mock_graph_client.get_inbox_messages.return_value = [mock_graph_message]
        mock_graph_client.get_folder_by_name.return_value = mock_folder  # Folder already exists
        # Mock email conversion with proper attributes
        mock_email = Mock()
        mock_email.id = "test-message-id-123"
        mock_email.to_ai_format.return_value = {"id": "test-message-id-123"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.process_id = "test-processing-id"
        
        # Set up required string attributes for ProcessingResult
        mock_email.sender = Mock()
        mock_email.sender.email = "test@example.com"
        mock_email.sender.name = "Test Sender"
        mock_email.subject = "Test Subject"
        
        mock_graph_client.convert_to_email_model.return_value = mock_email
        # Mock scenario processor context manager
        mock_scenario_result = Mock()
        mock_scenario_result.scenario_type.value = "scenario_1"
        mock_scenario_result.success = True  # Ensure scenario succeeds
        mock_scenario_result.agent_actions_log = ["test_action"]
        mock_scenario_result.expert_assigned = None
        mock_scenario_result.case_created = None
        mock_scenario_result.emails_sent = []
        processor.scenario_processor.process_email_scenario = AsyncMock(return_value=mock_scenario_result)
        processor.scenario_processor.__aenter__ = AsyncMock(return_value=processor.scenario_processor)
        processor.scenario_processor.__aexit__ = AsyncMock(return_value=None)
        
        # Mock retry_operation to return success
        with patch("utils.retry.retry_operation") as mock_retry:
            mock_retry.return_value = (True, {"id": "moved-message"}, None)
            # Mock file writing
            with patch("builtins.open", mock_open()):
                results = await processor.process_inbox()
        assert results["success"] is True
        assert results["processed_count"] == 1
        assert results["failed_count"] == 0
        assert len(results["processing_results"]) == 1
        # Note: retry_operation may not be called if scenario processing fails
        # The main test is that inbox processing completes successfully
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.edge_case
    @pytest.mark.email
    async def test_process_inbox_folder_creation_failure(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test handling folder creation failure."""
        mock_graph_client.get_inbox_messages.return_value = [mock_graph_message]
        mock_graph_client.get_folder_by_name.return_value = None
        mock_graph_client.create_folder.side_effect = Exception("Failed to create folder")
        results = await processor.process_inbox()
        assert results["success"] is False
        assert "Failed to create/get processed folder" in results["errors"][0]
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.email
    async def test_process_single_email_success(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test processing a single email successfully."""
        # Mock email conversion with proper attributes
        mock_email = Mock()
        mock_email.id = "test-message-id-123"
        mock_email.to_ai_format.return_value = {"id": "test-message-id-123"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.process_id = "test-processing-id"
        
        # Set up required string attributes for ProcessingResult
        mock_email.sender = Mock()
        mock_email.sender.email = "test@example.com"
        mock_email.sender.name = "Test Sender"
        mock_email.subject = "Test Subject"
        
        mock_graph_client.convert_to_email_model.return_value = mock_email
        # Mock retry_operation to return success
        with patch("utils.retry.retry_operation") as mock_retry:
            mock_retry.return_value = (True, {"id": "moved-message"}, None)
            # Mock file writing
            with patch("builtins.open", mock_open()):
                result = await processor._process_single_email(
                    mock_graph_message, "folder-id", "Processed_01_2024"
                )
        assert result.success is True
        assert result.email_id == "test-message-id-123"
        assert result.destination_folder == "Processed_01_2024"
        assert result.storage_location is not None
        assert result.error is None
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.email
    async def test_process_single_email_dry_run(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test processing email in dry-run mode."""
        processor.settings.dry_run = True
        # Mock email conversion with proper attributes
        mock_email = Mock()
        mock_email.id = "test-message-id-123"
        mock_email.to_ai_format.return_value = {"id": "test-message-id-123"}
        mock_email.processing_metadata = Mock()
        mock_email.processing_metadata.process_id = "test-processing-id"
        
        # Set up required string attributes for ProcessingResult
        mock_email.sender = Mock()
        mock_email.sender.email = "test@example.com"
        mock_email.sender.name = "Test Sender"
        mock_email.subject = "Test Subject"
        
        mock_graph_client.convert_to_email_model.return_value = mock_email
        # Mock file writing
        with patch("builtins.open", mock_open()):
            result = await processor._process_single_email(
                mock_graph_message, "folder-id", "Processed_01_2024"
            )
        assert result.success is True
        assert result.destination_folder is None  # Not moved in dry-run
        # Verify email was NOT moved
        mock_graph_client.move_message.assert_not_called()
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.edge_case
    @pytest.mark.email
    async def test_process_single_email_failure(
        self, processor, mock_graph_client, mock_graph_message
    ):
        """Test handling email processing failure."""
        mock_graph_client.convert_to_email_model.side_effect = Exception("Conversion failed")
        result = await processor._process_single_email(
            mock_graph_message, "folder-id", "Processed_01_2024"
        )
        assert result.success is False
        assert "Conversion failed" in result.error
        assert result.destination_folder is None
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    async def test_store_email_file(self, processor, mock_email_model):
        """Test storing email as file."""
        # Mock file operations
        with patch("builtins.open", mock_open()) as mock_file, patch("pathlib.Path.mkdir"):
            location = await processor._store_email_file(mock_email_model)
        assert "email_" in location
        assert ".json" in location
        # Verify file was written
        mock_file.assert_called_once()
        # Since json.dump is used, we check that file handle was used
        assert mock_file().write.called or mock_file().__enter__().write.called
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_store_email_api(self, processor, mock_email_model):
        """Test storing email via API."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"
        processor.settings.output.api_key = "test-api-key"
        # Mock API response
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"id": "api-email-id"}
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            
            mock_client_class.return_value = mock_client
            location = await processor._store_email_api(mock_email_model)
        assert location == "api-email-id"
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    async def test_store_email_api_error(self, processor, mock_email_model):
        """Test API storage error handling."""
        processor.settings.output.storage_type = "api"
        processor.settings.output.api_endpoint = "https://api.example.com/emails"
        # Mock API error response
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            
            mock_client_class.return_value = mock_client
            with pytest.raises(Exception, match="API request failed: 500"):
                await processor._store_email_api(mock_email_model)
    @pytest.mark.fast
    @pytest.mark.unit
    def test_get_processed_folder_name(self, processor):
        """Test generating processed folder name."""
        with patch("services.email_processor.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.side_effect = ["01", "2024"]
            folder_name = processor._get_processed_folder_name()
        assert folder_name == "Processed_01_2024"
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.integration
    @pytest.mark.azure
    async def test_ensure_processed_folder_exists(self, processor, mock_graph_client, mock_folder):
        """Test ensuring folder exists when it already exists."""
        mock_graph_client.get_folder_by_name.return_value = mock_folder
        folder = await processor._ensure_processed_folder("Test Folder")
        assert folder is not None
        assert folder["id"] == "test-folder-id-123"
        # Should not create new folder
        mock_graph_client.create_folder.assert_not_called()
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.retry
    async def test_ensure_processed_folder_create_new(
        self, processor, mock_graph_client, mock_folder
    ):
        """Test creating new folder when it doesn't exist."""
        mock_graph_client.get_folder_by_name.return_value = None
        # Mock retry_operation to return success - patch at service level
        with patch("services.email_processor.retry_operation") as mock_retry:
            mock_retry.return_value = (True, mock_folder, None)
            folder = await processor._ensure_processed_folder("Test Folder")
        assert folder is not None
        assert folder["id"] == "test-folder-id-123"  # This should match mock_folder fixture
        # Should have called retry operation
        mock_retry.assert_called_once()
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.azure
    async def test_ensure_processed_folder_create_failure(self, processor, mock_graph_client):
        """Test handling folder creation failure."""
        mock_graph_client.get_folder_by_name.return_value = None
        mock_graph_client.create_folder.side_effect = Exception("Creation failed")
        folder = await processor._ensure_processed_folder("Test Folder")
        assert folder is None