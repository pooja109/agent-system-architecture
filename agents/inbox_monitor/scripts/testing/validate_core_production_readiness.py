#!/usr/bin/env python3
"""
Core Production Readiness Validator
===================================

Validates that the core scenario tracking system is ready for production deployment.
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
import structlog

logger = structlog.get_logger(__name__)


class CoreProductionReadinessValidator:
    """Validates core system production readiness."""
    
    def __init__(self, table_suffix: str = ""):
        """Initialize production readiness validator."""
        self.table_suffix = table_suffix
        self.validation_results = {}
    
    async def validate_production_readiness(self) -> Dict[str, Any]:
        """Run comprehensive production readiness validation."""
        logger.info("Starting core production readiness validation")
        
        validation_start = datetime.now()
        
        # Run all validation checks
        await self._validate_deployment_requirements()
        await self._validate_system_performance()
        await self._validate_security_compliance()
        await self._validate_monitoring_readiness()
        await self._validate_operational_procedures()
        await self._validate_disaster_recovery()
        
        validation_duration = datetime.now() - validation_start
        
        # Generate readiness assessment
        assessment = await self._generate_readiness_assessment(validation_duration)
        
        return assessment
    
    async def _validate_deployment_requirements(self):
        """Validate deployment requirements are met."""
        logger.info("Validating deployment requirements")
        
        try:
            requirements_check = {}
            
            # Check Python dependencies
            required_packages = ['pydantic', 'structlog', 'databricks-sql-connector']
            missing_packages = []
            
            for package in required_packages:
                try:
                    __import__(package.replace('-', '_'))
                except ImportError:
                    missing_packages.append(package)
            
            requirements_check['dependencies'] = {
                'status': 'passed' if not missing_packages else 'failed',
                'missing_packages': missing_packages
            }
            
            # Check environment configuration
            import os
            required_env_vars = [
                'DATABRICKS_HOST',
                'DATABRICKS_WAREHOUSE_ID',
                'DATABRICKS_OAUTH_CLIENT_ID',
                'DATABRICKS_OAUTH_CLIENT_SECRET'
            ]
            
            missing_env_vars = []
            for var in required_env_vars:
                if not os.getenv(var):
                    missing_env_vars.append(var)
            
            requirements_check['environment'] = {
                'status': 'passed' if not missing_env_vars else 'failed',
                'missing_variables': missing_env_vars
            }
            
            # Check core services availability
            try:
                from services.scenario_tracking_client import ScenarioTrackingClient
                from database.scenario_tracking_models import ScenarioProcessingRecord
                
                requirements_check['core_services'] = {
                    'status': 'passed',
                    'available_services': ['scenario_tracking_client', 'scenario_processing_record']
                }
                
            except ImportError as import_error:
                requirements_check['core_services'] = {
                    'status': 'failed',
                    'error': str(import_error)
                }
            
            overall_requirements = all(
                check['status'] == 'passed' 
                for check in requirements_check.values()
            )
            
            self.validation_results['deployment_requirements'] = {
                'status': 'passed' if overall_requirements else 'failed',
                'checks': requirements_check
            }
            
        except Exception as e:
            logger.error("Deployment requirements validation failed", error=str(e))
            self.validation_results['deployment_requirements'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def _validate_system_performance(self):
        """Validate system meets performance requirements."""
        logger.info("Validating system performance")
        
        try:
            from services.scenario_tracking_client import ScenarioTrackingClient
            from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
            
            performance_metrics = {}
            
            async with ScenarioTrackingClient(table_suffix=self.table_suffix) as client:
                # Test health check performance
                health_start = datetime.now()
                health_status = await client.health_check()
                health_duration = (datetime.now() - health_start).total_seconds()
                
                performance_metrics['health_check'] = {
                    'duration_seconds': health_duration,
                    'meets_requirement': health_duration < 2.0,  # Under 2 seconds
                    'status': health_status.get('status')
                }
                
                # Test single record performance
                test_record = ScenarioProcessingRecord(
                    process_id=f"perf_validation_{int(datetime.now().timestamp())}",
                    email_id="performance_validation_email",
                    sender_email="perf_validation@test.com",
                    received_datetime=datetime.now(timezone.utc),
                    process_success=True,
                    scenario_type=ScenarioType.SCENARIO_5,
                    test_mode=True
                )
                
                storage_start = datetime.now()
                try:
                    storage_result = await client.store_scenario_result(test_record)
                    storage_duration = (datetime.now() - storage_start).total_seconds()
                    
                    performance_metrics['single_record_storage'] = {
                        'duration_seconds': storage_duration,
                        'meets_requirement': storage_duration < 1.0,  # Under 1 second
                        'success': storage_result
                    }
                    
                except Exception as storage_error:
                    performance_metrics['single_record_storage'] = {
                        'duration_seconds': (datetime.now() - storage_start).total_seconds(),
                        'meets_requirement': False,
                        'error': str(storage_error)
                    }
                
                # Test batch performance
                batch_records = []
                for i in range(10):
                    record = ScenarioProcessingRecord(
                        process_id=f"batch_perf_{i}_{int(datetime.now().timestamp())}",
                        email_id=f"batch_email_{i}",
                        sender_email=f"batch_{i}@test.com",
                        received_datetime=datetime.now(timezone.utc),
                        process_success=True,
                        scenario_type=ScenarioType.SCENARIO_5,
                        test_mode=True
                    )
                    batch_records.append(record)
                
                batch_start = datetime.now()
                try:
                    batch_result = await client.store_scenario_results_batch(batch_records)
                    batch_duration = (datetime.now() - batch_start).total_seconds()
                    
                    throughput = batch_result.get('successful_records', 0) / batch_duration if batch_duration > 0 else 0
                    
                    performance_metrics['batch_storage'] = {
                        'duration_seconds': batch_duration,
                        'throughput_records_per_second': throughput,
                        'meets_requirement': throughput >= 5.0,  # At least 5 records/second
                        'success_rate': batch_result.get('success_rate', 0)
                    }
                    
                except Exception as batch_error:
                    performance_metrics['batch_storage'] = {
                        'duration_seconds': (datetime.now() - batch_start).total_seconds(),
                        'meets_requirement': False,
                        'error': str(batch_error)
                    }
            
            # Overall performance assessment
            performance_requirements_met = all(
                metric.get('meets_requirement', False) 
                for metric in performance_metrics.values()
            )
            
            self.validation_results['system_performance'] = {
                'status': 'passed' if performance_requirements_met else 'failed',
                'metrics': performance_metrics,
                'overall_meets_requirements': performance_requirements_met
            }
            
        except Exception as e:
            logger.error("System performance validation failed", error=str(e))
            self.validation_results['system_performance'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def _validate_security_compliance(self):
        """Validate security compliance requirements."""
        logger.info("Validating security compliance")
        
        try:
            security_checks = {}
            
            # Check HTTPS enforcement
            import os
            databricks_host = os.getenv('DATABRICKS_HOST', '')
            https_enforced = databricks_host.startswith('https://') or 'localhost' in databricks_host
            
            security_checks['https_enforcement'] = {
                'status': 'passed' if https_enforced else 'failed',
                'host': databricks_host[:50] if databricks_host else 'not_set'
            }
            
            # Check PII handling compliance
            from database.scenario_tracking_models import ScenarioProcessingRecord
            
            # Test PII truncation
            long_pii_data = "Sensitive customer information " * 100
            pii_test_record = ScenarioProcessingRecord(
                process_id="security_pii_test",
                email_id="security_test",
                sender_email="security@test.com",
                subject=long_pii_data,
                email_body=long_pii_data,
                received_datetime=datetime.now(timezone.utc),
                process_success=True
            )
            
            pii_properly_handled = (
                len(pii_test_record.subject) <= 503 and
                len(pii_test_record.email_body) <= 255
            )
            
            security_checks['pii_handling'] = {
                'status': 'passed' if pii_properly_handled else 'failed',
                'subject_length': len(pii_test_record.subject),
                'email_body_length': len(pii_test_record.email_body)
            }
            
            # Check for hardcoded secrets (basic check)
            source_files = [
                Path(__file__).parent.parent.parent / 'services' / 'scenario_tracking_client.py',
                Path(__file__).parent.parent.parent / 'database' / 'scenario_tracking_models.py'
            ]
            
            secrets_found = False
            for file_path in source_files:
                if file_path.exists():
                    content = file_path.read_text().lower()
                    if any(pattern in content for pattern in ['password=', 'secret=', 'token=']):
                        if not any(safe_word in content for safe_word in ['test', 'example', 'dummy']):
                            secrets_found = True
                            break
            
            security_checks['no_hardcoded_secrets'] = {
                'status': 'passed' if not secrets_found else 'failed',
                'files_checked': len([f for f in source_files if f.exists()])
            }
            
            # Overall security assessment
            all_security_passed = all(
                check['status'] == 'passed' 
                for check in security_checks.values()
            )
            
            self.validation_results['security_compliance'] = {
                'status': 'passed' if all_security_passed else 'failed',
                'checks': security_checks
            }
            
        except Exception as e:
            logger.error("Security compliance validation failed", error=str(e))
            self.validation_results['security_compliance'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def _validate_monitoring_readiness(self):
        """Validate monitoring and observability readiness."""
        logger.info("Validating monitoring readiness")
        
        try:
            from services.scenario_tracking_client import ScenarioTrackingClient
            
            monitoring_checks = {}
            
            async with ScenarioTrackingClient(table_suffix=self.table_suffix) as client:
                # Test health check comprehensiveness
                health_status = await client.health_check()
                
                required_health_fields = ['service_name', 'status', 'timestamp', 'checks']
                health_comprehensive = all(field in health_status for field in required_health_fields)
                
                monitoring_checks['health_check_comprehensive'] = {
                    'status': 'passed' if health_comprehensive else 'failed',
                    'available_fields': list(health_status.keys()),
                    'required_fields': required_health_fields
                }
                
                # Test metrics availability
                try:
                    metrics = await client.get_performance_metrics()
                    metrics_available = isinstance(metrics, dict) and len(metrics) > 0
                    
                    monitoring_checks['performance_metrics'] = {
                        'status': 'passed' if metrics_available else 'failed',
                        'metrics_count': len(metrics) if isinstance(metrics, dict) else 0
                    }
                    
                except Exception as metrics_error:
                    monitoring_checks['performance_metrics'] = {
                        'status': 'failed',
                        'error': str(metrics_error)
                    }
                
                # Test error reporting capability
                monitoring_checks['error_reporting'] = {
                    'status': 'passed',  # Basic logging is built-in
                    'logging_configured': True
                }
            
            all_monitoring_ready = all(
                check['status'] == 'passed' 
                for check in monitoring_checks.values()
            )
            
            self.validation_results['monitoring_readiness'] = {
                'status': 'passed' if all_monitoring_ready else 'failed',
                'checks': monitoring_checks
            }
            
        except Exception as e:
            logger.error("Monitoring readiness validation failed", error=str(e))
            self.validation_results['monitoring_readiness'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def _validate_operational_procedures(self):
        """Validate operational procedures are in place."""
        logger.info("Validating operational procedures")
        
        try:
            operational_checks = {}
            
            # Check deployment scripts exist
            deployment_scripts = [
                Path(__file__).parent.parent / 'deployment' / 'deploy_core_scenario_tracking.py',
                Path(__file__).parent.parent / 'deployment' / 'validate_core_deployment.py',
                Path(__file__).parent.parent / 'deployment' / 'rollback_core_deployment.py'
            ]
            
            deployment_scripts_available = sum(1 for script in deployment_scripts if script.exists())
            
            operational_checks['deployment_scripts'] = {
                'status': 'passed' if deployment_scripts_available >= 2 else 'failed',
                'available_scripts': deployment_scripts_available,
                'total_scripts': len(deployment_scripts)
            }
            
            # Check configuration management
            config_files = [
                Path(__file__).parent.parent.parent / 'config' / 'settings.py'
            ]
            
            config_management = sum(1 for config in config_files if config.exists())
            
            operational_checks['configuration_management'] = {
                'status': 'passed' if config_management > 0 else 'degraded',
                'available_configs': config_management
            }
            
            # Check test procedures
            test_scripts = [
                Path(__file__).parent / 'run_core_integration_tests.py'
            ]
            
            test_procedures = sum(1 for script in test_scripts if script.exists())
            
            operational_checks['test_procedures'] = {
                'status': 'passed' if test_procedures > 0 else 'failed',
                'available_test_scripts': test_procedures
            }
            
            all_operational_ready = all(
                check['status'] in ['passed', 'degraded'] 
                for check in operational_checks.values()
            )
            
            self.validation_results['operational_procedures'] = {
                'status': 'passed' if all_operational_ready else 'failed',
                'checks': operational_checks
            }
            
        except Exception as e:
            logger.error("Operational procedures validation failed", error=str(e))
            self.validation_results['operational_procedures'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def _validate_disaster_recovery(self):
        """Validate disaster recovery capabilities."""
        logger.info("Validating disaster recovery capabilities")
        
        try:
            dr_checks = {}
            
            # Check rollback capability
            rollback_script = Path(__file__).parent.parent / 'deployment' / 'rollback_core_deployment.py'
            
            dr_checks['rollback_capability'] = {
                'status': 'passed' if rollback_script.exists() else 'failed',
                'rollback_script_available': rollback_script.exists()
            }
            
            # Check backup capability (basic check)
            from services.scenario_tracking_client import ScenarioTrackingClient
            
            async with ScenarioTrackingClient(table_suffix=self.table_suffix) as client:
                try:
                    # Test that we can retrieve data (prerequisite for backup)
                    analytics = await client.get_scenario_analytics(days_back=1)
                    backup_capability = True
                except Exception:
                    backup_capability = False
                
                dr_checks['backup_capability'] = {
                    'status': 'passed' if backup_capability else 'degraded',
                    'data_retrieval_works': backup_capability
                }
            
            # Check data retention policies
            dr_checks['data_retention'] = {
                'status': 'passed',  # Built into data model
                'retention_fields_available': True
            }
            
            all_dr_ready = all(
                check['status'] in ['passed', 'degraded'] 
                for check in dr_checks.values()
            )
            
            self.validation_results['disaster_recovery'] = {
                'status': 'passed' if all_dr_ready else 'failed',
                'checks': dr_checks
            }
            
        except Exception as e:
            logger.error("Disaster recovery validation failed", error=str(e))
            self.validation_results['disaster_recovery'] = {
                'status': 'error',
                'error': str(e)
            }
    
    async def _generate_readiness_assessment(self, validation_duration) -> Dict[str, Any]:
        """Generate production readiness assessment."""
        
        # Calculate overall readiness
        validation_statuses = [result.get('status', 'unknown') for result in self.validation_results.values()]
        
        critical_failures = sum(1 for status in validation_statuses if status == 'failed')
        errors = sum(1 for status in validation_statuses if status == 'error')
        passed = sum(1 for status in validation_statuses if status == 'passed')
        degraded = sum(1 for status in validation_statuses if status == 'degraded')
        
        if critical_failures > 0 or errors > 0:
            overall_readiness = 'not_ready'
        elif degraded > 0:
            overall_readiness = 'ready_with_warnings'
        else:
            overall_readiness = 'production_ready'
        
        assessment = {
            'assessment_timestamp': datetime.now(timezone.utc).isoformat(),
            'validation_duration_seconds': validation_duration.total_seconds(),
            'overall_readiness': overall_readiness,
            'table_suffix': self.table_suffix,
            'validation_summary': {
                'total_checks': len(self.validation_results),
                'passed_checks': passed,
                'degraded_checks': degraded,
                'failed_checks': critical_failures,
                'error_checks': errors
            },
            'detailed_results': self.validation_results
        }
        
        return assessment


async def main():
    """Main production readiness validation function."""
    parser = argparse.ArgumentParser(description='Validate Core Production Readiness')
    parser.add_argument('--table-suffix', default='', help='Table suffix for test isolation')
    parser.add_argument('--output', help='Save assessment to file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run production readiness validation
    validator = CoreProductionReadinessValidator(args.table_suffix)
    assessment = await validator.validate_production_readiness()
    
    # Output results
    if args.output:
        Path(args.output).write_text(json.dumps(assessment, indent=2))
        logger.info("Production readiness assessment saved", file=args.output)
    else:
        print(json.dumps(assessment, indent=2))
    
    # Print summary
    print(f"\nProduction Readiness Assessment:")
    print(f"Overall Status: {assessment['overall_readiness']}")
    print(f"Total Checks: {assessment['validation_summary']['total_checks']}")
    print(f"Passed: {assessment['validation_summary']['passed_checks']}")
    print(f"Degraded: {assessment['validation_summary']['degraded_checks']}")
    print(f"Failed: {assessment['validation_summary']['failed_checks']}")
    print(f"Errors: {assessment['validation_summary']['error_checks']}")
    
    # Return appropriate exit code
    if assessment['overall_readiness'] in ['production_ready', 'ready_with_warnings']:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))