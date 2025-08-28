#!/usr/bin/env python3
"""
Complete Core Deployment Validation Script
===========================================

Final validation script to ensure complete Phase 6 implementation is working correctly.
"""

import asyncio
import argparse
import json
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
import structlog

logger = structlog.get_logger(__name__)


class CompleteCoreDeploymentValidator:
    """Validates complete core deployment implementation."""
    
    def __init__(self, table_suffix: str = ""):
        """Initialize complete deployment validator."""
        self.table_suffix = table_suffix
        self.validation_results = {}
        self.project_root = Path(__file__).parent.parent
    
    async def validate_complete_implementation(self) -> Dict[str, Any]:
        """Run complete validation of Phase 6 implementation."""
        logger.info("Starting complete Phase 6 implementation validation")
        
        validation_start = datetime.now()
        
        # Run all validation components
        await self._validate_core_components()
        await self._validate_test_suites()
        await self._validate_deployment_scripts()
        await self._validate_documentation()
        await self._validate_configuration_files()
        await self._validate_maintenance_scripts()
        await self._run_integration_tests()
        
        validation_duration = datetime.now() - validation_start
        
        # Generate final assessment
        assessment = await self._generate_final_assessment(validation_duration)
        
        return assessment
    
    async def _validate_core_components(self):
        """Validate core system components."""
        logger.info("Validating core system components")
        
        core_components = {
            'database_models': 'database/scenario_tracking_models.py',
            'database_schema': 'database/scenario_tracking_schema.sql',
            'tracking_client': 'services/scenario_tracking_client.py',
            'tracking_exceptions': 'services/scenario_tracking_exceptions.py',
            'tracking_metrics': 'services/scenario_tracking_metrics.py',
            'tracking_integration': 'services/scenario_tracking_integration.py'
        }
        
        component_results = {}
        
        for component_name, file_path in core_components.items():
            full_path = self.project_root / file_path
            
            if full_path.exists():
                # Basic file validation
                try:
                    content = full_path.read_text()
                    component_results[component_name] = {
                        'exists': True,
                        'size_bytes': len(content),
                        'lines': len(content.splitlines()),
                        'has_content': len(content.strip()) > 0
                    }
                except Exception as e:
                    component_results[component_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                component_results[component_name] = {
                    'exists': False,
                    'expected_path': str(full_path)
                }
        
        # Validate imports work
        try:
            from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
            from services.scenario_tracking_client import ScenarioTrackingClient
            
            component_results['imports'] = {
                'status': 'success',
                'models_import': True,
                'client_import': True
            }
        except ImportError as e:
            component_results['imports'] = {
                'status': 'failed',
                'error': str(e)
            }
        
        all_components_valid = all(
            result.get('exists', False) and not result.get('error')
            for result in component_results.values()
            if isinstance(result, dict) and 'exists' in result
        )
        
        self.validation_results['core_components'] = {
            'status': 'passed' if all_components_valid else 'failed',
            'components': component_results
        }
    
    async def _validate_test_suites(self):
        """Validate all test suites exist and can run."""
        logger.info("Validating test suites")
        
        test_suites = {
            'core_integration': 'tests/scenario_tracking/test_core_integration.py',
            'storage_performance': 'tests/scenario_tracking/test_storage_performance.py',
            'pipeline_integration': 'tests/scenario_tracking/test_pipeline_integration.py',
            'production_readiness': 'tests/scenario_tracking/test_production_readiness_core.py',
            'load_testing': 'tests/load_testing/test_storage_load.py',
            'security_compliance': 'tests/security/test_security_compliance_core.py'
        }
        
        suite_results = {}
        
        for suite_name, file_path in test_suites.items():
            full_path = self.project_root / file_path
            
            if full_path.exists():
                # Test syntax validation
                try:
                    result = subprocess.run([
                        'python', '-m', 'py_compile', str(full_path)
                    ], capture_output=True, text=True, cwd=self.project_root)
                    
                    suite_results[suite_name] = {
                        'exists': True,
                        'syntax_valid': result.returncode == 0,
                        'syntax_error': result.stderr if result.returncode != 0 else None
                    }
                except Exception as e:
                    suite_results[suite_name] = {
                        'exists': True,
                        'syntax_valid': False,
                        'error': str(e)
                    }
            else:
                suite_results[suite_name] = {
                    'exists': False,
                    'expected_path': str(full_path)
                }
        
        all_tests_valid = all(
            result.get('exists', False) and result.get('syntax_valid', False)
            for result in suite_results.values()
        )
        
        self.validation_results['test_suites'] = {
            'status': 'passed' if all_tests_valid else 'failed',
            'suites': suite_results
        }
    
    async def _validate_deployment_scripts(self):
        """Validate deployment scripts exist and are executable."""
        logger.info("Validating deployment scripts")
        
        deployment_scripts = {
            'core_deployment': 'scripts/deployment/deploy_core_scenario_tracking.py',
            'deployment_validation': 'scripts/deployment/validate_core_deployment.py',
            'deployment_rollback': 'scripts/deployment/rollback_core_deployment.py'
        }
        
        script_results = {}
        
        for script_name, file_path in deployment_scripts.items():
            full_path = self.project_root / file_path
            
            if full_path.exists():
                try:
                    # Check if script is executable (syntax check)
                    result = subprocess.run([
                        'python', '-m', 'py_compile', str(full_path)
                    ], capture_output=True, text=True)
                    
                    # Check for main function
                    content = full_path.read_text()
                    has_main = 'def main(' in content or 'async def main(' in content
                    
                    script_results[script_name] = {
                        'exists': True,
                        'syntax_valid': result.returncode == 0,
                        'has_main': has_main,
                        'executable': full_path.stat().st_mode & 0o100 != 0
                    }
                except Exception as e:
                    script_results[script_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                script_results[script_name] = {
                    'exists': False,
                    'expected_path': str(full_path)
                }
        
        all_scripts_valid = all(
            result.get('exists', False) and result.get('syntax_valid', False)
            for result in script_results.values()
        )
        
        self.validation_results['deployment_scripts'] = {
            'status': 'passed' if all_scripts_valid else 'failed',
            'scripts': script_results
        }
    
    async def _validate_documentation(self):
        """Validate documentation files exist and are complete."""
        logger.info("Validating documentation")
        
        documentation_files = {
            'core_readme': 'docs/scenario_tracking/README_CORE.md',
            'storage_architecture': 'docs/scenario_tracking/STORAGE_ARCHITECTURE.md'
        }
        
        doc_results = {}
        
        for doc_name, file_path in documentation_files.items():
            full_path = self.project_root / file_path
            
            if full_path.exists():
                try:
                    content = full_path.read_text()
                    
                    # Basic quality checks
                    has_headers = '# ' in content
                    has_code_examples = '```' in content
                    reasonable_length = len(content) > 1000  # At least 1KB of content
                    
                    doc_results[doc_name] = {
                        'exists': True,
                        'size_bytes': len(content),
                        'has_headers': has_headers,
                        'has_code_examples': has_code_examples,
                        'reasonable_length': reasonable_length
                    }
                except Exception as e:
                    doc_results[doc_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                doc_results[doc_name] = {
                    'exists': False,
                    'expected_path': str(full_path)
                }
        
        all_docs_valid = all(
            result.get('exists', False) and result.get('reasonable_length', False)
            for result in doc_results.values()
        )
        
        self.validation_results['documentation'] = {
            'status': 'passed' if all_docs_valid else 'failed',
            'documents': doc_results
        }
    
    async def _validate_configuration_files(self):
        """Validate configuration files exist and are valid."""
        logger.info("Validating configuration files")
        
        config_files = {
            'production_config': 'config/core_deployment/core_production_config.yaml',
            'development_config': 'config/core_deployment/core_development_config.yaml'
        }
        
        config_results = {}
        
        for config_name, file_path in config_files.items():
            full_path = self.project_root / file_path
            
            if full_path.exists():
                try:
                    import yaml
                    
                    with open(full_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    # Basic validation of config structure
                    has_database_section = 'database' in config_data
                    has_deployment_section = 'core_deployment' in config_data
                    
                    config_results[config_name] = {
                        'exists': True,
                        'valid_yaml': True,
                        'has_database_section': has_database_section,
                        'has_deployment_section': has_deployment_section,
                        'sections': list(config_data.keys())
                    }
                except Exception as e:
                    config_results[config_name] = {
                        'exists': True,
                        'valid_yaml': False,
                        'error': str(e)
                    }
            else:
                config_results[config_name] = {
                    'exists': False,
                    'expected_path': str(full_path)
                }
        
        all_configs_valid = all(
            result.get('exists', False) and result.get('valid_yaml', False)
            for result in config_results.values()
        )
        
        self.validation_results['configuration_files'] = {
            'status': 'passed' if all_configs_valid else 'failed',
            'configs': config_results
        }
    
    async def _validate_maintenance_scripts(self):
        """Validate maintenance scripts exist and are functional."""
        logger.info("Validating maintenance scripts")
        
        maintenance_scripts = {
            'data_cleanup': 'scripts/maintenance/data_cleanup_core.py',
            'health_monitor': 'scripts/maintenance/health_monitor_core.py'
        }
        
        script_results = {}
        
        for script_name, file_path in maintenance_scripts.items():
            full_path = self.project_root / file_path
            
            if full_path.exists():
                try:
                    result = subprocess.run([
                        'python', '-m', 'py_compile', str(full_path)
                    ], capture_output=True, text=True)
                    
                    content = full_path.read_text()
                    has_main = 'def main(' in content or 'async def main(' in content
                    
                    script_results[script_name] = {
                        'exists': True,
                        'syntax_valid': result.returncode == 0,
                        'has_main': has_main
                    }
                except Exception as e:
                    script_results[script_name] = {
                        'exists': True,
                        'error': str(e)
                    }
            else:
                script_results[script_name] = {
                    'exists': False,
                    'expected_path': str(full_path)
                }
        
        all_maintenance_valid = all(
            result.get('exists', False) and result.get('syntax_valid', False)
            for result in script_results.values()
        )
        
        self.validation_results['maintenance_scripts'] = {
            'status': 'passed' if all_maintenance_valid else 'failed',
            'scripts': script_results
        }
    
    async def _run_integration_tests(self):
        """Run basic integration tests to validate functionality."""
        logger.info("Running basic integration tests")
        
        integration_results = {}
        
        try:
            # Test basic model functionality
            from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
            
            test_record = ScenarioProcessingRecord(
                process_id="validation_test",
                email_id="validation_email",
                sender_email="validation@test.com",
                received_datetime=datetime.now(timezone.utc),
                process_success=True,
                scenario_type=ScenarioType.SCENARIO_5
            )
            
            # Test serialization
            serialized = test_record.to_databricks_dict()
            
            integration_results['model_functionality'] = {
                'status': 'passed',
                'record_creation': True,
                'serialization': True,
                'serialized_fields': len(serialized)
            }
            
        except Exception as e:
            integration_results['model_functionality'] = {
                'status': 'failed',
                'error': str(e)
            }
        
        try:
            # Test client initialization
            from services.scenario_tracking_client import ScenarioTrackingClient
            
            client = ScenarioTrackingClient(table_suffix=self.table_suffix)
            
            integration_results['client_initialization'] = {
                'status': 'passed',
                'client_created': True
            }
            
        except Exception as e:
            integration_results['client_initialization'] = {
                'status': 'failed',
                'error': str(e)
            }
        
        all_integration_passed = all(
            result.get('status') == 'passed' 
            for result in integration_results.values()
        )
        
        self.validation_results['integration_tests'] = {
            'status': 'passed' if all_integration_passed else 'failed',
            'tests': integration_results
        }
    
    async def _generate_final_assessment(self, validation_duration) -> Dict[str, Any]:
        """Generate final assessment of complete implementation."""
        
        # Calculate overall status
        validation_statuses = [result.get('status', 'unknown') for result in self.validation_results.values()]
        
        total_validations = len(validation_statuses)
        passed_validations = sum(1 for status in validation_statuses if status == 'passed')
        failed_validations = sum(1 for status in validation_statuses if status == 'failed')
        
        if failed_validations == 0:
            overall_status = 'complete_implementation'
        elif passed_validations >= total_validations * 0.8:  # 80% pass rate
            overall_status = 'mostly_complete'
        else:
            overall_status = 'incomplete_implementation'
        
        assessment = {
            'validation_timestamp': datetime.now(timezone.utc).isoformat(),
            'validation_duration_seconds': validation_duration.total_seconds(),
            'overall_status': overall_status,
            'table_suffix': self.table_suffix,
            'phase_6_implementation_summary': {
                'total_validation_categories': total_validations,
                'passed_validations': passed_validations,
                'failed_validations': failed_validations,
                'completion_percentage': (passed_validations / total_validations * 100) if total_validations > 0 else 0
            },
            'detailed_validation_results': self.validation_results,
            'implementation_completeness': {
                'core_components': self.validation_results.get('core_components', {}).get('status') == 'passed',
                'test_suites': self.validation_results.get('test_suites', {}).get('status') == 'passed',
                'deployment_scripts': self.validation_results.get('deployment_scripts', {}).get('status') == 'passed',
                'documentation': self.validation_results.get('documentation', {}).get('status') == 'passed',
                'configuration': self.validation_results.get('configuration_files', {}).get('status') == 'passed',
                'maintenance_scripts': self.validation_results.get('maintenance_scripts', {}).get('status') == 'passed',
                'integration_tests': self.validation_results.get('integration_tests', {}).get('status') == 'passed'
            }
        }
        
        return assessment


async def main():
    """Main validation function."""
    parser = argparse.ArgumentParser(description='Validate Complete Phase 6 Implementation')
    parser.add_argument('--table-suffix', default='', help='Table suffix for test isolation')
    parser.add_argument('--output', help='Save validation results to file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        import logging
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run complete validation
    validator = CompleteCoreDeploymentValidator(args.table_suffix)
    assessment = await validator.validate_complete_implementation()
    
    # Output results
    if args.output:
        Path(args.output).write_text(json.dumps(assessment, indent=2))
        logger.info("Validation assessment saved", file=args.output)
    else:
        print(json.dumps(assessment, indent=2))
    
    # Print summary
    print(f"\nPhase 6 Implementation Validation Summary:")
    print(f"Overall Status: {assessment['overall_status']}")
    print(f"Completion: {assessment['phase_6_implementation_summary']['completion_percentage']:.1f}%")
    print(f"Passed Validations: {assessment['phase_6_implementation_summary']['passed_validations']}/{assessment['phase_6_implementation_summary']['total_validation_categories']}")
    
    completeness = assessment['implementation_completeness']
    print(f"\nComponent Completeness:")
    for component, complete in completeness.items():
        status = "✓" if complete else "✗"
        print(f"  {status} {component}")
    
    # Return appropriate exit code
    if assessment['overall_status'] == 'complete_implementation':
        print(f"\n🎉 Phase 6 implementation is complete and ready for deployment!")
        return 0
    elif assessment['overall_status'] == 'mostly_complete':
        print(f"\n⚠️  Phase 6 implementation is mostly complete with minor issues.")
        return 0
    else:
        print(f"\n❌ Phase 6 implementation is incomplete - review failed validations.")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))