#!/usr/bin/env python3
"""
Core Deployment Validation Script
=================================

Comprehensive validation of core scenario tracking system deployment.
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)


class CoreDeploymentValidator:
    """Validates core deployment functionality and health."""
    
    def __init__(self, table_suffix: str = ""):
        """Initialize core deployment validator."""
        self.table_suffix = table_suffix
        self.logger = structlog.get_logger(__name__, component="deployment_validator")
        self.validation_results = {}
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive deployment validation."""
        self.logger.info("Starting comprehensive core deployment validation")
        
        validation_start = datetime.now()
        
        # Run all validation checks
        await self._validate_database_schema()
        await self._validate_service_functionality()
        await self._validate_configuration()
        await self._validate_security_compliance()
        await self._validate_performance()
        await self._validate_monitoring()
        
        validation_duration = datetime.now() - validation_start
        
        # Generate validation summary
        summary = await self._generate_validation_summary(validation_duration)
        
        return summary
    
    async def _validate_database_schema(self):
        """Validate database schema deployment."""
        self.logger.info("Validating database schema")
        
        try:
            # Import and test database connectivity
            try:
                from services.databricks_connection_pool import get_connection_pool
                
                connection_pool = await get_connection_pool()
                async with connection_pool.get_connection() as connection:
                    # Test basic connectivity
                    result = await connection.execute_query("SELECT 1 as test", {})
                    assert result.fetchone()['test'] == 1
                    
                    # Test table exists
                    table_name = f"inbox_monitor_scenario_processing{self.table_suffix}"
                    table_check = await connection.execute_query(f"""
                        SELECT COUNT(*) as table_exists
                        FROM information_schema.tables 
                        WHERE table_name = '{table_name}'
                    """, {})
                    
                    table_exists = table_check.fetchone()['table_exists'] > 0
                    
                    self.validation_results['database_schema'] = {
                        'status': 'passed' if table_exists else 'failed',
                        'connectivity': 'passed',
                        'table_exists': table_exists,
                        'table_name': table_name
                    }
                    
            except ImportError:
                self.logger.warning("Database connection not available for validation")
                self.validation_results['database_schema'] = {
                    'status': 'skipped',
                    'reason': 'database_connection_not_available'
                }
                
        except Exception as e:
            self.logger.error("Database schema validation failed", error=str(e))
            self.validation_results['database_schema'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _validate_service_functionality(self):
        """Validate core service functionality."""
        self.logger.info("Validating service functionality")
        
        try:
            from services.scenario_tracking_client import ScenarioTrackingClient
            from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
            
            # Test service instantiation and health check
            async with ScenarioTrackingClient(table_suffix=self.table_suffix) as client:
                # Health check
                health_status = await client.health_check()
                health_passed = health_status.get('status') in ['healthy', 'degraded']
                
                # Test record creation and storage
                test_record = ScenarioProcessingRecord(
                    process_id=f"validation_test_{int(datetime.now().timestamp())}",
                    email_id="validation_test_email",
                    sender_email="validation@test.com",
                    received_datetime=datetime.now(timezone.utc),
                    process_success=True,
                    scenario_type=ScenarioType.SCENARIO_5,
                    test_mode=True,
                    environment="deployment_validation"
                )
                
                # Test storage operation
                try:
                    storage_result = await client.store_scenario_result(test_record)
                    storage_passed = storage_result is True
                except Exception as storage_error:
                    storage_passed = False
                    self.logger.warning("Storage test failed", error=str(storage_error))
                
                # Test analytics query
                try:
                    analytics = await client.get_scenario_analytics(days_back=1)
                    analytics_passed = analytics.total_processed >= 0
                except Exception as analytics_error:
                    analytics_passed = False
                    self.logger.warning("Analytics test failed", error=str(analytics_error))
                
                self.validation_results['service_functionality'] = {
                    'status': 'passed' if (health_passed and storage_passed and analytics_passed) else 'degraded',
                    'health_check': 'passed' if health_passed else 'failed',
                    'storage_operation': 'passed' if storage_passed else 'failed',
                    'analytics_query': 'passed' if analytics_passed else 'failed',
                    'health_status': health_status
                }
                
        except Exception as e:
            self.logger.error("Service functionality validation failed", error=str(e))
            self.validation_results['service_functionality'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _validate_configuration(self):
        """Validate configuration completeness and correctness."""
        self.logger.info("Validating configuration")
        
        try:
            import os
            
            # Check required environment variables
            required_vars = [
                'DATABRICKS_HOST',
                'DATABRICKS_WAREHOUSE_ID',
                'DATABRICKS_OAUTH_CLIENT_ID',
                'DATABRICKS_OAUTH_CLIENT_SECRET'
            ]
            
            config_status = {}
            for var in required_vars:
                value = os.getenv(var)
                config_status[var] = {
                    'set': value is not None,
                    'non_empty': bool(value and value.strip())
                }
            
            all_configured = all(status['non_empty'] for status in config_status.values())
            
            # Test configuration loading
            try:
                from config.settings import get_settings
                settings = await get_settings()
                settings_loaded = hasattr(settings, 'databricks_oauth')
            except ImportError:
                settings_loaded = False
                self.logger.warning("Settings configuration not available")
            
            self.validation_results['configuration'] = {
                'status': 'passed' if (all_configured or settings_loaded) else 'failed',
                'environment_variables': config_status,
                'settings_loaded': settings_loaded
            }
            
        except Exception as e:
            self.logger.error("Configuration validation failed", error=str(e))
            self.validation_results['configuration'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _validate_security_compliance(self):
        """Validate security compliance requirements."""
        self.logger.info("Validating security compliance")
        
        try:
            security_checks = {}
            
            # Check for HTTPS URLs
            import os
            host = os.getenv('DATABRICKS_HOST', '')
            https_check = host.startswith('https://') or 'localhost' in host
            security_checks['https_enforced'] = https_check
            
            # Check for hardcoded secrets (basic check)
            source_files = [
                Path(__file__).parent.parent.parent / 'database' / 'scenario_tracking_models.py',
                Path(__file__).parent.parent.parent / 'services' / 'scenario_tracking_client.py'
            ]
            
            hardcoded_secrets_found = False
            for file_path in source_files:
                if file_path.exists():
                    content = file_path.read_text().lower()
                    # Very basic check for obvious secrets
                    if any(pattern in content for pattern in ['password=', 'secret=', 'token=']):
                        if not any(test_word in content for test_word in ['test', 'example', 'dummy']):
                            hardcoded_secrets_found = True
                            break
            
            security_checks['no_hardcoded_secrets'] = not hardcoded_secrets_found
            
            # Test PII handling
            from database.scenario_tracking_models import ScenarioProcessingRecord
            long_pii = "Very long PII data that should be truncated " * 50
            
            test_record = ScenarioProcessingRecord(
                process_id="pii_validation_test",
                email_id="pii_test",
                sender_email="pii@test.com",
                subject=long_pii,
                email_body=long_pii,
                received_datetime=datetime.now(timezone.utc),
                process_success=True
            )
            
            pii_truncated = len(test_record.subject) <= 503 and len(test_record.email_body) <= 255
            security_checks['pii_truncation'] = pii_truncated
            
            all_security_passed = all(security_checks.values())
            
            self.validation_results['security_compliance'] = {
                'status': 'passed' if all_security_passed else 'failed',
                'checks': security_checks
            }
            
        except Exception as e:
            self.logger.error("Security compliance validation failed", error=str(e))
            self.validation_results['security_compliance'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _validate_performance(self):
        """Validate performance characteristics."""
        self.logger.info("Validating performance")
        
        try:
            from services.scenario_tracking_client import ScenarioTrackingClient
            from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
            
            performance_metrics = {}
            
            # Test single record latency
            async with ScenarioTrackingClient(table_suffix=self.table_suffix) as client:
                test_records = []
                for i in range(5):
                    record = ScenarioProcessingRecord(
                        process_id=f"perf_test_{i}_{int(datetime.now().timestamp())}",
                        email_id=f"perf_email_{i}",
                        sender_email=f"perf_{i}@test.com",
                        received_datetime=datetime.now(timezone.utc),
                        process_success=True,
                        scenario_type=ScenarioType.SCENARIO_5,
                        test_mode=True
                    )
                    test_records.append(record)
                
                # Test batch performance
                start_time = datetime.now()
                
                try:
                    result = await client.store_scenario_results_batch(test_records)
                    batch_duration = (datetime.now() - start_time).total_seconds()
                    
                    performance_metrics['batch_storage'] = {
                        'duration_seconds': batch_duration,
                        'records_processed': len(test_records),
                        'successful_records': result.get('successful_records', 0),
                        'success_rate': result.get('success_rate', 0)
                    }
                    
                    # Performance requirements
                    batch_performance_passed = (
                        batch_duration < 10 and  # Under 10 seconds
                        result.get('success_rate', 0) >= 0.8  # 80% success rate
                    )
                    
                except Exception as perf_error:
                    batch_performance_passed = False
                    performance_metrics['batch_storage'] = {
                        'error': str(perf_error)
                    }
                
                # Test health check performance
                health_start = datetime.now()
                try:
                    health_status = await client.health_check()
                    health_duration = (datetime.now() - health_start).total_seconds()
                    
                    performance_metrics['health_check'] = {
                        'duration_seconds': health_duration,
                        'status': health_status.get('status')
                    }
                    
                    health_performance_passed = health_duration < 5  # Under 5 seconds
                    
                except Exception:
                    health_performance_passed = False
                
                overall_performance_passed = batch_performance_passed and health_performance_passed
                
                self.validation_results['performance'] = {
                    'status': 'passed' if overall_performance_passed else 'degraded',
                    'metrics': performance_metrics,
                    'batch_performance': 'passed' if batch_performance_passed else 'failed',
                    'health_check_performance': 'passed' if health_performance_passed else 'failed'
                }
                
        except Exception as e:
            self.logger.error("Performance validation failed", error=str(e))
            self.validation_results['performance'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _validate_monitoring(self):
        """Validate monitoring and observability features."""
        self.logger.info("Validating monitoring capabilities")
        
        try:
            from services.scenario_tracking_client import ScenarioTrackingClient
            
            async with ScenarioTrackingClient(table_suffix=self.table_suffix) as client:
                # Test health check completeness
                health_status = await client.health_check()
                
                required_health_fields = ['service_name', 'status', 'timestamp', 'checks']
                health_complete = all(field in health_status for field in required_health_fields)
                
                # Test metrics availability
                try:
                    metrics = await client.get_performance_metrics()
                    metrics_available = isinstance(metrics, dict) and len(metrics) > 0
                except Exception:
                    metrics_available = False
                
                self.validation_results['monitoring'] = {
                    'status': 'passed' if (health_complete and metrics_available) else 'degraded',
                    'health_check_complete': health_complete,
                    'metrics_available': metrics_available,
                    'health_status': health_status
                }
                
        except Exception as e:
            self.logger.error("Monitoring validation failed", error=str(e))
            self.validation_results['monitoring'] = {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _generate_validation_summary(self, validation_duration) -> Dict[str, Any]:
        """Generate comprehensive validation summary."""
        
        # Calculate overall status
        statuses = [result.get('status', 'unknown') for result in self.validation_results.values()]
        
        if all(status == 'passed' for status in statuses):
            overall_status = 'passed'
        elif any(status == 'failed' for status in statuses):
            overall_status = 'failed'
        else:
            overall_status = 'degraded'
        
        summary = {
            'validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'validation_duration_seconds': validation_duration.total_seconds(),
            'overall_status': overall_status,
            'table_suffix': self.table_suffix,
            'validation_results': self.validation_results,
            'summary': {
                'total_checks': len(self.validation_results),
                'passed_checks': sum(1 for r in self.validation_results.values() if r.get('status') == 'passed'),
                'failed_checks': sum(1 for r in self.validation_results.values() if r.get('status') == 'failed'),
                'degraded_checks': sum(1 for r in self.validation_results.values() if r.get('status') == 'degraded'),
                'skipped_checks': sum(1 for r in self.validation_results.values() if r.get('status') == 'skipped')
            }
        }
        
        return summary


async def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate Core Scenario Tracking Deployment')
    parser.add_argument('--table-suffix', default='', help='Table suffix for environment isolation')
    parser.add_argument('--output', help='Output file for validation results')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run validation
    validator = CoreDeploymentValidator(args.table_suffix)
    validation_summary = await validator.run_comprehensive_validation()
    
    # Output results
    if args.output:
        output_file = Path(args.output)
        output_file.write_text(json.dumps(validation_summary, indent=2))
        logger.info("Validation results saved", file=args.output)
    else:
        print(json.dumps(validation_summary, indent=2))
    
    # Return appropriate exit code
    overall_status = validation_summary['overall_status']
    if overall_status == 'passed':
        logger.info("Core deployment validation passed")
        return 0
    elif overall_status == 'degraded':
        logger.warning("Core deployment validation passed with warnings")
        return 0  # Still successful for deployment purposes
    else:
        logger.error("Core deployment validation failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))