#!/usr/bin/env python3
"""
Core Integration Test Runner
============================

Comprehensive test runner for core scenario tracking system integration tests.
"""

import asyncio
import argparse
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Any
import structlog

logger = structlog.get_logger(__name__)


class CoreIntegrationTestRunner:
    """Runner for core integration tests."""
    
    def __init__(self, table_suffix: str = "", verbose: bool = False):
        """Initialize test runner."""
        self.table_suffix = table_suffix
        self.verbose = verbose
        self.test_results = {}
    
    async def run_all_core_tests(self) -> Dict[str, Any]:
        """Run all core integration tests."""
        logger.info("Starting comprehensive core integration tests")
        
        test_suites = [
            {
                'name': 'core_integration',
                'file': 'tests/scenario_tracking/test_core_integration.py',
                'markers': 'integration'
            },
            {
                'name': 'storage_performance',
                'file': 'tests/scenario_tracking/test_storage_performance.py', 
                'markers': 'performance'
            },
            {
                'name': 'pipeline_integration',
                'file': 'tests/scenario_tracking/test_pipeline_integration.py',
                'markers': 'integration'
            },
            {
                'name': 'production_readiness',
                'file': 'tests/scenario_tracking/test_production_readiness_core.py',
                'markers': 'production'
            },
            {
                'name': 'load_testing',
                'file': 'tests/load_testing/test_storage_load.py',
                'markers': 'load'
            },
            {
                'name': 'security_compliance',
                'file': 'tests/security/test_security_compliance_core.py',
                'markers': 'security'
            }
        ]
        
        for suite in test_suites:
            await self._run_test_suite(suite)
        
        return self._generate_test_summary()
    
    async def _run_test_suite(self, suite: Dict[str, str]):
        """Run a single test suite."""
        logger.info(f"Running {suite['name']} test suite")
        
        # Build pytest command
        cmd = [
            'python', '-m', 'pytest',
            suite['file'],
            '-v',
            '--tb=short',
            '-m', suite['markers'],
            '--asyncio-mode=auto'
        ]
        
        # Add table suffix environment variable if specified
        env = {}
        if self.table_suffix:
            env['SCENARIO_TRACKING_TABLE_SUFFIX'] = self.table_suffix
        
        # Add verbose output if requested
        if self.verbose:
            cmd.extend(['--verbose', '-s'])
        
        try:
            # Run test suite
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
                env={**dict(os.environ), **env} if env else None,
                timeout=300  # 5 minute timeout per suite
            )
            
            self.test_results[suite['name']] = {
                'status': 'passed' if result.returncode == 0 else 'failed',
                'return_code': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'command': ' '.join(cmd)
            }
            
            if result.returncode == 0:
                logger.info(f"{suite['name']} test suite passed")
            else:
                logger.error(f"{suite['name']} test suite failed", 
                           return_code=result.returncode)
                
                if self.verbose:
                    print(f"\n{suite['name']} STDOUT:")
                    print(result.stdout)
                    print(f"\n{suite['name']} STDERR:")
                    print(result.stderr)
                
        except subprocess.TimeoutExpired:
            logger.error(f"{suite['name']} test suite timed out")
            self.test_results[suite['name']] = {
                'status': 'timeout',
                'error': 'Test suite exceeded 5 minute timeout'
            }
            
        except Exception as e:
            logger.error(f"{suite['name']} test suite error", error=str(e))
            self.test_results[suite['name']] = {
                'status': 'error',
                'error': str(e)
            }
    
    def _generate_test_summary(self) -> Dict[str, Any]:
        """Generate comprehensive test summary."""
        
        passed_suites = [name for name, result in self.test_results.items() 
                        if result.get('status') == 'passed']
        failed_suites = [name for name, result in self.test_results.items() 
                        if result.get('status') == 'failed']
        error_suites = [name for name, result in self.test_results.items() 
                       if result.get('status') in ['error', 'timeout']]
        
        overall_status = 'passed'
        if failed_suites or error_suites:
            overall_status = 'failed'
        
        summary = {
            'overall_status': overall_status,
            'total_suites': len(self.test_results),
            'passed_suites': len(passed_suites),
            'failed_suites': len(failed_suites),
            'error_suites': len(error_suites),
            'suite_results': {
                'passed': passed_suites,
                'failed': failed_suites,
                'errors': error_suites
            },
            'detailed_results': self.test_results
        }
        
        return summary


async def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='Run Core Integration Tests')
    parser.add_argument('--table-suffix', default='', help='Table suffix for test isolation')
    parser.add_argument('--suite', help='Run specific test suite only')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--output', help='Save results to file')
    
    args = parser.parse_args()
    
    # Set up environment
    import os
    if args.table_suffix:
        os.environ['SCENARIO_TRACKING_TABLE_SUFFIX'] = args.table_suffix
    
    # Run tests
    test_runner = CoreIntegrationTestRunner(args.table_suffix, args.verbose)
    
    if args.suite:
        # Run specific suite (implementation would filter suites)
        logger.info(f"Running specific test suite: {args.suite}")
        # For now, run all tests - in full implementation would filter
    
    test_summary = await test_runner.run_all_core_tests()
    
    # Output results
    if args.output:
        import json
        Path(args.output).write_text(json.dumps(test_summary, indent=2))
        logger.info("Test results saved", file=args.output)
    
    # Print summary
    print(f"\nTest Summary:")
    print(f"Overall Status: {test_summary['overall_status']}")
    print(f"Total Suites: {test_summary['total_suites']}")
    print(f"Passed: {test_summary['passed_suites']}")
    print(f"Failed: {test_summary['failed_suites']}")
    print(f"Errors: {test_summary['error_suites']}")
    
    if test_summary['suite_results']['passed']:
        print(f"\nPassed Suites: {', '.join(test_summary['suite_results']['passed'])}")
    
    if test_summary['suite_results']['failed']:
        print(f"\nFailed Suites: {', '.join(test_summary['suite_results']['failed'])}")
    
    if test_summary['suite_results']['errors']:
        print(f"\nError Suites: {', '.join(test_summary['suite_results']['errors'])}")
    
    # Return appropriate exit code
    return 0 if test_summary['overall_status'] == 'passed' else 1


if __name__ == "__main__":
    import os
    sys.exit(asyncio.run(main()))