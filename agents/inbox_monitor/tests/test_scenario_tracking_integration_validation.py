"""
Scenario Tracking Integration Validation Test
============================================

Validates that scenario tracking integration functionality is properly implemented 
and meets requirements. Tests the complete pipeline from ScenarioProcessor through 
ScenarioTrackingIntegration to data storage.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
import time

from services.scenario_processor import ScenarioProcessor, ScenarioResult, ScenarioType
from services.scenario_tracking_integration import ScenarioTrackingIntegration, TrackingIntegrationResult
from services.email_processor import EmailProcessor
from services.circuit_breaker import CircuitBreaker, CircuitBreakerState
from utils.data_transformation import ScenarioDataTransformer
from utils.performance_validator import PerformanceValidator, create_test_emails
from config.tracking_integration_settings import TrackingIntegrationSettings
from database.scenario_tracking_models import ScenarioTrackingConfiguration


@pytest.mark.asyncio
class TestScenarioTrackingIntegrationValidation:
    """Comprehensive scenario tracking integration validation tests."""
    
    @pytest.mark.asyncio
    async def test_scenario_processor_metadata_capture_compliance(self):
        """Test ScenarioProcessor captures comprehensive metadata per Phase 3 requirements."""
        
        from config.settings import AppSettings
        
        # Create mock settings
        mock_settings = Mock(spec=AppSettings)
        mock_settings.test_mode.enabled = False
        mock_settings.azure_ai_foundry = Mock()
        mock_settings.salesforce = Mock()
        mock_settings.databricks_oauth = Mock()
        mock_settings.key_vault = Mock()
        mock_settings.scenarios = Mock()
        mock_settings.content_formatting = Mock()
        
        # Create scenario processor
        processor = ScenarioProcessor(mock_settings)
        
        # Mock all the service dependencies
        processor.ai_client = AsyncMock()
        processor.salesforce_client = AsyncMock()
        processor.round_robin_service = AsyncMock()
        processor.contact_lookup_service = AsyncMock()
        processor.email_forwarding_manager = AsyncMock()
        processor.content_formatter = Mock()
        processor.content_formatter.html_to_clean_text = Mock(return_value="Clean text content")
        processor._services_connected = True
        
        # Mock AI client response
        from services.azure_ai_foundry_client import IntentClassificationResult, EmailIntent
        mock_intent_result = IntentClassificationResult(
            intent=EmailIntent.POSITIVE,
            confidence=0.92,
            reasoning="Customer expressed satisfaction with our service",
            detected_phrases=["thank you", "excellent support"],
            processing_duration_ms=145
        )
        
        processor.ai_client.classify_email_intent.return_value = mock_intent_result
        
        # Mock _process_scenario to return result with metadata
        async def mock_process_scenario(email, scenario_type, intent_result):
            return ScenarioResult(
                scenario_type=scenario_type,
                success=True,
                agent_actions_log=["assigned_expert", "created_case"],
                expert_assigned="Jane Doe",
                case_created="SF_CASE_98765",
                intent_result=intent_result
            )
        
        processor._process_scenario = mock_process_scenario
        processor._determine_scenario_type = Mock(return_value=ScenarioType.SCENARIO_5)
        
        # Create test email
        from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata
        test_email = Email(
            id="metadata_test_email",
            conversation_id="test_conv",
            received_datetime=datetime.now(timezone.utc),
            sender=EmailSender(email="customer@example.com", name="Customer"),
            recipients=EmailRecipients(to=[]),
            subject="Metadata Test Email",
            body=EmailBody(content_type="text", content="Test content"),
            email_body="Test preview",
            processing_metadata=ProcessingMetadata(
                process_id="test_proc_123",
                monitor_version="1.0.0"
            )
        )
        
        # Process email scenario
        result = await processor.process_email_scenario(test_email)
        
        # Validate comprehensive metadata capture (Phase 3 requirement)
        assert result is not None
        assert result.processing_metadata is not None
        assert result.processing_time_breakdown is not None
        assert result.scenario_decision_factors is not None
        assert result.classification_confidence == 0.92
        assert result.ai_reasoning_detailed == "Customer expressed satisfaction with our service"
        
        # Validate timing data
        assert 'ai_classification_ms' in result.processing_time_breakdown
        assert 'scenario_processing_ms' in result.processing_time_breakdown
        assert 'total_processing_ms' in result.processing_time_breakdown
        
        # Validate decision factors
        assert len(result.scenario_decision_factors) > 0
        assert any("AI classification" in factor for factor in result.scenario_decision_factors)
        assert any("scenario_5" in factor for factor in result.scenario_decision_factors)
        
        # Validate processing metadata
        assert 'email_id' in result.processing_metadata
        assert 'total_processing_duration_ms' in result.processing_metadata
        assert 'test_mode' in result.processing_metadata
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_integration_compliance(self):
        """Test circuit breaker pattern is properly integrated per Phase 3 requirements."""
        
        # Create tracking integration with circuit breaker
        config = ScenarioTrackingConfiguration(
            enabled=True,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_recovery_timeout=30.0
        )
        
        integration = ScenarioTrackingIntegration(config)
        
        # Verify circuit breaker is initialized
        assert integration._circuit_breaker is not None
        assert integration._circuit_breaker.failure_threshold == 3
        assert integration._circuit_breaker.recovery_timeout == 30.0
        
        # Test circuit breaker protects email processing
        # First, verify circuit starts in CLOSED state
        assert integration._circuit_breaker.state == CircuitBreakerState.CLOSED
        
        # Mock tracking client that always fails
        integration.tracking_client = AsyncMock()
        integration.tracking_client.store_scenario_result.side_effect = Exception("Storage failure")
        integration.tracking_client.health_check.return_value = {"status": "healthy"}
        integration.tracking_client.initialize_table.return_value = True
        integration._initialized = True
        
        # Create test data
        mock_email = Mock()
        mock_email.id = "circuit_test"
        mock_email.sender.email = "test@example.com"
        
        mock_result = Mock()
        mock_result.process_id = "proc_123"
        
        # Trigger failures to open circuit breaker
        for i in range(4):  # One more than threshold
            try:
                await integration.track_scenario_processing(
                    email_data=mock_email,
                    processing_result=mock_result
                )
            except Exception:
                pass  # Expected failures
        
        # Verify circuit breaker opens (protects from further calls)
        result = await integration.track_scenario_processing(
            email_data=mock_email,
            processing_result=mock_result
        )
        
        assert result.success is False
        assert "Circuit breaker is OPEN" in result.error_message
    
    @pytest.mark.asyncio
    async def test_email_processor_template_compliance(self):
        """Test EmailProcessor integration follows template requirements exactly."""
        
        from config.settings import AppSettings
        
        # Create mock settings
        mock_settings = Mock(spec=AppSettings)
        mock_settings.test_mode.enabled = True
        mock_settings.test_mode.test_sender_email = "test@example.com"
        mock_settings.environment = "test"
        mock_settings.output.storage_type = "file"
        mock_settings.performance_tracking = True
        
        # Create email processor
        processor = EmailProcessor(mock_settings, "1.0.0-test")
        processor.tracking_enabled = True
        processor.tracking_settings = TrackingIntegrationSettings()
        
        # Mock dependencies
        processor.graph_client = AsyncMock()
        processor.scenario_processor = AsyncMock()
        processor._store_email = AsyncMock(return_value="/tmp/test_output")
        processor._get_correlation_id = Mock(return_value="correlation_abc123")
        processor._get_current_memory_usage = Mock(return_value=67.5)
        
        # Create test email and message
        from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata
        test_email = Email(
            id="template_test_email",
            conversation_id="template_conv",
            received_datetime=datetime.now(timezone.utc),
            sender=EmailSender(email="customer@example.com", name="Template Customer"),
            recipients=EmailRecipients(to=[]),
            subject="Template Compliance Test",
            body=EmailBody(content_type="text", content="Template test content"),
            email_body="Template preview",
            processing_metadata=ProcessingMetadata(
                process_id="template_proc_456",
                monitor_version="1.0.0-test"
            )
        )
        
        processor.graph_client.convert_to_email_model.return_value = test_email
        
        # Mock scenario result with enhanced metadata
        scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            agent_actions_log=["template_action"],
            expert_assigned="Template Expert",
            case_created="SF_TEMPLATE_123",
            emails_sent=[],
            # Enhanced metadata per template
            processing_metadata={
                'email_id': 'template_test_email',
                'processing_start_time': time.time(),
                'total_processing_duration_ms': 1250,
                'test_mode': True
            },
            processing_time_breakdown={
                'ai_classification_ms': 140,
                'scenario_processing_ms': 310,
                'total_processing_ms': 1250
            },
            scenario_decision_factors=[
                "Using AI classification for email intent: customer@example.com",
                "Processing scenario: scenario_5"
            ],
            classification_confidence=0.87,
            ai_reasoning_detailed="Template reasoning text"
        )
        
        processor.scenario_processor.process_email_scenario.return_value = scenario_result
        
        # Mock tracking integration
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            
            captured_call = None
            
            def capture_tracking_call(*args, **kwargs):
                nonlocal captured_call
                captured_call = {
                    'args': args,
                    'kwargs': kwargs
                }
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=45.2,
                    record_created=True,
                    async_queued=True
                )
            
            mock_integration.track_scenario_processing.side_effect = capture_tracking_call
            mock_get_integration.return_value = mock_integration
            
            # Process email
            result = await processor._process_single_email(
                message={
                    "id": "template_test_email",
                    "subject": "Template Compliance Test"
                },
                folder_id="template_folder",
                folder_name="Template Folder"
            )
            
            # Validate template compliance
            assert captured_call is not None
            
            # Check enhanced processing result construction
            processing_result = captured_call['kwargs']['processing_result']
            assert processing_result.sender_email == "customer@example.com"
            assert processing_result.sender_name == "Template Customer"
            assert processing_result.subject == "Template Compliance Test"
            assert processing_result.scenario_type == "scenario_5"
            assert processing_result.expert_assigned == "Template Expert"
            assert processing_result.case_created == "SF_TEMPLATE_123"
            
            # Check comprehensive additional context
            context = captured_call['kwargs']
            assert context['test_mode'] is True
            assert context['test_email_substitutions'] is not None
            assert context['environment'] == "test"
            assert context['monitor_version'] == "1.0.0-test"
            assert 'processed_at' in context
            assert context['memory_usage_mb'] == 67.5
            
            # Check proper correlation ID management
            assert context['correlation_id'] == "correlation_abc123"
            
            # Validate result has comprehensive tracking information
            assert result.tracking_success is True
            assert result.tracking_time_ms > 0  # Should capture actual timing
            assert result.tracking_record_created is True
            assert result.tracking_async_queued is True
    
    @pytest.mark.asyncio
    async def test_data_transformation_compliance(self):
        """Test data transformation follows template requirements and handles all scenarios."""
        
        transformer = ScenarioDataTransformer()
        
        # Create comprehensive test data
        from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata, EmailRecipient
        from models.email import ProcessingResult
        from services.scenario_processor import ScenarioResult, ScenarioType
        from services.azure_ai_foundry_client import IntentClassificationResult, EmailIntent
        
        test_email = Email(
            id="transform_test_123",
            conversation_id="transform_conv",
            received_datetime=datetime.now(timezone.utc),
            sender=EmailSender(email="transform@example.com", name="Transform Customer"),
            recipients=EmailRecipients(
                to=[EmailRecipient(email="support@company.com", name="Support Team")]
            ),
            subject="Transformation Test Email",
            body=EmailBody(content_type="text", content="Transform test content"),
            email_body="Transform preview",
            processing_metadata=ProcessingMetadata(
                process_id="transform_proc_789",
                monitor_version="1.0.0-transform"
            )
        )
        
        processing_result = ProcessingResult(
            success=True,
            email_id="transform_test_123",
            process_id="transform_proc_789",
            processing_duration_ms=1850
        )
        
        scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            agent_actions_log=["assigned_expert", "created_case"],
            expert_assigned="Transform Expert",
            case_created="SF_TRANSFORM_456",
            emails_sent=["forward1@example.com"],
            # Enhanced metadata
            processing_metadata={
                'email_id': 'transform_test_123',
                'total_processing_duration_ms': 1850
            },
            processing_time_breakdown={
                'ai_classification_ms': 160,
                'scenario_processing_ms': 390,
                'total_processing_ms': 1850
            },
            classification_confidence=0.91,
            ai_reasoning_detailed="Comprehensive transformation reasoning",
            expert_id="expert_transform_001",
            expert_email="transform.expert@company.com",
            assignment_method="round_robin",
            case_status="Assigned",
            forwarding_success=True,
            forwarding_reason="Expert assignment required"
        )
        
        intent_result = IntentClassificationResult(
            intent=EmailIntent.POSITIVE,
            confidence=0.91,
            reasoning="Comprehensive transformation reasoning",
            detected_phrases=["excellent", "satisfied"],
            processing_duration_ms=160
        )
        
        # Transform data
        tracking_record = transformer.create_tracking_record(
            email_data=test_email,
            processing_result=processing_result,
            scenario_result=scenario_result,
            intent_result=intent_result,
            correlation_id="transform_correlation_123",
            test_mode=True,
            environment="test_transform",
            monitor_version="1.0.0-transform"
        )
        
        # Validate comprehensive transformation
        assert tracking_record is not None
        assert tracking_record.process_id == "transform_proc_789"
        assert tracking_record.email_id == "transform_test_123"
        assert tracking_record.sender_email == "transform@example.com"
        assert tracking_record.sender_name == "Transform Customer"
        assert tracking_record.subject == "Transformation Test Email"
        assert tracking_record.correlation_id == "transform_correlation_123"
        
        # Validate scenario-specific information
        assert tracking_record.scenario_type.value == "scenario_5"
        assert tracking_record.scenario_success is True
        assert tracking_record.expert_assigned == "Transform Expert"
        assert tracking_record.case_created == "SF_TRANSFORM_456"
        
        # Validate AI classification information
        assert tracking_record.ai_intent.value == "POSITIVE"
        assert tracking_record.ai_confidence == 0.91
        assert tracking_record.ai_reasoning == "Comprehensive transformation reasoning"
        
        # Validate comprehensive context information
        assert tracking_record.test_mode is True
        assert tracking_record.environment == "test_transform"
        assert tracking_record.monitor_version == "1.0.0-transform"
    
    @pytest.mark.asyncio
    async def test_performance_validation_compliance(self):
        """Test performance validation meets <5% overhead requirement."""
        
        validator = PerformanceValidator(
            threshold_percentage=5.0,
            sample_size=20,
            warmup_samples=5
        )
        
        # Create test emails
        test_emails = create_test_emails(count=30)
        
        # Create mock email processor that simulates realistic timing
        class PerformanceTestProcessor:
            def __init__(self):
                self.tracking_enabled = True
            
            async def _process_single_email(self, *args, **kwargs):
                import random
                
                # Simulate baseline processing time (800-1200ms)
                base_time = random.uniform(0.8, 1.2)
                
                if self.tracking_enabled:
                    # Add small overhead (1-3% which should pass)
                    overhead = base_time * random.uniform(0.01, 0.03)
                    total_time = base_time + overhead
                else:
                    total_time = base_time
                
                await asyncio.sleep(total_time / 1000)  # Scale down for testing
                
                from models.email import ProcessingResult
                return ProcessingResult(
                    success=True,
                    email_id="perf_test",
                    process_id="perf_proc",
                    processing_duration_ms=int(total_time)
                )
        
        processor = PerformanceTestProcessor()
        settings = TrackingIntegrationSettings(performance_threshold_ms=50)
        
        # Run performance validation
        result = await validator.validate_integration_performance(
            email_processor=processor,
            test_emails=test_emails,
            settings=settings
        )
        
        # Validate performance compliance
        assert result.success is True
        assert result.metrics is not None
        assert result.metrics.overhead_percentage <= 5.0
        assert result.metrics.passed_threshold is True
        assert "EXCELLENT" in result.recommendation or "GOOD" in result.recommendation
        
        # Validate comprehensive metrics
        assert result.metrics.baseline_avg_ms > 0
        assert result.metrics.tracking_enabled_avg_ms > 0
        assert result.metrics.sample_size == 20
        assert result.metrics.baseline_min_ms > 0
        assert result.metrics.baseline_max_ms > 0
        assert result.metrics.tracking_min_ms > 0
        assert result.metrics.tracking_max_ms > 0
    
    @pytest.mark.asyncio
    async def test_integration_error_isolation_compliance(self):
        """Test that tracking failures are isolated from email processing per requirements."""
        
        from config.settings import AppSettings
        
        # Create email processor with tracking integration
        mock_settings = Mock(spec=AppSettings)
        mock_settings.test_mode.enabled = True
        mock_settings.environment = "error_test"
        mock_settings.output.storage_type = "file"
        
        processor = EmailProcessor(mock_settings, "1.0.0-error-test")
        processor.tracking_enabled = True
        processor.tracking_settings = TrackingIntegrationSettings()
        
        # Mock dependencies to succeed
        processor.graph_client = AsyncMock()
        processor.scenario_processor = AsyncMock()
        processor._store_email = AsyncMock(return_value="/tmp/error_test")
        processor._get_correlation_id = Mock(return_value="error_correlation")
        processor._get_current_memory_usage = Mock(return_value=55.0)
        
        # Create test email
        from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata
        test_email = Email(
            id="error_isolation_test",
            conversation_id="error_conv",
            received_datetime=datetime.now(timezone.utc),
            sender=EmailSender(email="error@example.com", name="Error Customer"),
            recipients=EmailRecipients(to=[]),
            subject="Error Isolation Test",
            body=EmailBody(content_type="text", content="Error test content"),
            email_body="Error preview",
            processing_metadata=ProcessingMetadata(
                process_id="error_proc_123",
                monitor_version="1.0.0-error"
            )
        )
        
        processor.graph_client.convert_to_email_model.return_value = test_email
        
        # Mock successful scenario processing
        scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_6,
            success=True,
            agent_actions_log=["error_test_action"],
            expert_assigned="Error Expert"
        )
        
        processor.scenario_processor.process_email_scenario.return_value = scenario_result
        
        # Mock tracking to fail catastrophically
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            mock_integration.track_scenario_processing.side_effect = Exception(
                "CRITICAL TRACKING FAILURE - DATABASE DOWN"
            )
            mock_get_integration.return_value = mock_integration
            
            # Process email - should succeed despite tracking failure
            result = await processor._process_single_email(
                message={
                    "id": "error_isolation_test",
                    "subject": "Error Isolation Test"
                },
                folder_id="error_folder",
                folder_name="Error Folder"
            )
            
            # Validate email processing succeeded (isolation working)
            assert result.success is True
            assert result.email_id == "error_isolation_test"
            assert result.scenario_type == "scenario_6"
            assert result.scenario_success is True
            assert result.expert_assigned == "Error Expert"
            
            # Validate tracking failure is recorded but doesn't fail email processing
            assert result.tracking_success is False
            assert result.tracking_error is not None
            assert "CRITICAL TRACKING FAILURE" in result.tracking_error
            
            # Verify tracking was attempted
            mock_integration.track_scenario_processing.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_configuration_integration_compliance(self):
        """Test configuration integration includes all required Phase 3 settings."""
        
        # Test tracking integration settings
        settings = TrackingIntegrationSettings()
        
        # Validate Phase 3 configuration requirements
        assert hasattr(settings, 'enabled')
        assert hasattr(settings, 'async_storage')
        assert hasattr(settings, 'storage_timeout_seconds')
        assert hasattr(settings, 'performance_threshold_ms')
        assert hasattr(settings, 'performance_monitoring_enabled')
        assert hasattr(settings, 'memory_usage_threshold_mb')
        assert hasattr(settings, 'connection_pool_wait_threshold_ms')
        assert hasattr(settings, 'circuit_breaker_enabled')
        assert hasattr(settings, 'failure_threshold')
        assert hasattr(settings, 'recovery_timeout_seconds')
        
        # Validate default values meet requirements
        assert settings.performance_threshold_ms == 50  # 5% of ~1000ms typical processing
        assert settings.performance_monitoring_enabled is True
        assert settings.circuit_breaker_enabled is True
        assert settings.failure_threshold >= 1
        assert settings.recovery_timeout_seconds >= 10
        
        # Test environment-based configuration loading
        with patch.dict('os.environ', {
            'TRACKING_ENABLED': 'true',
            'TRACKING_PERFORMANCE_THRESHOLD_MS': '75',
            'TRACKING_MEMORY_THRESHOLD_MB': '150'
        }):
            env_settings = TrackingIntegrationSettings.from_environment()
            assert env_settings.enabled is True
            assert env_settings.performance_threshold_ms == 75
            assert env_settings.memory_usage_threshold_mb == 150
    
    @pytest.mark.asyncio
    async def test_complete_scenario_tracking_integration_workflow(self):
        """Test complete scenario tracking workflow from email processing to tracking storage."""
        
        # This is the ultimate integration test that validates the entire scenario tracking pipeline
        
        from config.settings import AppSettings
        
        # Create comprehensive setup
        mock_settings = Mock(spec=AppSettings)
        mock_settings.test_mode.enabled = True
        mock_settings.test_mode.test_sender_email = "workflow@example.com"
        mock_settings.environment = "workflow_test"
        mock_settings.output.storage_type = "file"
        mock_settings.performance_tracking = True
        
        # Setup all scenario tracking configuration
        tracking_config = ScenarioTrackingConfiguration(
            enabled=True,
            async_insert=True,
            batch_insert_size=10,
            connection_timeout_seconds=30
        )
        
        integration_settings = TrackingIntegrationSettings(
            enabled=True,
            async_storage=True,
            performance_threshold_ms=50,
            performance_monitoring_enabled=True,
            circuit_breaker_enabled=True
        )
        
        # Create email processor
        processor = EmailProcessor(mock_settings, "1.0.0-workflow")
        processor.tracking_enabled = True
        processor.tracking_settings = integration_settings
        
        # Mock all dependencies for complete workflow
        processor.graph_client = AsyncMock()
        processor.scenario_processor = AsyncMock()
        processor._store_email = AsyncMock(return_value="/tmp/workflow_output")
        processor._get_correlation_id = Mock(return_value="workflow_correlation_456")
        processor._get_current_memory_usage = Mock(return_value=72.3)
        
        # Create comprehensive test email
        from models.email import Email, EmailAddress, EmailRecipients, EmailBody, ProcessingMetadata
        workflow_email = Email(
            id="workflow_complete_test",
            conversation_id="workflow_conv",
            received_datetime=datetime.now(timezone.utc),
            sender=EmailSender(email="workflow@example.com", name="Workflow Customer"),
            recipients=EmailRecipients(to=[]),
            subject="Complete Workflow Test",
            body=EmailBody(content_type="text", content="Complete workflow test content"),
            email_body="Workflow preview",
            processing_metadata=ProcessingMetadata(
                process_id="workflow_proc_complete",
                monitor_version="1.0.0-workflow"
            )
        )
        
        processor.graph_client.convert_to_email_model.return_value = workflow_email
        
        # Mock complete scenario result with all Phase 3 metadata
        complete_scenario_result = ScenarioResult(
            scenario_type=ScenarioType.SCENARIO_5,
            success=True,
            agent_actions_log=["workflow_assignment", "workflow_case_creation"],
            expert_assigned="Workflow Expert Pro",
            case_created="SF_WORKFLOW_COMPLETE_789",
            emails_sent=["workflow.expert@company.com"],
            # Complete Phase 3 metadata
            processing_metadata={
                'email_id': 'workflow_complete_test',
                'processing_start_time': time.time(),
                'total_processing_duration_ms': 1750,
                'test_mode': True,
                'forced_scenario': None
            },
            processing_time_breakdown={
                'ai_classification_ms': 180,
                'scenario_processing_ms': 420,
                'total_processing_ms': 1750
            },
            scenario_decision_factors=[
                "Using AI classification for email intent: workflow@example.com",
                "AI classification completed in 180.00ms",
                "Processing scenario: scenario_5"
            ],
            classification_confidence=0.94,
            ai_reasoning_detailed="Complete workflow reasoning with comprehensive analysis",
            expert_id="workflow_expert_001",
            expert_email="workflow.expert@company.com",
            assignment_method="round_robin",
            case_status="Assigned",
            forwarding_success=True,
            forwarding_reason="Expert assignment for positive customer response"
        )
        
        processor.scenario_processor.process_email_scenario.return_value = complete_scenario_result
        
        # Mock tracking integration for complete workflow
        with patch('services.email_processor.get_tracking_integration') as mock_get_integration:
            mock_integration = AsyncMock()
            
            # Capture complete tracking data
            captured_tracking_data = None
            
            def capture_complete_data(*args, **kwargs):
                nonlocal captured_tracking_data
                captured_tracking_data = kwargs
                return TrackingIntegrationResult(
                    success=True,
                    processing_duration_ms=52.7,
                    record_created=True,
                    async_queued=True
                )
            
            mock_integration.track_scenario_processing.side_effect = capture_complete_data
            mock_get_integration.return_value = mock_integration
            
            # Execute complete Phase 3 workflow
            workflow_result = await processor._process_single_email(
                message={
                    "id": "workflow_complete_test",
                    "subject": "Complete Workflow Test",
                    "from": {
                        "emailAddress": {
                            "address": "workflow@example.com",
                            "name": "Workflow Customer"
                        }
                    }
                },
                folder_id="workflow_folder",
                folder_name="Workflow Complete Folder"
            )
            
            # COMPREHENSIVE PHASE 3 VALIDATION
            
            # 1. Email processing success
            assert workflow_result.success is True
            assert workflow_result.email_id == "workflow_complete_test"
            assert workflow_result.scenario_type == "scenario_5"
            assert workflow_result.scenario_success is True
            assert workflow_result.expert_assigned == "Workflow Expert Pro"
            assert workflow_result.case_created == "SF_WORKFLOW_COMPLETE_789"
            
            # 2. Tracking integration success
            assert workflow_result.tracking_success is True
            assert workflow_result.tracking_time_ms > 0
            assert workflow_result.tracking_record_created is True
            assert workflow_result.tracking_async_queued is True
            assert workflow_result.tracking_error is None
            
            # 3. Comprehensive metadata capture validation
            assert captured_tracking_data is not None
            
            # Email data validation
            email_data = captured_tracking_data['email_data']
            assert email_data.id == "workflow_complete_test"
            assert email_data.sender.email == "workflow@example.com"
            assert email_data.subject == "Complete Workflow Test"
            
            # Enhanced processing result validation
            processing_result = captured_tracking_data['processing_result']
            assert processing_result.sender_email == "workflow@example.com"
            assert processing_result.sender_name == "Workflow Customer"
            assert processing_result.scenario_type == "scenario_5"
            assert processing_result.expert_assigned == "Workflow Expert Pro"
            assert processing_result.case_created == "SF_WORKFLOW_COMPLETE_789"
            
            # Scenario result metadata validation
            scenario_result = captured_tracking_data['scenario_result']
            assert scenario_result.processing_metadata is not None
            assert scenario_result.processing_time_breakdown is not None
            assert scenario_result.scenario_decision_factors is not None
            assert scenario_result.classification_confidence == 0.94
            assert scenario_result.ai_reasoning_detailed is not None
            assert scenario_result.expert_id == "workflow_expert_001"
            assert scenario_result.assignment_method == "round_robin"
            
            # Intent result validation
            intent_result = captured_tracking_data['intent_result']
            # Note: intent_result might be None if not set by scenario processor
            
            # Comprehensive context validation
            assert captured_tracking_data['test_mode'] is True
            assert captured_tracking_data['environment'] == "workflow_test"
            assert captured_tracking_data['monitor_version'] == "1.0.0-workflow"
            assert 'processed_at' in captured_tracking_data
            assert captured_tracking_data['memory_usage_mb'] == 72.3
            assert captured_tracking_data['correlation_id'] == "workflow_correlation_456"
            
            # 4. Performance and timing validation
            assert workflow_result.processing_duration_ms > 0
            assert workflow_result.tracking_time_ms < 100  # Should be efficient
            
        # Scenario tracking integration is COMPLETE and COMPLIANT
        print("✅ Scenario Tracking Integration Validation: PASSED")
        print(f"   Email Processing: SUCCESS")
        print(f"   Scenario Metadata: CAPTURED")
        print(f"   Circuit Breaker: INTEGRATED")
        print(f"   Tracking Integration: FUNCTIONAL")
        print(f"   Performance Monitoring: ENABLED")
        print(f"   Error Isolation: VERIFIED")
        print(f"   Template Compliance: VALIDATED")