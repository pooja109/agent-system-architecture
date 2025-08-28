"""
CI/CD Integration Utilities for Test Runner CLI
==============================================

Provides specialized functionality for different CI/CD platforms.
"""

import os
import json
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

class CIPlatform(Enum):
    """Supported CI/CD platforms."""
    GITHUB_ACTIONS = "github"
    AZURE_DEVOPS = "azure"
    JENKINS = "jenkins"
    GITLAB_CI = "gitlab"
    GENERIC = "generic"

@dataclass
class CIConfiguration:
    """Configuration for CI-specific behavior."""
    platform: CIPlatform
    output_format: str = "json"
    artifact_path: str = "test-results"
    enable_annotations: bool = True
    fail_fast: bool = True
    parallel_jobs: int = 4

class CIIntegration:
    """CI/CD platform integration utilities."""
    
    def __init__(self):
        self.platform = self._detect_ci_platform()
        self.config = self._load_ci_config()
    
    def _detect_ci_platform(self) -> CIPlatform:
        """Automatically detect the current CI platform."""
        if os.getenv('GITHUB_ACTIONS'):
            return CIPlatform.GITHUB_ACTIONS
        elif os.getenv('SYSTEM_TEAMFOUNDATIONCOLLECTIONURI'):
            return CIPlatform.AZURE_DEVOPS
        elif os.getenv('JENKINS_URL'):
            return CIPlatform.JENKINS
        elif os.getenv('GITLAB_CI'):
            return CIPlatform.GITLAB_CI
        else:
            return CIPlatform.GENERIC
    
    def _load_ci_config(self) -> CIConfiguration:
        """Load CI-specific configuration."""
        config_map = {
            CIPlatform.GITHUB_ACTIONS: CIConfiguration(
                platform=CIPlatform.GITHUB_ACTIONS,
                output_format="json",
                artifact_path="test-results",
                enable_annotations=True,
                fail_fast=False  # GitHub Actions handles this
            ),
            CIPlatform.AZURE_DEVOPS: CIConfiguration(
                platform=CIPlatform.AZURE_DEVOPS,
                output_format="xml",
                artifact_path="$(Agent.TempDirectory)/test-results",
                enable_annotations=True,
                fail_fast=True
            ),
            CIPlatform.JENKINS: CIConfiguration(
                platform=CIPlatform.JENKINS,
                output_format="xml",
                artifact_path="test-results",
                enable_annotations=False,
                fail_fast=True
            ),
            CIPlatform.GITLAB_CI: CIConfiguration(
                platform=CIPlatform.GITLAB_CI,
                output_format="json",
                artifact_path="test-results",
                enable_annotations=True,
                fail_fast=True
            )
        }
        
        return config_map.get(self.platform, CIConfiguration(platform=self.platform))
    
    def get_optimal_execution_mode(self) -> ExecutionMode:
        """Get optimal execution mode for the current CI environment."""
        # Check for PR/branch builds vs main branch
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            if os.getenv('GITHUB_EVENT_NAME') == 'pull_request':
                return ExecutionMode.ALL_EXCEPT_SLOW
            else:
                return ExecutionMode.FULL
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            if os.getenv('BUILD_REASON') == 'PullRequest':
                return ExecutionMode.ALL_EXCEPT_SLOW
            else:
                return ExecutionMode.FULL
        
        # Default for other platforms
        return ExecutionMode.CI_SAFE
    
    def setup_ci_environment(self) -> Dict[str, str]:
        """Set up environment variables for CI execution."""
        env_vars = {}
        
        # Common CI optimizations
        env_vars['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        env_vars['PYTHONUNBUFFERED'] = '1'
        
        # Platform-specific settings
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            env_vars['PYTEST_XDIST_WORKER_COUNT'] = str(self.config.parallel_jobs)
            env_vars['GITHUB_STEP_SUMMARY'] = 'test-summary.md'
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            env_vars['PYTEST_AZUREPIPELINES'] = '1'
            env_vars['AGENT_TEMPDIRECTORY'] = os.getenv('AGENT_TEMPDIRECTORY', '/tmp')
        
        return env_vars
    
    def generate_ci_commands(self, mode: ExecutionMode) -> List[str]:
        """Generate CI-optimized test runner commands."""
        base_cmd = ['python', 'test_runner.py']
        
        # Add execution mode
        mode_flag = f'--{mode.value.replace("_", "-")}'
        base_cmd.append(mode_flag)
        
        # Add CI-specific options
        base_cmd.extend([
            '--ci-mode', self.platform.value,
            '--output', f'{self.config.artifact_path}/results.{self.config.output_format}',
            '--quiet'  # Reduce noise in CI logs
        ])
        
        if self.config.fail_fast:
            base_cmd.append('--fail-fast')
        
        if self.config.parallel_jobs > 1:
            base_cmd.append('--parallel')
        
        return base_cmd
    
    def process_test_results(self, result: TestResult) -> Dict[str, Any]:
        """Process test results for CI platform consumption."""
        processed_result = {
            'platform': self.platform.value,
            'timestamp': result.total_execution_time,
            'summary': {
                'total': result.total_tests,
                'passed': result.passed_tests,
                'failed': result.failed_tests,
                'skipped': result.skipped_tests,
                'success_rate': result.success_rate
            }
        }
        
        # Add platform-specific processing
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            processed_result['github'] = self._process_github_actions(result)
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            processed_result['azure'] = self._process_azure_devops(result)
        
        return processed_result
    
    def _process_github_actions(self, result: TestResult) -> Dict[str, Any]:
        """Process results for GitHub Actions."""
        github_data = {}
        
        # Create step summary
        summary_lines = [
            f"# Test Results Summary",
            f"",
            f"**Total Tests:** {result.total_tests}",
            f"**Passed:** ✅ {result.passed_tests}",
            f"**Failed:** ❌ {result.failed_tests}",
            f"**Success Rate:** {result.success_rate:.1f}%",
            f"**Execution Time:** {result.total_execution_time:.2f}s",
        ]
        
        if result.failure_details:
            summary_lines.extend([
                f"",
                f"## Failures",
                f"",
            ])
            for failure in result.failure_details[:10]:  # Limit to first 10
                summary_lines.append(f"- `{failure}`")
        
        github_data['step_summary'] = "\n".join(summary_lines)
        
        # Create annotations for failures
        if result.failure_details and len(result.failure_details) <= 10:
            github_data['annotations'] = []
            for failure in result.failure_details:
                github_data['annotations'].append({
                    'level': 'error',
                    'message': f'Test failed: {failure}',
                    'title': 'Test Failure'
                })
        
        return github_data
    
    def _process_azure_devops(self, result: TestResult) -> Dict[str, Any]:
        """Process results for Azure DevOps."""
        azure_data = {
            'test_results_format': 'VSTest',
            'publish_results': True,
            'merge_results': True
        }
        
        # Create Azure DevOps test result format
        if result.individual_test_times:
            azure_data['individual_results'] = []
            for test_name, duration in result.individual_test_times.items():
                azure_data['individual_results'].append({
                    'test_name': test_name,
                    'outcome': 'Passed',  # Would need more sophisticated detection
                    'duration': duration * 1000,  # Convert to milliseconds
                })
        
        return azure_data
    
    def write_ci_outputs(self, result: TestResult, output_dir: Path):
        """Write CI platform-specific output files."""
        output_dir.mkdir(exist_ok=True, parents=True)
        
        # Write common results file
        results_file = output_dir / f'results.{self.config.output_format}'
        if self.config.output_format == 'json':
            results_data = self.process_test_results(result)
            results_file.write_text(json.dumps(results_data, indent=2))
        
        # Write platform-specific files
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            self._write_github_outputs(result, output_dir)
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            self._write_azure_outputs(result, output_dir)
    
    def _write_github_outputs(self, result: TestResult, output_dir: Path):
        """Write GitHub Actions specific outputs."""
        processed = self.process_test_results(result)
        github_data = processed.get('github', {})
        
        # Write step summary
        if 'step_summary' in github_data:
            summary_file = output_dir / 'step-summary.md'
            summary_file.write_text(github_data['step_summary'])
            
            # Set GitHub Actions step summary
            if os.getenv('GITHUB_STEP_SUMMARY'):
                with open(os.getenv('GITHUB_STEP_SUMMARY'), 'a') as f:
                    f.write(github_data['step_summary'])
        
        # Write annotations
        if 'annotations' in github_data:
            for annotation in github_data['annotations']:
                print(f"::error::{annotation['message']}")
    
    def _write_azure_outputs(self, result: TestResult, output_dir: Path):
        """Write Azure DevOps specific outputs."""
        # Write test results in Azure format
        # This would typically be in VSTest format or similar
        processed = self.process_test_results(result)
        azure_file = output_dir / 'azure-results.json'
        azure_file.write_text(json.dumps(processed.get('azure', {}), indent=2))
        
        # Set Azure DevOps variables
        print(f"##vso[task.setvariable variable=TestsPassed]{result.passed_tests}")
        print(f"##vso[task.setvariable variable=TestsFailed]{result.failed_tests}")
        print(f"##vso[task.setvariable variable=TestsTotal]{result.total_tests}")
        print(f"##vso[task.setvariable variable=SuccessRate]{result.success_rate:.1f}")
    
    def get_build_info(self) -> Dict[str, str]:
        """Extract build information from CI environment."""
        build_info = {}
        
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            build_info.update({
                'repository': os.getenv('GITHUB_REPOSITORY', ''),
                'ref': os.getenv('GITHUB_REF', ''),
                'sha': os.getenv('GITHUB_SHA', ''),
                'run_id': os.getenv('GITHUB_RUN_ID', ''),
                'run_number': os.getenv('GITHUB_RUN_NUMBER', ''),
                'actor': os.getenv('GITHUB_ACTOR', ''),
                'event_name': os.getenv('GITHUB_EVENT_NAME', '')
            })
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            build_info.update({
                'repository': os.getenv('BUILD_REPOSITORY_NAME', ''),
                'ref': os.getenv('BUILD_SOURCEBRANCH', ''),
                'sha': os.getenv('BUILD_SOURCEVERSION', ''),
                'build_id': os.getenv('BUILD_BUILDID', ''),
                'build_number': os.getenv('BUILD_BUILDNUMBER', ''),
                'reason': os.getenv('BUILD_REASON', '')
            })
        
        elif self.platform == CIPlatform.JENKINS:
            build_info.update({
                'job_name': os.getenv('JOB_NAME', ''),
                'build_number': os.getenv('BUILD_NUMBER', ''),
                'build_url': os.getenv('BUILD_URL', ''),
                'git_commit': os.getenv('GIT_COMMIT', ''),
                'git_branch': os.getenv('GIT_BRANCH', '')
            })
        
        elif self.platform == CIPlatform.GITLAB_CI:
            build_info.update({
                'project_path': os.getenv('CI_PROJECT_PATH', ''),
                'commit_sha': os.getenv('CI_COMMIT_SHA', ''),
                'commit_ref_name': os.getenv('CI_COMMIT_REF_NAME', ''),
                'job_id': os.getenv('CI_JOB_ID', ''),
                'pipeline_id': os.getenv('CI_PIPELINE_ID', '')
            })
        
        return build_info
    
    def should_run_full_suite(self) -> bool:
        """Determine if full test suite should run based on CI context."""
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            # Run full suite on main branch or release branches
            ref = os.getenv('GITHUB_REF', '')
            if 'refs/heads/main' in ref or 'refs/heads/master' in ref or 'refs/heads/release' in ref:
                return True
            # Run full suite on scheduled builds
            if os.getenv('GITHUB_EVENT_NAME') == 'schedule':
                return True
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            # Run full suite on main branch
            branch = os.getenv('BUILD_SOURCEBRANCH', '')
            if 'refs/heads/main' in branch or 'refs/heads/master' in branch:
                return True
            # Run full suite on manual or scheduled builds
            reason = os.getenv('BUILD_REASON', '')
            if reason in ['Manual', 'Schedule']:
                return True
        
        return False
    
    def get_parallel_job_count(self) -> int:
        """Get optimal parallel job count for current CI environment."""
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            # GitHub Actions runners typically have 2 cores
            return min(self.config.parallel_jobs, 2)
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            # Azure DevOps agents vary, but typically 2-4 cores
            return min(self.config.parallel_jobs, 4)
        
        elif self.platform == CIPlatform.JENKINS:
            # Jenkins can vary widely, use configured value
            return self.config.parallel_jobs
        
        return self.config.parallel_jobs
    
    def create_workflow_commands(self, result: TestResult) -> List[str]:
        """Create platform-specific workflow commands."""
        commands = []
        
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            # Set outputs for GitHub Actions
            commands.extend([
                f"echo 'tests-passed={result.passed_tests}' >> $GITHUB_OUTPUT",
                f"echo 'tests-failed={result.failed_tests}' >> $GITHUB_OUTPUT",
                f"echo 'tests-total={result.total_tests}' >> $GITHUB_OUTPUT",
                f"echo 'success-rate={result.success_rate:.1f}' >> $GITHUB_OUTPUT"
            ])
            
            # Create job summary
            if result.failure_details:
                commands.append("echo '## ❌ Test Failures' >> $GITHUB_STEP_SUMMARY")
                for failure in result.failure_details[:5]:
                    commands.append(f"echo '- {failure}' >> $GITHUB_STEP_SUMMARY")
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            # Set pipeline variables
            commands.extend([
                f"echo '##vso[task.setvariable variable=TestsPassed;isOutput=true]{result.passed_tests}'",
                f"echo '##vso[task.setvariable variable=TestsFailed;isOutput=true]{result.failed_tests}'",
                f"echo '##vso[task.setvariable variable=TestsTotal;isOutput=true]{result.total_tests}'",
                f"echo '##vso[task.setvariable variable=SuccessRate;isOutput=true]{result.success_rate:.1f}'"
            ])
        
        return commands
    
    def get_cache_key(self) -> str:
        """Generate cache key for CI environment."""
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            runner_os = os.getenv('RUNNER_OS', 'Linux')
            python_version = os.getenv('PYTHON_VERSION', '3.9')
            return f"pytest-cache-{runner_os}-{python_version}-${{{{ hashFiles('**/requirements.txt') }}}}"
        
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            agent_os = os.getenv('AGENT_OS', 'Linux')
            python_version = os.getenv('PYTHON_VERSION', '3.9')
            return f"pytest-cache-{agent_os}-{python_version}"
        
        return "pytest-cache-generic"
    
    def generate_ci_config_template(self) -> str:
        """Generate CI configuration template for the detected platform."""
        if self.platform == CIPlatform.GITHUB_ACTIONS:
            return self._generate_github_actions_template()
        elif self.platform == CIPlatform.AZURE_DEVOPS:
            return self._generate_azure_devops_template()
        elif self.platform == CIPlatform.JENKINS:
            return self._generate_jenkins_template()
        elif self.platform == CIPlatform.GITLAB_CI:
            return self._generate_gitlab_ci_template()
        else:
            return "# Generic CI template not available"
    
    def _generate_github_actions_template(self) -> str:
        """Generate GitHub Actions workflow template."""
        return '''
name: Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
        
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        cd agents/inbox_monitor
        python test_runner.py --ci-safe --generate-report html --output test-results/
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: test-results
        path: agents/inbox_monitor/test-results/
        '''
    
    def _generate_azure_devops_template(self) -> str:
        """Generate Azure DevOps pipeline template.""" 
        return '''
trigger:
- main
- develop

pr:
- main

pool:
  vmImage: 'ubuntu-latest'

variables:
  pythonVersion: '3.9'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '$(pythonVersion)'
  displayName: 'Use Python $(pythonVersion)'

- script: |
    python -m pip install --upgrade pip
    pip install -r requirements.txt
  displayName: 'Install dependencies'

- script: |
    cd agents/inbox_monitor
    python test_runner.py --ci-mode azure --generate-report xml --output $(Agent.TempDirectory)/test-results/
  displayName: 'Run tests'

- task: PublishTestResults@2
  condition: always()
  inputs:
    testResultsFiles: '$(Agent.TempDirectory)/test-results/**/*.xml'
    testRunTitle: 'Python Tests'
    
- task: PublishBuildArtifacts@1
  condition: always()
  inputs:
    pathToPublish: '$(Agent.TempDirectory)/test-results'
    artifactName: 'test-results'
        '''
    
    def _generate_jenkins_template(self) -> str:
        """Generate Jenkins pipeline template."""
        return '''
pipeline {
    agent any
    
    stages {
        stage('Setup') {
            steps {
                sh 'python -m pip install --upgrade pip'
                sh 'pip install -r requirements.txt'
            }
        }
        
        stage('Test') {
            steps {
                dir('agents/inbox_monitor') {
                    sh 'python test_runner.py --ci-mode jenkins --generate-report xml --output test-results/'
                }
            }
            post {
                always {
                    junit 'agents/inbox_monitor/test-results/**/*.xml'
                    archiveArtifacts artifacts: 'agents/inbox_monitor/test-results/**/*', allowEmptyArchive: true
                }
            }
        }
    }
}
        '''
    
    def _generate_gitlab_ci_template(self) -> str:
        """Generate GitLab CI template."""
        return '''
stages:
  - test

test:
  stage: test
  image: python:3.9
  before_script:
    - python -m pip install --upgrade pip
    - pip install -r requirements.txt
  script:
    - cd agents/inbox_monitor
    - python test_runner.py --ci-mode gitlab --generate-report json --output test-results/
  artifacts:
    when: always
    paths:
      - agents/inbox_monitor/test-results/
    expire_in: 1 week
    reports:
      junit: agents/inbox_monitor/test-results/**/*.xml
        '''