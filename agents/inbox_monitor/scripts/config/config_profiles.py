"""
Configuration Profile Management for Test Runner CLI
===================================================

Provides advanced configuration management with profile support.
"""

import json
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

from .runner_config import ExecutionMode, MarkerConfig

class ProfileType(Enum):
    """Types of configuration profiles."""
    DEVELOPMENT = "development"
    CI_CD = "ci_cd"
    PERFORMANCE = "performance"
    DEBUGGING = "debugging"
    PRODUCTION = "production"
    CUSTOM = "custom"

@dataclass
class TestRunnerProfile:
    """Configuration profile for test runner."""
    name: str
    description: str
    profile_type: ProfileType
    execution_mode: ExecutionMode
    environment_variables: Dict[str, str] = field(default_factory=dict)
    pytest_options: List[str] = field(default_factory=list)
    timeout_seconds: Optional[int] = None
    max_failures: Optional[int] = None
    parallel_jobs: Optional[int] = None
    fail_fast: bool = False
    verbose: bool = False
    quiet: bool = False
    enable_coverage: bool = False
    coverage_threshold: float = 80.0
    custom_markers: Optional[str] = None
    output_formats: List[str] = field(default_factory=list)
    report_directory: str = "test_reports"
    enable_html_report: bool = False
    enable_junit_xml: bool = False
    enable_performance_analysis: bool = False
    enable_trend_analysis: bool = False
    ci_integration: Optional[str] = None
    created_at: Optional[str] = None
    modified_at: Optional[str] = None

class ConfigProfileManager:
    """Manages configuration profiles for the test runner."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / '.test_runner'
        self.config_dir.mkdir(exist_ok=True)
        self.profiles_file = self.config_dir / 'profiles.json'
        self.profiles: Dict[str, TestRunnerProfile] = {}
        self._load_profiles()
        self._ensure_default_profiles()
    
    def _load_profiles(self):
        """Load profiles from configuration file."""
        if self.profiles_file.exists():
            try:
                data = json.loads(self.profiles_file.read_text())
                for name, profile_data in data.items():
                    # Convert dict back to dataclass
                    profile_data['profile_type'] = ProfileType(profile_data['profile_type'])
                    profile_data['execution_mode'] = ExecutionMode(profile_data['execution_mode'])
                    self.profiles[name] = TestRunnerProfile(**profile_data)
            except (json.JSONError, KeyError, ValueError) as e:
                print(f"Warning: Could not load profiles from {self.profiles_file}: {e}")
                self.profiles = {}
    
    def _save_profiles(self):
        """Save profiles to configuration file."""
        try:
            # Convert dataclasses to dicts for JSON serialization
            data = {}
            for name, profile in self.profiles.items():
                profile_dict = asdict(profile)
                profile_dict['profile_type'] = profile.profile_type.value
                profile_dict['execution_mode'] = profile.execution_mode.value
                data[name] = profile_dict
            
            self.profiles_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error saving profiles: {e}")
    
    def _ensure_default_profiles(self):
        """Create default profiles if they don't exist."""
        default_profiles = self._get_default_profiles()
        
        for profile in default_profiles:
            if profile.name not in self.profiles:
                self.profiles[profile.name] = profile
        
        self._save_profiles()
    
    def _get_default_profiles(self) -> List[TestRunnerProfile]:
        """Get list of default configuration profiles."""
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        
        return [
            TestRunnerProfile(
                name="fast-dev",
                description="Quick development feedback with fast tests only",
                profile_type=ProfileType.DEVELOPMENT,
                execution_mode=ExecutionMode.FAST,
                environment_variables={
                    "PYTEST_TIMEOUT": "300",
                    "TEST_MODE": "development"
                },
                pytest_options=["--tb=short", "-v"],
                timeout_seconds=300,
                parallel_jobs=2,
                fail_fast=True,
                verbose=True,
                output_formats=["console"],
                enable_html_report=False,
                enable_performance_analysis=True,
                created_at=timestamp
            ),
            
            TestRunnerProfile(
                name="ci-pull-request",
                description="CI profile for pull request validation",
                profile_type=ProfileType.CI_CD,
                execution_mode=ExecutionMode.ALL_EXCEPT_SLOW,
                environment_variables={
                    "PYTEST_TIMEOUT": "1800",
                    "PYTEST_WORKERS": "4",
                    "CI": "true"
                },
                pytest_options=["--tb=short", "-q"],
                timeout_seconds=1800,
                max_failures=5,
                parallel_jobs=4,
                quiet=True,
                output_formats=["junit", "json"],
                report_directory="ci_reports",
                enable_junit_xml=True,
                enable_performance_analysis=True,
                ci_integration="github",
                created_at=timestamp
            ),
            
            TestRunnerProfile(
                name="ci-main-branch",
                description="Comprehensive CI profile for main branch",
                profile_type=ProfileType.CI_CD,
                execution_mode=ExecutionMode.FULL,
                environment_variables={
                    "PYTEST_TIMEOUT": "3600",
                    "PYTEST_WORKERS": "6",
                    "CI": "true"
                },
                pytest_options=["--tb=line", "-q"],
                timeout_seconds=3600,
                parallel_jobs=6,
                quiet=True,
                enable_coverage=True,
                coverage_threshold=85.0,
                output_formats=["junit", "json", "html"],
                report_directory="ci_reports",
                enable_html_report=True,
                enable_junit_xml=True,
                enable_performance_analysis=True,
                enable_trend_analysis=True,
                ci_integration="github",
                created_at=timestamp
            ),
            
            TestRunnerProfile(
                name="performance-testing",
                description="Profile optimized for performance testing and benchmarks",
                profile_type=ProfileType.PERFORMANCE,
                execution_mode=ExecutionMode.CUSTOM,
                custom_markers="performance or slow",
                environment_variables={
                    "PYTEST_TIMEOUT": "7200",
                    "PERFORMANCE_MODE": "true"
                },
                pytest_options=["--tb=short", "-v", "--durations=20"],
                timeout_seconds=7200,
                parallel_jobs=1,  # Sequential for accurate performance measurements
                verbose=True,
                output_formats=["json", "html"],
                enable_html_report=True,
                enable_performance_analysis=True,
                enable_trend_analysis=True,
                created_at=timestamp
            ),
            
            TestRunnerProfile(
                name="debug-mode",
                description="Debugging profile with maximum verbosity and no timeouts",
                profile_type=ProfileType.DEBUGGING,
                execution_mode=ExecutionMode.FAST,
                environment_variables={
                    "DEBUG": "true",
                    "PYTEST_CAPTURE": "no"
                },
                pytest_options=["--tb=long", "-v", "-s", "--no-timeout"],
                parallel_jobs=1,  # Sequential for debugging
                verbose=True,
                fail_fast=True,
                output_formats=["console"],
                created_at=timestamp
            ),
            
            TestRunnerProfile(
                name="smoke-check",
                description="Quick smoke test for critical functionality",
                profile_type=ProfileType.PRODUCTION,
                execution_mode=ExecutionMode.SMOKE,
                environment_variables={
                    "PYTEST_TIMEOUT": "180"
                },
                pytest_options=["--tb=short"],
                timeout_seconds=180,
                fail_fast=True,
                output_formats=["console", "json"],
                enable_performance_analysis=True,
                created_at=timestamp
            )
        ]
    
    def get_profile(self, name: str) -> Optional[TestRunnerProfile]:
        """Get a profile by name."""
        return self.profiles.get(name)
    
    def list_profiles(self) -> Dict[str, TestRunnerProfile]:
        """Get all available profiles."""
        return self.profiles.copy()
    
    def create_profile(self, profile: TestRunnerProfile) -> bool:
        """Create a new profile."""
        if profile.name in self.profiles:
            return False  # Profile already exists
        
        from datetime import datetime
        profile.created_at = datetime.now().isoformat()
        profile.modified_at = profile.created_at
        
        self.profiles[profile.name] = profile
        self._save_profiles()
        return True
    
    def update_profile(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update an existing profile."""
        if name not in self.profiles:
            return False
        
        profile = self.profiles[name]
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                # Handle enum conversions
                if key == 'profile_type' and isinstance(value, str):
                    value = ProfileType(value)
                elif key == 'execution_mode' and isinstance(value, str):
                    value = ExecutionMode(value)
                
                setattr(profile, key, value)
        
        from datetime import datetime
        profile.modified_at = datetime.now().isoformat()
        
        self._save_profiles()
        return True
    
    def delete_profile(self, name: str) -> bool:
        """Delete a profile."""
        if name not in self.profiles:
            return False
        
        # Don't allow deletion of default profiles
        default_names = {p.name for p in self._get_default_profiles()}
        if name in default_names:
            return False
        
        del self.profiles[name]
        self._save_profiles()
        return True
    
    def clone_profile(self, source_name: str, new_name: str, description: Optional[str] = None) -> bool:
        """Clone an existing profile with a new name."""
        if source_name not in self.profiles or new_name in self.profiles:
            return False
        
        source_profile = self.profiles[source_name]
        
        # Create a copy
        new_profile = TestRunnerProfile(**asdict(source_profile))
        new_profile.name = new_name
        new_profile.description = description or f"Copy of {source_profile.description}"
        new_profile.profile_type = ProfileType.CUSTOM
        
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        new_profile.created_at = timestamp
        new_profile.modified_at = timestamp
        
        self.profiles[new_name] = new_profile
        self._save_profiles()
        return True
    
    def get_profile_by_type(self, profile_type: ProfileType) -> List[TestRunnerProfile]:
        """Get all profiles of a specific type."""
        return [p for p in self.profiles.values() if p.profile_type == profile_type]
    
    def validate_profile(self, profile: TestRunnerProfile) -> List[str]:
        """Validate a profile configuration and return any errors."""
        errors = []
        
        # Validate required fields
        if not profile.name:
            errors.append("Profile name is required")
        
        if not profile.description:
            errors.append("Profile description is required")
        
        # Validate timeout
        if profile.timeout_seconds and profile.timeout_seconds < 0:
            errors.append("Timeout must be positive")
        
        # Validate parallel jobs
        if profile.parallel_jobs and profile.parallel_jobs < 1:
            errors.append("Parallel jobs must be at least 1")
        
        # Validate coverage threshold
        if profile.coverage_threshold < 0 or profile.coverage_threshold > 100:
            errors.append("Coverage threshold must be between 0 and 100")
        
        # Validate custom markers for CUSTOM execution mode
        if (profile.execution_mode == ExecutionMode.CUSTOM and 
            not profile.custom_markers):
            errors.append("Custom markers required when using CUSTOM execution mode")
        
        # Validate output formats
        valid_formats = {"console", "json", "xml", "html", "junit"}
        for format_name in profile.output_formats:
            if format_name not in valid_formats:
                errors.append(f"Invalid output format: {format_name}")
        
        return errors
    
    def apply_profile_to_environment(self, profile: TestRunnerProfile):
        """Apply profile environment variables to current environment."""
        if profile is None:
            raise ValueError("Profile cannot be None")
        if profile.environment_variables:
            for key, value in profile.environment_variables.items():
                os.environ[key] = value
    
    def get_pytest_command_from_profile(self, profile: TestRunnerProfile) -> List[str]:
        """Generate pytest command from profile configuration."""
        cmd = ['python', '-m', 'pytest']
        
        # Add execution mode markers
        if profile.execution_mode != ExecutionMode.CUSTOM:
            from runner_config import RunnerConfig
            config = RunnerConfig()
            marker_config = config.get_marker_config(profile.execution_mode)
            if marker_config.markers:
                cmd.extend(['-m', marker_config.markers])
        elif profile.custom_markers:
            cmd.extend(['-m', profile.custom_markers])
        
        # Add profile-specific pytest options
        cmd.extend(profile.pytest_options)
        
        # Add conditional options
        if profile.fail_fast:
            cmd.append('--maxfail=1')
        elif profile.max_failures:
            cmd.append(f'--maxfail={profile.max_failures}')
        
        if profile.parallel_jobs and profile.parallel_jobs > 1:
            cmd.extend(['-n', str(profile.parallel_jobs)])
        
        if profile.timeout_seconds:
            cmd.extend(['--timeout', str(profile.timeout_seconds)])
        
        if profile.enable_coverage:
            cmd.extend(['--cov=.', f'--cov-fail-under={profile.coverage_threshold}'])
        
        # Add output format options
        if 'junit' in profile.output_formats or profile.enable_junit_xml:
            cmd.extend(['--junit-xml', f'{profile.report_directory}/junit.xml'])
        
        if profile.enable_html_report:
            cmd.extend(['--html', f'{profile.report_directory}/report.html', '--self-contained-html'])
        
        # Add test discovery path
        cmd.append('tests/')
        
        return cmd
    
    def export_profile(self, name: str, output_path: Path) -> bool:
        """Export a profile to a JSON file."""
        if name not in self.profiles:
            return False
        
        try:
            profile = self.profiles[name]
            profile_dict = asdict(profile)
            profile_dict['profile_type'] = profile.profile_type.value
            profile_dict['execution_mode'] = profile.execution_mode.value
            
            output_path.write_text(json.dumps(profile_dict, indent=2))
            return True
        except Exception as e:
            print(f"Error exporting profile: {e}")
            return False
    
    def import_profile(self, input_path: Path) -> bool:
        """Import a profile from a JSON file."""
        try:
            data = json.loads(input_path.read_text())
            
            # Convert enum values back
            data['profile_type'] = ProfileType(data['profile_type'])
            data['execution_mode'] = ExecutionMode(data['execution_mode'])
            
            profile = TestRunnerProfile(**data)
            
            # Validate before importing
            errors = self.validate_profile(profile)
            if errors:
                print(f"Profile validation failed: {', '.join(errors)}")
                return False
            
            # Check for conflicts
            if profile.name in self.profiles:
                print(f"Profile '{profile.name}' already exists")
                return False
            
            self.profiles[profile.name] = profile
            self._save_profiles()
            return True
            
        except Exception as e:
            print(f"Error importing profile: {e}")
            return False
    
    def get_profile_recommendations(self, context: Dict[str, Any]) -> List[str]:
        """Get profile recommendations based on context."""
        recommendations = []
        
        # Check for CI environment
        if context.get('is_ci'):
            if context.get('is_pull_request'):
                recommendations.append("ci-pull-request")
            else:
                recommendations.append("ci-main-branch")
        
        # Check for development environment
        elif context.get('is_development'):
            recommendations.append("fast-dev")
        
        # Check for performance testing
        if context.get('performance_focus'):
            recommendations.append("performance-testing")
        
        # Check for debugging
        if context.get('debug_mode'):
            recommendations.append("debug-mode")
        
        # Default recommendation
        if not recommendations:
            recommendations.append("fast-dev")
        
        return recommendations
    
    def merge_profiles(self, base_profile: str, override_profile: str, new_name: str) -> bool:
        """Merge two profiles into a new profile."""
        if (base_profile not in self.profiles or 
            override_profile not in self.profiles or 
            new_name in self.profiles):
            return False
        
        base = self.profiles[base_profile]
        override = self.profiles[override_profile]
        
        # Start with base profile
        merged_dict = asdict(base)
        
        # Override with non-None values from override profile
        override_dict = asdict(override)
        for key, value in override_dict.items():
            if key in ['name', 'created_at', 'modified_at']:
                continue  # Skip metadata fields
            
            if value is not None and value != getattr(base, key):
                if isinstance(value, dict) and key == 'environment_variables':
                    # Merge environment variables
                    merged_dict[key].update(value)
                elif isinstance(value, list):
                    # Combine lists (removing duplicates)
                    merged_dict[key] = list(set(merged_dict[key] + value))
                else:
                    merged_dict[key] = value
        
        # Create new profile
        merged_dict['name'] = new_name
        merged_dict['description'] = f"Merged profile: {base.description} + {override.description}"
        merged_dict['profile_type'] = ProfileType.CUSTOM
        
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        merged_dict['created_at'] = timestamp
        merged_dict['modified_at'] = timestamp
        
        merged_profile = TestRunnerProfile(**merged_dict)
        
        # Validate merged profile
        errors = self.validate_profile(merged_profile)
        if errors:
            print(f"Merged profile validation failed: {', '.join(errors)}")
            return False
        
        self.profiles[new_name] = merged_profile
        self._save_profiles()
        return True
    
    def get_profile_usage_stats(self) -> Dict[str, Any]:
        """Get statistics about profile usage (would need usage tracking)."""
        # This would require usage tracking to be implemented
        # For now, return basic statistics about available profiles
        
        profile_counts = {}
        for profile in self.profiles.values():
            profile_type = profile.profile_type.value
            profile_counts[profile_type] = profile_counts.get(profile_type, 0) + 1
        
        return {
            'total_profiles': len(self.profiles),
            'profiles_by_type': profile_counts,
            'default_profiles': len(self._get_default_profiles()),
            'custom_profiles': len([p for p in self.profiles.values() 
                                  if p.profile_type == ProfileType.CUSTOM])
        }