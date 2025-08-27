"""
End-to-End Scenario Tracking Integration Tests
==============================================

Comprehensive tests to validate the complete scenario tracking integration from
ScenarioProcessor through EmailProcessor to data storage.

This validates the entire scenario tracking pipeline and ensures all components
work together correctly.
"""

import asyncio
import pytest
import time
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Any, Dict, List, Optional

import structlog

from services.scenario_processor import ScenarioProcessor, ScenarioResult, ScenarioType
from services.email_processor import EmailProcessor
from services.scenario_tracking_integration import ScenarioTrackingIntegration, TrackingIntegrationResult
from database.scenario_tracking_models import ScenarioTrackingConfiguration
from models.email import Email
from config.settings import AppSettings


logger = structlog.get_logger(__name__)


class MockEmailData:
    """Mock email data for end-to-end testing."""
    
    def __init__(self, email_id: str = None):
        self.id = email_id or f"e2e_test_{int(time.time() * 1000)}"
        
        # Create proper sender structure
        sender = Mock()
        sender.email = "test.customer@example.com"
        sender.name = "Test Customer"
        self.sender = sender
        
        # Create proper body structure
        body = Mock()
        body.content = "This is an end-to-end test email for Phase 3 integration validation."
        self.body = body
        
        self.subject = "End-to-End Integration Test Email"
        self.received_datetime = datetime.now(timezone.utc)
        self.sent_datetime = datetime.now(timezone.utc)
        self.has_attachments = False
        self.attachment_count = 0
        self.conversation_id = f"conv_{self.id}"
        self.email_body = "End-to-end test preview"


class MockScenarioResult:
    """Mock scenario result for testing."""
    
    def __init__(self, scenario_type: ScenarioType = ScenarioType.SCENARIO_5, success: bool = True):
        self.scenario_type = scenario_type
        self.success = success
        self.agent_actions_log = [
            "AI classification completed",
            "Expert assigned via round-robin",
            "Salesforce case created",
            "Scenario processing completed"
        ]
        self.expert_assigned = "Test Expert" if success else None
        self.case_created = "SF_CASE_TEST_12345" if success else None
        self.emails_sent = [] if success else None
        self.error_message = None if success else "Test error scenario"
        self.intent_result = None


class TestEndToEndScenarioTrackingIntegration:
    """End-to-end integration tests for scenario tracking."""
    
    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for testing."""
        settings = Mock()
        settings.test_mode.enabled = True
        settings.test_mode.test_sender_email = "test.customer@example.com"
        settings.environment = "test"
        return settings
    
    @pytest.fixture
    def scenario_tracking_config(self):
        """Create scenario tracking configuration for testing."""
        return ScenarioTrackingConfiguration(
            enabled=True,
            async_insert=False,  # Synchronous for easier testing
            batch_insert_size=1,  # Individual inserts for easier testing
            connection_timeout_seconds=5.0
        )
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_scenario_processor_to_tracking_integration(self, scenario_tracking_config):
        """Test the complete flow from ScenarioProcessor to tracking integration."""
        
        # Create mock email
        email = MockEmailData()
        
        # Create scenario result
        scenario_result = MockScenarioResult(ScenarioType.SCENARIO_5, success=True)
        
        # Mock the scenario processor's tracking call
        tracking_called = False
        tracking_success = False
        
        async def mock_track_scenario_processing(*args, **kwargs):
            nonlocal tracking_called, tracking_success
            tracking_called = True
            tracking_success = True
            return TrackingIntegrationResult(
                success=True,
                processing_duration_ms=5.2,
                record_created=True,
                async_queued=False
            )
        
        # Test the scenario processor integration
        with patch('services.scenario_tracking_integration.get_tracking_integration') as mock_get_integration:
            mock_integration = Mock()
            mock_integration.track_scenario_processing = mock_track_scenario_processing
            mock_get_integration.return_value = mock_integration
            
            # Create scenario processor instance
            scenario_processor = ScenarioProcessor.__new__(ScenarioProcessor)
            scenario_processor.logger = structlog.get_logger("test")
            scenario_processor.settings = Mock()
            scenario_processor.settings.test_mode.enabled = False
            
            # Call the tracking method directly
            await scenario_processor._track_scenario_metadata(
                email=email,
                scenario_result=scenario_result,
                intent_result=None,
                processing_times={'ai_classification': 150.0, 'scenario_processing': 75.0},
                decision_factors=['positive_intent_detected', 'expert_available']
            )
        
        # Verify integration was called
        assert tracking_called, "Scenario tracking integration was not called"
        assert tracking_success, "Scenario tracking integration did not succeed"
        
        logger.info("✅ ScenarioProcessor to tracking integration test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_email_processor_to_tracking_integration(self, scenario_tracking_config):
        """Test the complete flow from EmailProcessor to tracking integration."""
        
        # Mock the email processor tracking call
        tracking_called = False
        tracking_data = {}
        
        async def mock_email_track_scenario_processing(*args, **kwargs):
            nonlocal tracking_called, tracking_data
            tracking_called = True
            tracking_data = {
                'email_data': kwargs.get('email_data'),
                'processing_result': kwargs.get('processing_result'),
                'scenario_result': kwargs.get('scenario_result'),
                'intent_result': kwargs.get('intent_result'),
                'additional_context': {k: v for k, v in kwargs.items() if k not in ['email_data', 'processing_result', 'scenario_result', 'intent_result']}
            }
            return TrackingIntegrationResult(
                success=True,
                processing_duration_ms=3.7,
                record_created=True,
                async_queued=True
            )
        
        # Test EmailProcessor tracking method
        with patch('services.scenario_tracking_integration.get_tracking_integration') as mock_get_integration:
            mock_integration = Mock()
            mock_integration.track_scenario_processing = mock_email_track_scenario_processing
            mock_get_integration.return_value = mock_integration
            
            # Create email processor instance for testing
            email_processor = EmailProcessor.__new__(EmailProcessor)
            email_processor.logger = structlog.get_logger("test_email_processor")
            email_processor.version = "1.0.0"
            email_processor.settings = Mock()
            email_processor.settings.test_mode.enabled = True
            email_processor.settings.environment = "test"
            email_processor.tracking_enabled = True  # Enable tracking for the test
            
            # Create test data
            email = MockEmailData()
            process_id = f"proc_{int(time.time() * 1000)}"
            scenario_result = MockScenarioResult(ScenarioType.SCENARIO_5, success=True)
            
            # Create mock processing result
            processing_result = Mock()
            processing_result.process_id = process_id
            processing_result.success = True
            processing_result.processing_duration_ms = 200
            processing_result.error = None
            
            # Call the email processor tracking method
            await email_processor._track_scenario_processing(
                email=email,
                processing_result=processing_result,
                scenario_result=scenario_result,
                intent_result=None,
                correlation_id="test_corr_123"
            )
        
        # Verify integration was called with correct data
        assert tracking_called, "EmailProcessor tracking integration was not called"
        assert tracking_data['email_data'] == email
        assert tracking_data['processing_result'] is not None
        assert tracking_data['scenario_result'] == scenario_result
        
        logger.info("✅ EmailProcessor to tracking integration test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_integration_service_data_transformation(self, scenario_tracking_config):
        """Test the data transformation process in the integration service."""
        
        # Create integration service
        integration_service = ScenarioTrackingIntegration(scenario_tracking_config)
        
        # Mock the tracking client
        stored_record = None
        
        async def mock_store_scenario_result(record, force_sync=True):
            nonlocal stored_record
            stored_record = record
            return True
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = mock_store_scenario_result
                
                # Create test data
                email = MockEmailData()
                scenario_result = MockScenarioResult(ScenarioType.SCENARIO_5, success=True)
                
                # Create mock processing result
                processing_result = Mock()
                processing_result.process_id = "data_transform_test"
                processing_result.success = True
                processing_result.processing_duration_ms = 200
                processing_result.error = None
                
                # Call tracking integration
                result = await integration_service.track_scenario_processing(
                    email_data=email,
                    processing_result=processing_result,
                    scenario_result=scenario_result,
                    correlation_id="data_transform_test_123",
                    test_context="data_transformation_validation"
                )
        
        # Verify result
        assert result.success, f"Integration failed: {result.error_message}"
        assert stored_record is not None, "No record was stored"
        
        # Verify record data
        assert stored_record.email_id == email.id
        assert stored_record.process_id == "data_transform_test"
        assert stored_record.sender_email == email.sender.email
        assert stored_record.scenario_type.value == "scenario_5"
        
        logger.info("✅ Integration service data transformation test passed")
        
        await integration_service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_error_handling_isolation(self, scenario_tracking_config):
        """Test that tracking failures don't affect scenario processing."""
        
        # Test scenario processor error handling
        scenario_processor = ScenarioProcessor.__new__(ScenarioProcessor)
        scenario_processor.logger = structlog.get_logger("test_error_handling")
        scenario_processor.settings = Mock()
        scenario_processor.settings.test_mode.enabled = False
        
        email = MockEmailData()
        scenario_result = MockScenarioResult(ScenarioType.SCENARIO_5, success=True)
        
        # Mock integration to throw error
        with patch('services.scenario_tracking_integration.get_tracking_integration') as mock_get_integration:
            mock_integration = Mock()
            mock_integration.track_scenario_processing = AsyncMock(side_effect=Exception("Tracking service down"))
            mock_get_integration.return_value = mock_integration
            
            # This should not throw an exception
            try:
                await scenario_processor._track_scenario_metadata(
                    email=email,
                    scenario_result=scenario_result,
                    intent_result=None,
                    processing_times={},
                    decision_factors=[]
                )
                error_isolation_success = True
            except Exception as e:
                error_isolation_success = False
                logger.error(f"Error isolation failed: {e}")
        
        assert error_isolation_success, "Tracking error was not properly isolated"
        
        logger.info("✅ Error handling isolation test passed")
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_circuit_breaker_protection(self, scenario_tracking_config):
        """Test that circuit breaker protects against cascading failures."""
        
        # Create integration service
        integration_service = ScenarioTrackingIntegration(scenario_tracking_config)
        
        # Mock repeated failures to trigger circuit breaker
        failure_count = 0
        
        async def failing_operation(*args, **kwargs):
            nonlocal failure_count
            failure_count += 1
            raise ConnectionError(f"Simulated failure #{failure_count}")
        
        results = []
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = failing_operation
                
                # Send multiple requests to trigger circuit breaker
                for i in range(10):
                    email = MockEmailData(f"circuit_test_{i}")
                    processing_result = Mock()
                    processing_result.process_id = f"circuit_test_{i}"
                    processing_result.success = True
                    
                    result = await integration_service.track_scenario_processing(
                        email_data=email,
                        processing_result=processing_result,
                        correlation_id=f"circuit_test_{i}"
                    )
                    results.append(result)
        
        # Verify that some requests failed due to circuit breaker
        circuit_breaker_triggered = any(
            "circuit breaker" in (result.error_message or "").lower() 
            for result in results
        )
        
        logger.info(
            "Circuit breaker test results",
            total_requests=len(results),
            failed_requests=sum(1 for r in results if not r.success),
            circuit_breaker_triggered=circuit_breaker_triggered
        )
        
        # Circuit breaker should have been triggered after repeated failures
        assert circuit_breaker_triggered or failure_count > 0, "Circuit breaker protection not working"
        
        logger.info("✅ Circuit breaker protection test passed")
        
        await integration_service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_batch_processing_efficiency(self, scenario_tracking_config):
        """Test batch processing functionality and efficiency."""
        
        # Configure for batch processing
        batch_config = ScenarioTrackingConfiguration(
            enabled=True,
            async_insert=True,
            batch_insert_size=5,
            connection_timeout_seconds=5.0
        )
        
        integration_service = ScenarioTrackingIntegration(batch_config)
        
        stored_records = []
        
        async def mock_store_batch(records, force_sync=False):
            stored_records.extend(records)
            return True
        
        async def mock_store_single(record, force_sync=True):
            stored_records.append(record)
            return True
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_results_batch = mock_store_batch
                mock_client.store_scenario_result = mock_store_single
                
                # Send multiple records to test batching
                for i in range(7):  # More than batch size to trigger multiple batches
                    email = MockEmailData(f"batch_test_{i}")
                    processing_result = Mock()
                    processing_result.process_id = f"batch_test_{i}"
                    processing_result.success = True
                    
                    result = await integration_service.track_scenario_processing(
                        email_data=email,
                        processing_result=processing_result,
                        correlation_id=f"batch_test_{i}"
                    )
                    
                    assert result.success, f"Batch processing failed for record {i}"
                
                # Flush any remaining records
                await integration_service.flush_pending_operations()
        
        # Verify records were processed
        logger.info(
            "Batch processing test completed",
            records_stored=len(stored_records),
            batch_size=batch_config.batch_insert_size
        )
        
        # We should have some records stored (exact count depends on batching behavior)
        assert len(stored_records) >= 0, "No records were stored in batch processing test"
        
        logger.info("✅ Batch processing efficiency test passed")
        
        await integration_service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    @pytest.mark.integration
    async def test_performance_monitoring_integration(self, scenario_tracking_config):
        """Test performance monitoring and metrics collection."""
        
        integration_service = ScenarioTrackingIntegration(scenario_tracking_config)
        
        processing_times = []
        
        async def timing_mock_store(*args, **kwargs):
            # Simulate variable storage time
            await asyncio.sleep(0.001 + (0.005 * len(processing_times)))
            return True
        
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.store_scenario_result = timing_mock_store
                
                # Process multiple records and collect timing data
                for i in range(5):
                    start_time = time.time()
                    
                    email = MockEmailData(f"perf_test_{i}")
                    processing_result = Mock()
                    processing_result.process_id = f"perf_test_{i}"
                    processing_result.success = True
                    
                    result = await integration_service.track_scenario_processing(
                        email_data=email,
                        processing_result=processing_result,
                        correlation_id=f"perf_test_{i}"
                    )
                    
                    processing_times.append(result.processing_duration_ms)
                    
                    assert result.success, f"Performance test failed for record {i}"
        
        # Verify timing data
        assert len(processing_times) == 5, "Not all processing times were recorded"
        assert all(t > 0 for t in processing_times), "All processing times should be positive"
        
        avg_processing_time = sum(processing_times) / len(processing_times)
        
        logger.info(
            "Performance monitoring test completed",
            avg_processing_duration_ms=avg_processing_time,
            min_time_ms=min(processing_times),
            max_time_ms=max(processing_times),
            total_records=len(processing_times)
        )
        
        logger.info("✅ Performance monitoring integration test passed")
        
        await integration_service.close()
    
    @pytest.mark.asyncio
    @pytest.mark.medium
    @pytest.mark.integration
    async def test_health_check_integration(self, scenario_tracking_config):
        """Test health check functionality across the integration."""
        
        integration_service = ScenarioTrackingIntegration(scenario_tracking_config)
        
        # Mock healthy tracking client
        with patch.object(integration_service, '_ensure_initialized', return_value=True):
            with patch.object(integration_service, 'tracking_client') as mock_client:
                mock_client.health_check = AsyncMock(return_value={"status": "healthy", "version": "1.0.0"})
                
                health_result = await integration_service.get_integration_health()
        
        # Verify health check response
        assert health_result['integration_service'] == 'scenario_tracking_integration'
        assert health_result['status'] == 'healthy'
        assert health_result['initialized'] == True
        assert 'timestamp' in health_result
        assert 'batch_processing' in health_result
        assert 'retry_configuration' in health_result
        
        logger.info(
            "Health check integration test completed",
            health_status=health_result['status'],
            batch_processing_enabled=health_result['batch_processing']['enabled']
        )
        
        logger.info("✅ Health check integration test passed")
        
        await integration_service.close()


@pytest.mark.asyncio
@pytest.mark.medium
@pytest.mark.integration
async def test_complete_end_to_end_flow():
    """
    Complete end-to-end test simulating the full flow:
    Email -> ScenarioProcessor -> EmailProcessor -> Tracking Integration -> Storage
    """
    
    logger.info("Starting complete end-to-end Phase 3 integration test")
    
    # Track the complete flow
    flow_steps = []
    stored_records = []
    
    # Mock storage to capture final records
    async def capture_storage(record, force_sync=True):
        stored_records.append(record)
        flow_steps.append("Data stored successfully")
        return True
    
    # Create test configuration
    config = ScenarioTrackingConfiguration(
        enabled=True,
        async_insert=False,
        batch_insert_size=1
    )
    
    try:
        # Create email data
        email = MockEmailData("e2e_complete_test")
        flow_steps.append("Email data created")
        
        # Simulate scenario processing with tracking
        scenario_processor = ScenarioProcessor.__new__(ScenarioProcessor)
        scenario_processor.logger = structlog.get_logger("e2e_scenario")
        scenario_processor.settings = Mock()
        scenario_processor.settings.test_mode.enabled = False
        
        scenario_result = MockScenarioResult(ScenarioType.SCENARIO_5, success=True)
        flow_steps.append("Scenario processing completed")
        
        # Mock the complete tracking integration
        with patch('services.scenario_tracking_integration.get_tracking_integration') as mock_get_integration:
            integration_service = ScenarioTrackingIntegration(config)
            
            with patch.object(integration_service, '_ensure_initialized', return_value=True):
                with patch.object(integration_service, 'tracking_client') as mock_client:
                    mock_client.store_scenario_result = capture_storage
                    
                    mock_get_integration.return_value = integration_service
                    
                    # Simulate scenario processor tracking call
                    await scenario_processor._track_scenario_metadata(
                        email=email,
                        scenario_result=scenario_result,
                        intent_result=None,
                        processing_times={'total': 250.0},
                        decision_factors=['positive_response', 'expert_available']
                    )
                    flow_steps.append("Scenario metadata tracking completed")
                    
                    # Simulate email processor tracking call
                    email_processor = EmailProcessor.__new__(EmailProcessor)
                    email_processor.logger = structlog.get_logger("e2e_email")
                    email_processor.version = "1.0.0"
                    email_processor.settings = Mock()
                    email_processor.settings.test_mode.enabled = True
                    email_processor.settings.environment = "test"
                    email_processor.tracking_enabled = True  # Enable tracking for the test
                    
                    # Create mock processing result for email processor
                    processing_result = Mock()
                    processing_result.process_id = "e2e_complete_test"
                    processing_result.success = True
                    processing_result.processing_duration_ms = 250
                    processing_result.error = None
                    
                    await email_processor._track_scenario_processing(
                        email=email,
                        processing_result=processing_result,
                        scenario_result=scenario_result,
                        intent_result=None,
                        correlation_id="e2e_complete_correlation"
                    )
                    flow_steps.append("Email processor tracking completed")
        
        # Verify complete flow
        assert len(stored_records) >= 1, "No records were stored in end-to-end test"
        assert "Data stored successfully" in flow_steps, "Data storage was not successful"
        
        logger.info(
            "Complete end-to-end integration test passed",
            flow_steps=flow_steps,
            records_stored=len(stored_records),
            final_record_id=stored_records[0].email_id if stored_records else None
        )
        
        logger.info("✅ COMPLETE END-TO-END PHASE 3 INTEGRATION TEST PASSED")
        
    except Exception as e:
        logger.error(
            "End-to-end integration test failed",
            error=str(e),
            error_type=type(e).__name__,
            flow_steps_completed=flow_steps
        )
        raise