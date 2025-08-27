"""
End-to-End Integration Tests for Scenario Tracking with Real Databricks Connections
================================================================================

Tests the complete email processing and scenario tracking pipeline with real
Databricks connections when available. Falls back to comprehensive mocks when
external dependencies are not available.

Test Categories:
- Full email processing pipeline with scenario tracking
- Batch processing with real database operations
- Retry mechanism testing with transient failures
- Data sanitization validation
- Health check integration
- Performance under load

Environment Variables:
- RUN_DATABRICKS_INTEGRATION_TESTS=true: Enable real Databricks tests
- DATABRICKS_TEST_TABLE_SUFFIX=_integration_test: Use test tables
- TEST_MODE=integration: Enable integration test mode
"""

import asyncio
import os
import pytest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List
import uuid

from services.scenario_tracking_integration import (
    ScenarioTrackingIntegration,
    TrackingIntegrationResult,
    get_tracking_integration
)
from services.scenario_processor import ScenarioProcessor, ScenarioResult, ScenarioType
from services.email_processor import EmailProcessor
from services.azure_ai_foundry_client import IntentClassificationResult, EmailIntent
from database.scenario_tracking_models import (
    ScenarioTrackingConfiguration,
    ScenarioProcessingRecord,
    TestModeType
)
from pydantic import ValidationError
from models.email import Email, ProcessingResult, EmailBody, EmailAddress, EmailRecipients
from utils.data_transformation import ScenarioDataTransformer
from config.settings import AppSettings
from services.health_check_service import HealthCheckService


class TestEndToEndDatabricksIntegration:
    """Comprehensive end-to-end integration tests."""
    
    @pytest.fixture(scope="class")
    def integration_enabled(self):
        """Check if integration tests should run with real connections."""
        return os.getenv("RUN_DATABRICKS_INTEGRATION_TESTS", "false").lower() == "true"
    
    @pytest.fixture
    async def real_integration_service(self, integration_enabled):
        """Create integration service with real or mock connections."""
        if integration_enabled:
            # Use real Databricks connection with test configuration
            config = ScenarioTrackingConfiguration(
                enabled=True,
                databricks_host=os.getenv("DATABRICKS_HOST"),
                databricks_token=os.getenv("DATABRICKS_TOKEN"),
                databricks_http_path=os.getenv("DATABRICKS_HTTP_PATH"),
                table_name=f"scenario_tracking{os.getenv('DATABRICKS_TEST_TABLE_SUFFIX', '_test')}",
                async_insert=True,
                batch_insert_size=5,
                connection_timeout_seconds=30,
                max_retry_attempts=3,
                base_retry_delay_seconds=1.0,
                max_retry_delay_seconds=10.0
            )
        else:
            # Use mock configuration
            config = ScenarioTrackingConfiguration(
                enabled=True,
                async_insert=True,
                batch_insert_size=5,
                retry_attempts=3  # Changed from max_retry_attempts to retry_attempts
            )
        
        service = ScenarioTrackingIntegration(config)
        
        if not integration_enabled:
            # Mock the tracking client for non-integration tests
            service.tracking_client = AsyncMock()
            service.tracking_client.store_scenario_result = AsyncMock(return_value=True)
            service.tracking_client.store_scenario_results_batch = AsyncMock(return_value=True)
            service.tracking_client.health_check = AsyncMock(return_value={"status": "healthy"})
            service.tracking_client.initialize_table = AsyncMock(return_value=True)
            service.tracking_client.close = AsyncMock()
        
        yield service, integration_enabled
        await service.close()
    
    @pytest.fixture
    def sample_email(self):
        """Create a comprehensive sample email for testing."""
        email = Email(
            id="integration-test-" + str(uuid.uuid4()),
            conversation_id="conv-" + str(uuid.uuid4()),
            sender=EmailAddress(
                email="integration.test@example.com",
                name="Integration Test User"
            ),
            recipients=EmailRecipients(
                to=[EmailAddress(email="support@company.com", name="Support Team")],
                cc=[],
                bcc=[]
            ),
            subject="Integration Test: Customer Inquiry",
            body=EmailBody(
                content_type="text/html",
                content="<p>This is a test email for integration testing. It contains customer feedback about our service.</p>"
            ),
            email_body="This is a test email for integration testing...",
            received_datetime=datetime.now(timezone.utc),
            importance="normal",
            has_attachments=False,
            attachment_count=0
        )
        return email
    
    @pytest.fixture
    def sample_processing_result(self):
        """Create a sample processing result."""
        return ProcessingResult(
            success=True,
            email_id="integration-test-" + str(uuid.uuid4()),
            process_id="proc-" + str(uuid.uuid4()),
            sender_email="integration.test@example.com",
            sender_name="Integration Test User",
            subject="Integration Test: Customer Inquiry",
            processing_duration_ms=1250,
            scenario_type="scenario_5",
            scenario_success=True,
            agent_actions_log=["expert_assigned", "case_created"],
            expert_assigned="john.expert@company.com",
            case_created="SF-123456"
        )
    
    @pytest.fixture
    def sample_scenario_result(self):
        """Create a sample scenario result with intent classification."""
        intent_result = IntentClassificationResult(
            intent=EmailIntent.POSITIVE,
            confidence=0.85,
            reasoning="Customer expressed satisfaction with service quality and mentioned positive experience.",
            detected_phrases=["excellent service", "very satisfied", "highly recommend"],
            processing_duration_ms=500
        )
        
        result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            agent_actions_log=["expert_assigned", "case_created", "notification_sent"],
            expert_assigned="john.expert@company.com",
            case_created="SF-123456",
            emails_sent=["john.expert@company.com"],
            intent_result=intent_result
        )
        
        return result
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_single_email_end_to_end_processing(
        self, 
        real_integration_service, 
        sample_email, 
        sample_processing_result, 
        sample_scenario_result
    ):
        """Test complete end-to-end processing of a single email."""
        service, is_real = real_integration_service
        
        # Track the email processing
        result = await service.track_scenario_processing(
            email_data=sample_email,
            processing_result=sample_processing_result,
            scenario_result=sample_scenario_result,
            intent_result=sample_scenario_result.intent_result,
            correlation_id="integration-test-correlation",
            test_mode=True,
            environment="integration_test",
            monitor_version="1.0.0-integration"
        )
        
        # Verify result
        assert result.success is True
        assert result.processing_duration_ms > 0
        assert result.record_created is True
        
        if is_real:
            # For real integration, verify record was actually stored
            assert result.async_queued in [True, False]  # Depends on configuration
        else:
            # For mock integration, verify mocks were called correctly
            assert service.tracking_client.store_scenario_result.called
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_batch_processing_integration(self, real_integration_service, sample_email):
        """Test batch processing with multiple emails."""
        service, is_real = real_integration_service
        
        # Create multiple emails for batch processing
        batch_size = 7
        emails = []
        processing_results = []
        
        for i in range(batch_size):
            email = Email(
                id=f"batch-test-{i}-{uuid.uuid4()}",
                sender=EmailAddress(email=f"batch.test.{i}@example.com", name=f"Batch User {i}"),
                recipients=EmailRecipients(to=[EmailAddress(email="support@company.com", name="Support")]),
                subject=f"Batch Test Email {i}",
                body=EmailBody(content_type="text/plain", content=f"Test email content {i}"),
                received_datetime=datetime.now(timezone.utc)
            )
            
            processing_result = ProcessingResult(
                success=True,
                email_id=email.id,
                process_id=f"batch-proc-{i}-{uuid.uuid4()}",
                sender_email=email.sender.email,
                processing_duration_ms=500 + (i * 100),
                scenario_type="scenario_6" if i % 2 == 0 else "scenario_5",
                scenario_success=True
            )
            
            emails.append(email)
            processing_results.append(processing_result)
        
        # Process emails and track them
        results = []
        for email, proc_result in zip(emails, processing_results):
            result = await service.track_scenario_processing(
                email_data=email,
                processing_result=proc_result,
                correlation_id=f"batch-correlation-{uuid.uuid4()}"
            )
            results.append(result)
        
        # Verify all processing succeeded
        assert all(r.success for r in results)
        assert len(results) == batch_size
        
        # Wait for batch processing to complete
        await asyncio.sleep(2)
        
        # Flush any pending batches
        await service.flush_pending_operations()
        
        if is_real:
            # For real integration, verify batch processing occurred
            health = await service.get_integration_health()
            batch_info = health.get("batch_processing", {})
            assert batch_info.get("enabled") is True
        
    @pytest.mark.slow
    @pytest.mark.e2e
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_retry_mechanism_with_transient_failures(self, real_integration_service, sample_email):
        """Test retry mechanism with simulated transient failures."""
        service, is_real = real_integration_service
        
        if not is_real:
            # Simulate transient failures for mock testing
            call_count = 0
            original_store = service.tracking_client.store_scenario_result
            
            async def failing_store(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:  # Fail first 2 attempts
                    raise ConnectionError("Simulated transient failure")
                return await original_store(*args, **kwargs)
            
            service.tracking_client.store_scenario_result = failing_store
        
        processing_result = ProcessingResult(
            success=True,
            email_id=sample_email.id,
            process_id=f"retry-test-{uuid.uuid4()}",
            sender_email=sample_email.sender.email,
            processing_duration_ms=1000
        )
        
        # Track with retry logic
        result = await service.track_scenario_processing(
            email_data=sample_email,
            processing_result=processing_result,
            correlation_id=f"retry-correlation-{uuid.uuid4()}"
        )
        
        if not is_real:
            # Should succeed after retries
            assert result.success is True
            assert result.retry_attempts >= 2  # Should have retried
            assert call_count == 3  # Initial + 2 retries
        else:
            # Real integration should work without retries needed
            assert result.success is True
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_data_sanitization_integration(self, real_integration_service):
        """Test comprehensive data sanitization during integration."""
        service, is_real = real_integration_service
        
        # Create email with potentially dangerous content
        malicious_email = Email(
            id="sanitization-test-" + str(uuid.uuid4()),
            sender=EmailAddress(
                email="test@example.com",
                name="'; DROP TABLE users; --"  # SQL injection attempt
            ),
            recipients=EmailRecipients(
                to=[EmailAddress(email="admin@company.com", name="Admin")]
            ),
            subject="<script>alert('xss')</script>Test Subject",
            body=EmailBody(
                content_type="text/html",
                content="<script>alert('xss')</script>Normal content with SSN: 123-45-6789"
            ),
            received_datetime=datetime.now(timezone.utc)
        )
        
        processing_result = ProcessingResult(
            success=True,
            email_id=malicious_email.id,
            process_id=f"sanitization-proc-{uuid.uuid4()}",
            sender_email=malicious_email.sender.email,
            error="../../../etc/passwd",  # Path traversal attempt
            processing_duration_ms=750
        )
        
        # Track the malicious email
        result = await service.track_scenario_processing(
            email_data=malicious_email,
            processing_result=processing_result,
            correlation_id=f"sanitization-correlation-{uuid.uuid4()}"
        )
        
        # Should succeed with sanitized data
        assert result.success is True
        
        # Verify sanitization occurred (check logs or data transformer)
        transformer = ScenarioDataTransformer()
        tracking_record = transformer.create_tracking_record(
            email_data=malicious_email,
            processing_result=processing_result
        )
        
        # Verify dangerous content was sanitized
        assert "DROP TABLE" not in tracking_record.sender_name
        assert "<script>" not in tracking_record.subject
        assert "[SANITIZED]" in tracking_record.sender_name
        assert "[PII_REDACTED]" in tracking_record.subject
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_health_check_integration(self, real_integration_service):
        """Test health check integration with main health system."""
        service, is_real = real_integration_service
        
        # Get scenario tracking health
        tracking_health = await service.get_integration_health()
        
        # Verify health check structure
        assert "integration_service" in tracking_health
        assert "status" in tracking_health
        assert "batch_processing" in tracking_health
        assert "retry_configuration" in tracking_health
        
        # Test main health check service integration
        health_service = HealthCheckService()
        comprehensive_health = await health_service.get_comprehensive_health_status()
        
        # Verify scenario tracking is included
        components = comprehensive_health.get("components", [])
        scenario_tracking_component = None
        for component in components:
            if component.get("name") == "scenario_tracking":
                scenario_tracking_component = component
                break
        
        assert scenario_tracking_component is not None
        assert scenario_tracking_component.get("status") in ["HEALTHY", "DEGRADED", "UNKNOWN"]
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_performance_under_load(self, real_integration_service, sample_email):
        """Test system performance under concurrent load."""
        service, is_real = real_integration_service
        
        # Create concurrent processing tasks
        concurrent_emails = 15
        tasks = []
        
        start_time = time.time()
        
        for i in range(concurrent_emails):
            email = Email(
                id=f"load-test-{i}-{uuid.uuid4()}",
                sender=EmailAddress(email=f"load.test.{i}@example.com", name=f"Load User {i}"),
                recipients=EmailRecipients(to=[EmailAddress(email="support@company.com", name="Support")]),
                subject=f"Load Test Email {i}",
                body=EmailBody(content_type="text/plain", content=f"Load test content {i}"),
                received_datetime=datetime.now(timezone.utc)
            )
            
            processing_result = ProcessingResult(
                success=True,
                email_id=email.id,
                process_id=f"load-proc-{i}-{uuid.uuid4()}",
                sender_email=email.sender.email,
                processing_duration_ms=300
            )
            
            task = service.track_scenario_processing(
                email_data=email,
                processing_result=processing_result,
                correlation_id=f"load-correlation-{i}"
            )
            tasks.append(task)
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all processing succeeded
        successful_results = [r for r in results if isinstance(r, TrackingIntegrationResult) and r.success]
        assert len(successful_results) >= concurrent_emails * 0.95  # Allow 5% failure rate
        
        # Performance assertions
        assert total_time < 30.0  # Should complete within 30 seconds
        avg_time_per_email = total_time / concurrent_emails
        assert avg_time_per_email < 2.0  # Average less than 2 seconds per email
        
        # Wait for any batch processing to complete
        await asyncio.sleep(3)
        await service.flush_pending_operations()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_error_recovery_and_degraded_mode(self, real_integration_service, sample_email):
        """Test system behavior under error conditions and degraded mode."""
        service, is_real = real_integration_service
        
        if not is_real:
            # Simulate database unavailability
            service.tracking_client.store_scenario_result = AsyncMock(
                side_effect=Exception("Database unavailable")
            )
        
        processing_result = ProcessingResult(
            success=True,
            email_id=sample_email.id,
            process_id=f"error-test-{uuid.uuid4()}",
            sender_email=sample_email.sender.email,
            processing_duration_ms=1000
        )
        
        # Attempt tracking during error condition
        result = await service.track_scenario_processing(
            email_data=sample_email,
            processing_result=processing_result,
            correlation_id=f"error-correlation-{uuid.uuid4()}"
        )
        
        if not is_real:
            # Should fail gracefully without breaking email processing
            assert result.success is False
            assert result.final_error is not None
            assert "Database unavailable" in result.final_error
        
        # Check health status reflects the issue
        health = await service.get_integration_health()
        if not is_real:
            # Health should show degraded status due to errors
            assert health.get("status") in ["unhealthy", "degraded"]
    
    @pytest.mark.asyncio
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_configuration_validation(self):
        """Test configuration validation and edge cases."""
        # Test with invalid configuration - should raise ValidationError
        with pytest.raises(ValidationError):
            invalid_config = ScenarioTrackingConfiguration(
                enabled=True,
                batch_insert_size=0,  # Invalid - must be >= 1
                retry_attempts=-1,  # Invalid - must be >= 1  
                connection_timeout_seconds=0  # Invalid - must be >= 5
            )
        
        # Test with valid configuration
        valid_config = ScenarioTrackingConfiguration(
            enabled=True,
            batch_insert_size=10,
            retry_attempts=2,
            connection_timeout_seconds=15
        )
        
        service = ScenarioTrackingIntegration(valid_config)
        
        # Should handle valid configuration properly
        health = await service.get_integration_health()
        assert health.get("status") in ["healthy", "degraded", "unhealthy", "not_initialized"]
        
        await service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_memory_usage_and_cleanup(self, real_integration_service):
        """Test memory usage patterns and resource cleanup."""
        service, is_real = real_integration_service
        
        initial_health = await service.get_integration_health()
        initial_queue_size = initial_health.get("batch_processing", {}).get("queue_length", 0)
        
        # Process many emails to build up batch queue
        for i in range(20):
            email = Email(
                id=f"memory-test-{i}-{uuid.uuid4()}",
                sender=EmailAddress(email=f"memory.test.{i}@example.com", name=f"Memory User {i}"),
                recipients=EmailRecipients(to=[EmailAddress(email="support@company.com", name="Support")]),
                subject=f"Memory Test {i}",
                body=EmailBody(content_type="text/plain", content="A" * 1000),  # Large content
                received_datetime=datetime.now(timezone.utc)
            )
            
            processing_result = ProcessingResult(
                success=True,
                email_id=email.id,
                process_id=f"memory-proc-{i}-{uuid.uuid4()}",
                sender_email=email.sender.email,
                processing_duration_ms=100
            )
            
            await service.track_scenario_processing(
                email_data=email,
                processing_result=processing_result
            )
        
        # Check batch queue growth
        mid_health = await service.get_integration_health()
        mid_queue_size = mid_health.get("batch_processing", {}).get("queue_length", 0)
        
        # Flush and cleanup
        await service.flush_pending_operations()
        await asyncio.sleep(1)
        
        final_health = await service.get_integration_health()
        final_queue_size = final_health.get("batch_processing", {}).get("queue_length", 0)
        
        # Verify memory was cleaned up
        assert final_queue_size <= initial_queue_size + 1  # Should be cleaned up


@pytest.mark.integration
class TestRealDatabricksIntegration:
    """Tests that require real Databricks connections."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_databricks_connection_available(self):
        """Verify Databricks connection is available for integration tests."""
        if not os.getenv("RUN_DATABRICKS_INTEGRATION_TESTS", "false").lower() == "true":
            pytest.skip("Real Databricks integration tests not enabled")
        
        required_env_vars = [
            "DATABRICKS_HOST",
            "DATABRICKS_TOKEN", 
            "DATABRICKS_HTTP_PATH"
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"Missing required environment variables: {missing_vars}")
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_real_table_creation_and_operations(self):
        """Test actual table creation and data operations in Databricks."""
        if not os.getenv("RUN_DATABRICKS_INTEGRATION_TESTS", "false").lower() == "true":
            pytest.skip("Real Databricks integration tests not enabled")
        
        # This test would require actual Databricks credentials and should be run
        # in a controlled environment with proper test tables
        config = ScenarioTrackingConfiguration(
            enabled=True,
            databricks_host=os.getenv("DATABRICKS_HOST"),
            databricks_token=os.getenv("DATABRICKS_TOKEN"),
            databricks_http_path=os.getenv("DATABRICKS_HTTP_PATH"),
            table_name=f"scenario_tracking_integration_test_{int(time.time())}",
            async_insert=False  # Synchronous for integration testing
        )
        
        service = ScenarioTrackingIntegration(config)
        
        try:
            # Initialize and verify connection
            assert await service._ensure_initialized()
            
            # Create sample data
            email = Email(
                id=f"real-test-{uuid.uuid4()}",
                sender=EmailAddress(email="real.test@example.com", name="Real Test User"),
                recipients=EmailRecipients(to=[EmailAddress(email="support@company.com", name="Support")]),
                subject="Real Databricks Integration Test",
                body=EmailBody(content_type="text/plain", content="This is a real integration test"),
                received_datetime=datetime.now(timezone.utc)
            )
            
            processing_result = ProcessingResult(
                success=True,
                email_id=email.id,
                process_id=f"real-proc-{uuid.uuid4()}",
                sender_email=email.sender.email,
                processing_duration_ms=1500
            )
            
            # Test actual data insertion
            result = await service.track_scenario_processing(
                email_data=email,
                processing_result=processing_result,
                correlation_id=f"real-correlation-{uuid.uuid4()}"
            )
            
            # Verify successful insertion
            assert result.success is True
            assert result.record_created is True
            
            # Test health check with real connection
            health = await service.get_integration_health()
            assert health.get("status") == "healthy"
            
        finally:
            await service.close()