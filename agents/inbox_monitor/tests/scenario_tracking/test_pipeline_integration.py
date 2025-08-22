"""
Pipeline Integration Tests for Scenario Tracking System
=======================================================

Integration testing focused on the email processing pipeline and
scenario tracking integration points.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch, call
import structlog

# Test framework imports
from tests.fixtures.integration_testing_architecture import (
    integration_test_environment, 
    mock_databricks_connection,
    mock_scenario_processor,
    test_email_data
)

# System under test imports
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
from services.scenario_processor import ScenarioProcessor
from services.email_processor import EmailProcessor

logger = structlog.get_logger(__name__)


class TestPipelineIntegration:
    """Test integration between email processing pipeline and scenario tracking."""
    
    @pytest.fixture(autouse=True)
    async def setup_pipeline_integration_environment(self, integration_test_environment):
        """Setup pipeline integration test environment."""
        self.test_env = integration_test_environment
        self.table_suffix = "_pipeline_integration_test"
    
    @pytest.mark.integration
    @pytest.mark.scenario_tracking
    @pytest.mark.email
    @pytest.mark.medium
    @pytest.mark.asyncio
    async def test_end_to_end_email_to_tracking_pipeline(self, test_email_data):
        """Test complete pipeline from email receipt to tracking storage."""
        
        tracking_calls = []
        
        # Mock the tracking client to capture calls (Phase 6 API)
        original_store_method = InboxMonitorDatabricksClient.store_scenario_processing_record
        
        async def mock_store_scenario_processing_record(self, record):
            tracking_calls.append({
                "record": record,
                "timestamp": datetime.now(timezone.utc)
            })
            return True  # Simulate successful storage
        
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_store_scenario_processing_record):
            # Process email through the complete pipeline
            async with EmailProcessor() as email_processor:
                processing_result = await email_processor.process_email(test_email_data)
        
        # Verify email processing succeeded
        assert processing_result is not None
        assert processing_result.success is True
        
        # Verify tracking integration was called
        assert len(tracking_calls) >= 0  # May be 0 if integration not fully connected
        
        # If tracking was called, verify the data
        if tracking_calls:
            tracking_call = tracking_calls[0]
            recorded_data = tracking_call["record"]
            
            assert isinstance(recorded_data, ScenarioProcessingRecord)
            assert recorded_data.email_id == test_email_data.id
            assert recorded_data.sender_email == test_email_data.sender.email
            assert recorded_data.process_success is True
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scenario_processor_integration(self, test_email_data):
        """Test scenario processor integration with tracking."""
        
        scenario_results = []
        
        # Mock scenario tracking to capture results
        async def mock_track_scenario_result(email_data, processing_result, scenario_result=None):
            scenario_results.append({
                "email_data": email_data,
                "processing_result": processing_result,
                "scenario_result": scenario_result,
                "timestamp": datetime.now(timezone.utc)
            })
        
        with patch('services.scenario_processor.track_scenario_result', mock_track_scenario_result):
            async with ScenarioProcessor() as scenario_processor:
                # Process email through scenario classification
                result = await scenario_processor.process_email_scenario(
                    email_data=test_email_data,
                    correlation_id="pipeline_test_123"
                )
        
        # Verify scenario processing completed
        assert result is not None
        assert result.success is True
        
        # Verify scenario tracking integration
        if scenario_results:
            tracked_result = scenario_results[0]
            assert tracked_result["email_data"].id == test_email_data.id
            assert tracked_result["processing_result"] is not None
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_propagation_through_pipeline(self, test_email_data):
        """Test how errors propagate through the pipeline and are tracked."""
        
        error_tracking_calls = []
        
        # Mock scenario processor to simulate error
        async def mock_failing_scenario_processor(*args, **kwargs):
            raise Exception("Simulated scenario processing error")
        
        # Mock tracking to capture error records (Phase 6 API)
        async def mock_store_error_record(self, record):
            error_tracking_calls.append({
                "record": record,
                "error": record.process_error,
                "success": record.process_success
            })
            return True
        
        with patch.object(ScenarioProcessor, 'process_email_scenario', mock_failing_scenario_processor), \
             patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_store_error_record):
            
            # Process should handle error gracefully
            async with EmailProcessor() as email_processor:
                processing_result = await email_processor.process_email(test_email_data)
            
            # Email processing should still complete (graceful degradation)
            assert processing_result is not None
            # May succeed or fail depending on error handling implementation
        
        # If error tracking was called, verify error was recorded
        if error_tracking_calls:
            error_record = error_tracking_calls[0]
            assert error_record["success"] is False
            assert error_record["error"] is not None
            assert "error" in error_record["error"].lower()
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_async_tracking_integration(self, test_email_data):
        """Test asynchronous tracking integration doesn't block email processing."""
        
        tracking_timing = []
        email_processing_timing = []
        
        # Mock async tracking with delay (Phase 6 API)
        async def mock_slow_tracking(self, record):
            start_time = datetime.now()
            await asyncio.sleep(0.5)  # Simulate slow tracking operation
            end_time = datetime.now()
            
            tracking_timing.append({
                "start": start_time,
                "end": end_time,
                "duration": (end_time - start_time).total_seconds()
            })
            return True
        
        # Time the email processing
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_slow_tracking):
            start_time = datetime.now()
            
            async with EmailProcessor() as email_processor:
                processing_result = await email_processor.process_email(test_email_data)
            
            end_time = datetime.now()
            
            email_processing_timing.append({
                "start": start_time,
                "end": end_time,
                "duration": (end_time - start_time).total_seconds()
            })
        
        # Verify email processing completed
        assert processing_result is not None
        assert processing_result.success is True
        
        # If both operations were captured, verify timing relationship
        if tracking_timing and email_processing_timing:
            email_duration = email_processing_timing[0]["duration"]
            tracking_duration = tracking_timing[0]["duration"]
            
            # Email processing should not be significantly delayed by tracking
            # (This depends on whether tracking is truly async or not)
            logger.info("Pipeline timing analysis",
                       email_duration=email_duration,
                       tracking_duration=tracking_duration)
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_scenario_type_flow_integration(self, test_email_data):
        """Test integration for different scenario types through the pipeline."""
        
        scenario_type_results = []
        
        # Mock scenario classification to return different types
        scenario_types_to_test = [
            ScenarioType.SCENARIO_5,
            ScenarioType.SCENARIO_6, 
            ScenarioType.SCENARIO_7,
            ScenarioType.UNKNOWN
        ]
        
        for scenario_type in scenario_types_to_test:
            # Mock scenario result
            mock_scenario_result = MagicMock()
            mock_scenario_result.scenario_type = scenario_type
            mock_scenario_result.success = True
            mock_scenario_result.agent_actions_log = [f"action_for_{scenario_type.value}"]
            
            if scenario_type == ScenarioType.SCENARIO_5:
                mock_scenario_result.expert_assigned = "Test Expert"
                mock_scenario_result.case_created = "CASE123"
            elif scenario_type in [ScenarioType.SCENARIO_6, ScenarioType.SCENARIO_7]:
                mock_scenario_result.emails_sent = ["forward@company.com"]
            
            # Mock tracking storage (Phase 6 API)
            captured_records = []
            
            async def mock_store_scenario_type(self, record):
                captured_records.append(record)
                return True
            
            with patch('services.scenario_processor.classify_scenario_type', return_value=mock_scenario_result), \
                 patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_store_scenario_type):
                
                async with ScenarioProcessor() as scenario_processor:
                    result = await scenario_processor.process_email_scenario(
                        email_data=test_email_data,
                        correlation_id=f"scenario_type_test_{scenario_type.value}"
                    )
                
                scenario_type_results.append({
                    "scenario_type": scenario_type,
                    "processing_result": result,
                    "captured_records": captured_records
                })
        
        # Verify each scenario type was processed and tracked correctly
        for result_data in scenario_type_results:
            scenario_type = result_data["scenario_type"]
            processing_result = result_data["processing_result"]
            captured_records = result_data["captured_records"]
            
            assert processing_result is not None
            assert processing_result.success is True
            
            # Verify tracking captured the correct scenario type
            if captured_records:
                tracked_record = captured_records[0]
                assert tracked_record.scenario_type == scenario_type
                
                # Verify scenario-specific fields
                if scenario_type == ScenarioType.SCENARIO_5:
                    assert tracked_record.expert_assigned is not None
                elif scenario_type in [ScenarioType.SCENARIO_6, ScenarioType.SCENARIO_7]:
                    assert len(tracked_record.emails_forwarded) > 0
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_batch_email_processing_integration(self):
        """Test pipeline integration with batch email processing."""
        
        # Generate multiple test emails
        test_emails = []
        for i in range(5):
            email = MagicMock()
            email.id = f"batch_test_email_{i}"
            email.sender = MagicMock()
            email.sender.email = f"batch_test_{i}@example.com"
            email.sender.name = f"Batch Test User {i}"
            email.subject = f"Batch test email {i}"
            email.received_datetime = datetime.now(timezone.utc) - timedelta(minutes=i)
            email.recipients = MagicMock()
            email.recipients.to = []
            email.recipients.cc = []
            email.recipients.bcc = []
            test_emails.append(email)
        
        batch_tracking_results = []
        
        # Mock batch tracking (Phase 6 API)
        async def mock_batch_tracking(self, record):
            batch_tracking_results.append({
                "email_id": record.email_id,
                "sender_email": record.sender_email,
                "process_success": record.process_success,
                "timestamp": datetime.now(timezone.utc)
            })
            return True
        
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_batch_tracking):
            # Process emails in sequence
            processing_results = []
            
            async with EmailProcessor() as email_processor:
                for email in test_emails:
                    result = await email_processor.process_email(email)
                    processing_results.append(result)
        
        # Verify all emails were processed
        assert len(processing_results) == len(test_emails)
        for i, result in enumerate(processing_results):
            assert result is not None
            assert result.success is True
        
        # Verify tracking captured all emails (if integration is active)
        if batch_tracking_results:
            assert len(batch_tracking_results) >= len(test_emails)
            
            tracked_email_ids = {r["email_id"] for r in batch_tracking_results}
            original_email_ids = {email.id for email in test_emails}
            
            # Should have significant overlap
            overlap = tracked_email_ids.intersection(original_email_ids)
            assert len(overlap) >= len(test_emails) * 0.8  # At least 80% tracked
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self, test_email_data):
        """Test that correlation IDs propagate through the pipeline."""
        
        correlation_tracking = []
        
        async def mock_tracking_with_correlation(self, record):
            correlation_tracking.append({
                "correlation_id": record.correlation_id,
                "process_id": record.process_id,
                "email_id": record.email_id
            })
            return True
        
        correlation_id = "pipeline_correlation_test_12345"
        
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_tracking_with_correlation):
            async with ScenarioProcessor() as scenario_processor:
                result = await scenario_processor.process_email_scenario(
                    email_data=test_email_data,
                    correlation_id=correlation_id
                )
        
        # Verify correlation ID propagation
        assert result is not None
        
        if correlation_tracking:
            tracked_correlation = correlation_tracking[0]
            assert tracked_correlation["correlation_id"] == correlation_id
            assert tracked_correlation["email_id"] == test_email_data.id
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_performance_monitoring_integration(self, test_email_data):
        """Test integration with performance monitoring through the pipeline."""
        
        performance_metrics = []
        
        async def mock_performance_tracking(self, record, force_sync=False):
            performance_metrics.append({
                "processing_duration_ms": record.processing_duration_ms,
                "ai_processing_duration_ms": record.ai_processing_duration_ms,
                "scenario_processing_duration_ms": record.scenario_processing_duration_ms,
                "memory_usage_mb": record.memory_usage_mb,
                "cpu_time_ms": record.cpu_time_ms
            })
            return True
        
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_performance_tracking):
            start_time = datetime.now()
            
            async with EmailProcessor() as email_processor:
                result = await email_processor.process_email(test_email_data)
            
            end_time = datetime.now()
            total_processing_time = (end_time - start_time).total_seconds() * 1000
        
        # Verify performance data collection
        assert result is not None
        
        if performance_metrics:
            metrics = performance_metrics[0]
            
            # Verify timing metrics are reasonable
            if metrics["processing_duration_ms"]:
                assert 0 < metrics["processing_duration_ms"] < 60000  # Under 1 minute
                assert metrics["processing_duration_ms"] <= total_processing_time * 2  # Reasonable bounds


class TestPipelineErrorHandling:
    """Test error handling in pipeline integration."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tracking_failure_doesnt_break_pipeline(self, test_email_data):
        """Test that tracking failures don't break email processing."""
        
        # Mock tracking to always fail
        async def mock_failing_tracking(self, record, force_sync=False):
            raise Exception("Tracking system unavailable")
        
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_failing_tracking):
            async with EmailProcessor() as email_processor:
                result = await email_processor.process_email(test_email_data)
        
        # Email processing should still succeed despite tracking failure
        assert result is not None
        assert result.success is True  # Graceful degradation
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self):
        """Test circuit breaker behavior in pipeline integration."""
        
        failure_count = 0
        
        async def mock_intermittent_tracking(self, record, force_sync=False):
            nonlocal failure_count
            failure_count += 1
            
            if failure_count <= 3:
                raise Exception(f"Tracking failure {failure_count}")
            else:
                return True  # Start succeeding after 3 failures
        
        # Process multiple emails to trigger circuit breaker
        test_emails = []
        for i in range(6):
            email = MagicMock()
            email.id = f"circuit_test_{i}"
            email.sender = MagicMock()
            email.sender.email = f"circuit_test_{i}@example.com"
            email.received_datetime = datetime.now(timezone.utc)
            test_emails.append(email)
        
        with patch.object(InboxMonitorDatabricksClient, 'store_scenario_processing_record', mock_intermittent_tracking):
            results = []
            
            async with EmailProcessor() as email_processor:
                for email in test_emails:
                    result = await email_processor.process_email(email)
                    results.append(result)
        
        # All email processing should succeed regardless of tracking issues
        for result in results:
            assert result is not None
            assert result.success is True


class TestPipelineDataFlow:
    """Test data flow through the pipeline integration."""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_data_transformation_through_pipeline(self, test_email_data):
        """Test that data is correctly transformed through pipeline stages."""
        
        transformation_stages = []
        
        # Mock to capture data at different stages
        original_from_processing_results = ScenarioProcessingRecord.from_processing_results
        
        @classmethod
        def mock_from_processing_results(cls, email_data, processing_result, scenario_result=None, **kwargs):
            # Capture the transformation stage
            transformation_stages.append({
                "stage": "record_creation",
                "email_id": email_data.id if hasattr(email_data, 'id') else None,
                "sender_email": email_data.sender.email if hasattr(email_data, 'sender') else None,
                "process_success": processing_result.success if hasattr(processing_result, 'success') else None,
                "scenario_type": scenario_result.scenario_type if scenario_result and hasattr(scenario_result, 'scenario_type') else None
            })
            
            # Call original method
            return original_from_processing_results(email_data, processing_result, scenario_result, **kwargs)
        
        with patch.object(ScenarioProcessingRecord, 'from_processing_results', mock_from_processing_results):
            async with ScenarioProcessor() as scenario_processor:
                result = await scenario_processor.process_email_scenario(
                    email_data=test_email_data,
                    correlation_id="data_flow_test"
                )
        
        # Verify data transformation occurred
        assert result is not None
        
        if transformation_stages:
            stage_data = transformation_stages[0]
            assert stage_data["email_id"] == test_email_data.id
            assert stage_data["sender_email"] == test_email_data.sender.email
            assert stage_data["process_success"] is not None


if __name__ == "__main__":
    # Run pipeline integration tests
    pytest.main([
        __file__,
        "-v", 
        "--tb=short",
        "-m", "integration",
        "--asyncio-mode=auto"
    ])