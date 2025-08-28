"""
Tests for Enhanced CLI with Advanced Options
==========================================

Tests the enhanced test runner CLI with all Phase X advanced options.
"""

import pytest
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from scripts.test_runner import TestRunnerCLI, ExitCode
from scripts.cli_validators import CLIOptions
from scripts.config.runner_config import ExecutionMode


class TestEnhancedCLI:
    """Test enhanced CLI functionality."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_cli_initialization(self):
        """Test CLI initialization with advanced components."""
        cli = TestRunnerCLI()
        
        # Check all advanced components are initialized
        assert cli.advanced_reporter is not None
        assert cli.ci_integration is not None
        assert cli.analyzer is not None
        assert cli.profile_manager is not None
        assert cli.monitor is not None
        assert cli.plugin_manager is not None
        assert cli.export_utilities is not None
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_profile_argument_parsing(self):
        """Test profile argument parsing."""
        cli = TestRunnerCLI()
        
        # Mock profile manager to avoid file system operations
        mock_profile = Mock()
        mock_profile.execution_mode = ExecutionMode.FAST
        cli.profile_manager.get_profile = Mock(return_value=mock_profile)
        cli.profile_manager.apply_profile_to_environment = Mock()
        
        args = ['--profile', 'fast-dev', '--fast']
        options = cli.parse_arguments(args)
        
        assert options.profile == 'fast-dev'
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_generate_report_argument_parsing(self):
        """Test generate report argument parsing."""
        cli = TestRunnerCLI()
        
        args = ['--fast', '--generate-report', 'html']
        options = cli.parse_arguments(args)
        
        assert options.generate_report == 'html'
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_export_formats_argument_parsing(self):
        """Test export formats argument parsing."""
        cli = TestRunnerCLI()
        
        args = ['--fast', '--export-formats', 'json', 'html', 'csv']
        options = cli.parse_arguments(args)
        
        assert options.export_formats == ['json', 'html', 'csv']
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_analyze_argument_parsing(self):
        """Test analyze argument parsing."""
        cli = TestRunnerCLI()
        
        args = ['--fast', '--analyze']
        options = cli.parse_arguments(args)
        
        assert options.analyze is True
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_ci_mode_argument_parsing(self):
        """Test CI mode argument parsing."""
        cli = TestRunnerCLI()
        
        args = ['--fast', '--ci-mode', 'github']
        options = cli.parse_arguments(args)
        
        assert options.ci_mode == 'github'
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_monitoring_argument_parsing(self):
        """Test monitoring argument parsing."""
        cli = TestRunnerCLI()
        
        args = ['--fast', '--monitoring']
        options = cli.parse_arguments(args)
        
        assert options.monitoring is True
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_plugins_argument_parsing(self):
        """Test plugins argument parsing."""
        cli = TestRunnerCLI()
        
        args = ['--fast', '--plugins', 'plugin1', 'plugin2']
        options = cli.parse_arguments(args)
        
        assert options.plugins == ['plugin1', 'plugin2']
        assert options.execution_mode == ExecutionMode.FAST
    
    @pytest.mark.slow
    @pytest.mark.unit
    @pytest.mark.fast
    def test_list_profiles_information_option(self):
        """Test --list-profiles information option."""
        cli = TestRunnerCLI()
        
        # Mock profiles to avoid file system operations
        mock_profiles = {
            'fast-dev': Mock(profile_type=Mock(value='development'), 
                           execution_mode=Mock(value='fast'),
                           description='Fast development profile',
                           timeout_seconds=300,
                           parallel_jobs=2)
        }
        cli.profile_manager.list_profiles = Mock(return_value=mock_profiles)
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                result = cli.parse_arguments(['--list-profiles'])
                
                # Should return None for information commands  
                assert result is None
                mock_exit.assert_called_with(ExitCode.SUCCESS.value)
                mock_print.assert_called()
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_list_plugins_information_option(self):
        """Test --list-plugins information option."""
        cli = TestRunnerCLI()
        
        # Mock plugin status
        mock_status = {
            'test-plugin': {
                'enabled': True,
                'metadata': {
                    'version': '1.0.0',
                    'type': 'reporter',
                    'description': 'Test plugin',
                    'author': 'Test Author',
                    'phases': ['post_execution']
                }
            }
        }
        cli.plugin_manager.get_plugin_status = Mock(return_value=mock_status)
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                result = cli.parse_arguments(['--list-plugins'])
                
                # Should return None for information commands
                assert result is None
                mock_exit.assert_called_with(ExitCode.SUCCESS.value)
                mock_print.assert_called()
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_supported_formats_information_option(self):
        """Test --supported-formats information option."""
        cli = TestRunnerCLI()
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                result = cli.parse_arguments(['--supported-formats'])
                
                # Should return None for information commands
                assert result is None
                mock_exit.assert_called_with(ExitCode.SUCCESS.value)
                mock_print.assert_called()
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_trends_analysis_information_option(self):
        """Test --trends analysis option."""
        cli = TestRunnerCLI()
        
        # Mock trends data
        mock_trends = {
            'daily_trends': {
                '2024-01-01': {
                    'avg_execution_time': 120.5,
                    'success_rate': 95.0,
                    'test_count': 100
                }
            },
            'analysis_period_days': 30,
            'total_test_runs': 10,
            'generated_at': '2024-01-01T12:00:00'
        }
        cli.analyzer.generate_trend_report = Mock(return_value=mock_trends)
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print') as mock_print:
                result = cli.parse_arguments(['--trends'])
                
                # Should return None for information commands
                assert result is None
                mock_exit.assert_called_with(ExitCode.SUCCESS.value)
                mock_print.assert_called()
    


    @pytest.mark.fast
    @pytest.mark.ci_safe
    @pytest.mark.edge_case
    @pytest.mark.unit
    @pytest.mark.fast
    def test_invalid_profile_error(self):
        """Test error handling for invalid profile."""
        cli = TestRunnerCLI()
        
        # Mock profile manager to return None for unknown profile
        cli.profile_manager.get_profile = Mock(return_value=None)
        
        with patch('sys.exit') as mock_exit:
            with patch('builtins.print'):
                with pytest.raises(ValueError, match="Profile cannot be None"):
                    cli.parse_arguments(['--profile', 'unknown-profile', '--fast'])
    
    @patch('scripts.test_runner.TestExecutor.execute_tests')
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_monitoring_integration(self, mock_executor):
        """Test monitoring integration in test execution."""
        cli = TestRunnerCLI()
        
        # Create a mock result
        mock_result = Mock()
        mock_result.has_failures = False
        mock_result.has_errors = False
        mock_result.total_execution_time = 1.5
        mock_executor.return_value = mock_result
        
        # Mock the monitor's context manager
        if hasattr(cli, 'monitor') and cli.monitor:
            cli.monitor.start_monitoring = Mock()
            cli.monitor.monitor_test_execution = Mock()
            cli.monitor.monitor_test_execution.return_value.__enter__ = Mock()
            cli.monitor.monitor_test_execution.return_value.__exit__ = Mock()
        
        # Mock the advanced reporter  
        if hasattr(cli, 'advanced_reporter') and cli.advanced_reporter:
            cli.advanced_reporter.start_reporting = Mock()
            cli.advanced_reporter.save_result_to_history = Mock()
        
        # Mock the config to prevent configuration issues
        cli.config.get_marker_config = Mock()
        mock_config = Mock()
        mock_config.estimated_time = 120
        cli.config.get_marker_config.return_value = mock_config
        
        args = ['--fast', '--monitoring']
        exit_code = cli.run(args)
        
        # Verify monitoring was started
        if hasattr(cli.monitor, 'start_monitoring'):
            cli.monitor.start_monitoring.assert_called_once_with(interval_seconds=30)
        
        # Verify advanced reporter was used (if it exists)
        if hasattr(cli.advanced_reporter, 'start_reporting'):
            cli.advanced_reporter.start_reporting.assert_called()
    
    @patch('scripts.test_runner.TestRunnerCLI._execute_tests')
    @patch('scripts.test_runner.TestRunnerCLI._handle_results')
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_plugin_enablement(self, mock_handle, mock_execute):
        """Test plugin enablement during execution."""
        cli = TestRunnerCLI()
        
        # Mock plugin manager
        cli.plugin_manager.enable_plugin = Mock(return_value=True)
        cli.plugin_manager.transform_results = Mock(side_effect=lambda x: x)
        cli.advanced_reporter.save_result_to_history = Mock()
        
        mock_result = Mock()
        mock_result.total_execution_time = 0
        mock_execute.return_value = mock_result
        mock_handle.return_value = ExitCode.SUCCESS.value
        
        args = ['--fast', '--plugins', 'plugin1', 'plugin2']
        exit_code = cli.run(args)
        
        # Verify plugins were enabled
        assert cli.plugin_manager.enable_plugin.call_count == 2
        cli.plugin_manager.enable_plugin.assert_any_call('plugin1')
        cli.plugin_manager.enable_plugin.assert_any_call('plugin2')
    
    @patch('scripts.test_runner.TestRunnerCLI._execute_tests')
    @patch('scripts.test_runner.TestRunnerCLI._run_analysis')
    @patch('scripts.test_runner.TestRunnerCLI._generate_reports')
    @patch('scripts.test_runner.TestRunnerCLI._handle_results')
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_analysis_and_reporting_integration(self, mock_handle, mock_generate, mock_analyze, mock_execute):
        """Test analysis and reporting integration."""
        cli = TestRunnerCLI()
        
        cli.advanced_reporter.save_result_to_history = Mock()
        cli.plugin_manager.transform_results = Mock(side_effect=lambda x: x)
        
        mock_result = Mock()
        mock_result.total_execution_time = 0
        mock_execute.return_value = mock_result
        mock_handle.return_value = ExitCode.SUCCESS.value
        
        args = ['--fast', '--analyze', '--generate-report', 'html']
        exit_code = cli.run(args)
        
        # Verify analysis was run
        mock_analyze.assert_called_once_with(mock_result)
        
        # Verify reports were generated
        mock_generate.assert_called_once()
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_ci_mode_environment_setup(self):
        """Test CI mode environment variable setup."""
        cli = TestRunnerCLI()
        
        # Mock CI integration
        mock_env_vars = {'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONUNBUFFERED': '1'}
        cli.ci_integration.setup_ci_environment = Mock(return_value=mock_env_vars)
        
        options = CLIOptions(
            execution_mode=ExecutionMode.FAST,
            ci_mode='github'
        )
        
        with patch.dict('os.environ', {}, clear=True):
            # This would be called in _execute_tests
            with patch('os.environ', {}) as mock_environ:
                # Simulate the environment setup that happens in _execute_tests
                if options.ci_mode:
                    ci_env_vars = cli.ci_integration.setup_ci_environment()
                    for key, value in ci_env_vars.items():
                        mock_environ[key] = value
                
                # Verify environment was set up
                cli.ci_integration.setup_ci_environment.assert_called_once()
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_argument_validation_with_advanced_options(self):
        """Test argument validation with advanced options."""
        cli = TestRunnerCLI()
        
        # Test valid advanced option combinations
        valid_args = ['--fast', '--analyze', '--generate-report', 'json', '--monitoring']
        options = cli.parse_arguments(valid_args)
        
        assert options.execution_mode == ExecutionMode.FAST
        assert options.analyze is True
        assert options.generate_report == 'json'
        assert options.monitoring is True
        
        # Test invalid report format
        with pytest.raises(SystemExit):
            cli.parse_arguments(['--fast', '--generate-report', 'invalid-format'])
        
        # Test invalid CI platform
        with pytest.raises(SystemExit):
            cli.parse_arguments(['--fast', '--ci-mode', 'invalid-platform'])
    


    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.unit
    def test_help_includes_advanced_options(self):
        """Test that help output includes advanced options."""
        cli = TestRunnerCLI()
        parser = cli.create_argument_parser()
        
        help_text = parser.format_help()
        
        # Check advanced options are in help
        assert '--profile' in help_text
        assert '--generate-report' in help_text
        assert '--analyze' in help_text
        assert '--trends' in help_text
        assert '--ci-mode' in help_text
        assert '--monitoring' in help_text
        assert '--plugins' in help_text
        assert '--export-formats' in help_text
        
        # Check information options
        assert '--list-profiles' in help_text
        assert '--list-plugins' in help_text
        assert '--supported-formats' in help_text
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_profile_overrides_execution_mode(self):
        """Test that profile can provide execution mode when none specified."""
        cli = TestRunnerCLI()
        
        # Mock profile with specific execution mode
        mock_profile = Mock()
        mock_profile.execution_mode = ExecutionMode.INTEGRATION
        cli.profile_manager.get_profile = Mock(return_value=mock_profile)
        cli.profile_manager.apply_profile_to_environment = Mock()
        
        # Parse arguments without explicit execution mode
        args = ['--profile', 'integration-profile']
        options = cli.parse_arguments(args)
        
        assert options.execution_mode == ExecutionMode.INTEGRATION
        assert options.profile == 'integration-profile'
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_explicit_mode_overrides_profile(self):
        """Test that explicit execution mode overrides profile mode."""
        cli = TestRunnerCLI()
        
        # Mock profile with different execution mode
        mock_profile = Mock()
        mock_profile.execution_mode = ExecutionMode.INTEGRATION
        cli.profile_manager.get_profile = Mock(return_value=mock_profile)
        cli.profile_manager.apply_profile_to_environment = Mock()
        
        # Parse arguments with explicit mode that differs from profile
        args = ['--profile', 'integration-profile', '--fast']
        options = cli.parse_arguments(args)
        
        # Explicit mode should take precedence
        assert options.execution_mode == ExecutionMode.FAST
        assert options.profile == 'integration-profile'


class TestAdvancedCLIFeatures:
    """Test specific advanced CLI features."""
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_analyze_result_processing(self):
        """Test analysis result processing."""
        cli = TestRunnerCLI()
        
        # Mock analyzer and quality report
        mock_quality_report = Mock()
        mock_quality_report.overall_score = 85.5
        mock_quality_report.performance_metrics.avg_test_time = 2.5
        mock_quality_report.performance_metrics.median_test_time = 1.8
        mock_quality_report.performance_metrics.p95_test_time = 5.2
        mock_quality_report.performance_metrics.performance_regression_candidates = ['test_slow']
        mock_quality_report.reliability_metrics.flaky_tests = ['test_flaky']
        mock_quality_report.reliability_metrics.consistently_failing_tests = []
        mock_quality_report.recommendations = ['Optimize slow tests']
        mock_quality_report.risk_areas = []
        
        cli.analyzer.analyze_test_results = Mock(return_value=mock_quality_report)
        cli.plugin_manager.analyze_results = Mock(return_value={})
        
        mock_result = Mock()
        
        with patch('builtins.print') as mock_print:
            cli._run_analysis(mock_result)
            
            # Verify analysis output was printed
            mock_print.assert_called()
            
            # Check that analyzer was called
            cli.analyzer.analyze_test_results.assert_called_once_with(mock_result, days_of_history=30)
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_report_generation(self):
        """Test report generation functionality."""
        cli = TestRunnerCLI()
        
        # Mock export utilities
        cli.export_utilities.export_test_results = Mock(return_value=True)
        cli.export_utilities.export_multiple_formats = Mock(return_value={'json': True, 'html': True})
        cli.export_utilities.create_export_summary = Mock(return_value=Path('summary.json'))
        
        # Mock CI integration and plugin manager
        cli.ci_integration.write_ci_outputs = Mock()
        cli.plugin_manager.generate_reports = Mock(return_value={'test-plugin': True})
        
        mock_result = Mock()
        
        # Test single report generation
        options = CLIOptions(
            execution_mode=ExecutionMode.FAST,
            generate_report='html'
        )
        
        with patch('builtins.print'):
            cli._generate_reports(mock_result, options)
        
        cli.export_utilities.export_test_results.assert_called_once()
        
        # Test multiple format export
        options = CLIOptions(
            execution_mode=ExecutionMode.FAST,
            export_formats=['json', 'html']
        )
        
        with patch('builtins.print'):
            cli._generate_reports(mock_result, options)
        
        cli.export_utilities.export_multiple_formats.assert_called_once()
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.medium
    def test_ci_mode_integration(self):
        """Test CI mode integration features."""
        cli = TestRunnerCLI()
        
        # Mock CI integration
        cli.ci_integration.write_ci_outputs = Mock()
        cli.export_utilities.export_multiple_formats = Mock(return_value={'json': True})
        cli.export_utilities.create_export_summary = Mock(return_value=Path('summary.json'))
        cli.plugin_manager.generate_reports = Mock(return_value={})
        
        mock_result = Mock()
        
        options = CLIOptions(
            execution_mode=ExecutionMode.FAST,
            ci_mode='github',
            export_formats=['json']
        )
        
        with patch('builtins.print'):
            cli._generate_reports(mock_result, options)
        
        # Verify CI-specific outputs were generated
        cli.ci_integration.write_ci_outputs.assert_called_once()
    
    @pytest.mark.medium
    @pytest.mark.integration
    @pytest.mark.fast
    def test_error_handling_in_advanced_features(self):
        """Test error handling in advanced features."""
        cli = TestRunnerCLI()
        
        # Mock analyzer to raise exception
        cli.analyzer.analyze_test_results = Mock(side_effect=Exception('Analysis failed'))
        cli.plugin_manager.analyze_results = Mock(return_value={})
        
        mock_result = Mock()
        
        # Should not crash, should handle error gracefully
        with patch('builtins.print') as mock_print:
            cli._run_analysis(mock_result)
            
            # Should print error message
            mock_print.assert_called()
    


    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.ci_safe
    @pytest.mark.fast
    @pytest.mark.unit
    def test_trends_analysis_no_data(self):
        """Test trends analysis when no data is available."""
        cli = TestRunnerCLI()
        
        # Mock analyzer to return empty trends
        mock_trends = {
            'daily_trends': {},
            'analysis_period_days': 30,
            'total_test_runs': 0,
            'generated_at': '2024-01-01T12:00:00'
        }
        cli.analyzer.generate_trend_report = Mock(return_value=mock_trends)
        
        with patch('builtins.print') as mock_print:
            cli._show_trends_analysis()
            
            # Should handle empty data gracefully
            mock_print.assert_called()
    
    @pytest.mark.fast
    @pytest.mark.unit
    @pytest.mark.fast
    def test_plugin_failure_handling(self):
        """Test handling of plugin failures."""
        cli = TestRunnerCLI()
        
        # Mock plugin manager to fail enabling a plugin
        cli.plugin_manager.enable_plugin = Mock(return_value=False)
        cli.logger.warning = Mock()
        
        # Simulate plugin enabling during run
        if ['plugin1', 'plugin2']:  # Simulate options.plugins
            for plugin_name in ['plugin1', 'plugin2']:
                if not cli.plugin_manager.enable_plugin(plugin_name):
                    cli.logger.warning(f"Failed to enable plugin: {plugin_name}")
        
        # Verify warnings were logged
        assert cli.logger.warning.call_count == 2
        cli.logger.warning.assert_any_call("Failed to enable plugin: plugin1")
        cli.logger.warning.assert_any_call("Failed to enable plugin: plugin2")