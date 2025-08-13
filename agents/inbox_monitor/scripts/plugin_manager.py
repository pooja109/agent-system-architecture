"""
Plugin Manager for Test Runner CLI Extensibility
================================================

Provides plugin architecture for extending test runner functionality.
"""

import json
import importlib
import importlib.util
import inspect
import sys
from typing import Dict, List, Optional, Any, Callable, Type
from dataclasses import dataclass, field
from pathlib import Path
from abc import ABC, abstractmethod
from enum import Enum

try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

class PluginType(Enum):
    """Types of plugins supported."""
    REPORTER = "reporter"
    ANALYZER = "analyzer"
    EXPORTER = "exporter"
    VALIDATOR = "validator"
    TRANSFORMER = "transformer"
    HOOK = "hook"

class PluginPhase(Enum):
    """Execution phases where plugins can hook in."""
    PRE_EXECUTION = "pre_execution"
    POST_EXECUTION = "post_execution"
    PRE_REPORTING = "pre_reporting"
    POST_REPORTING = "post_reporting"
    ON_FAILURE = "on_failure"
    ON_SUCCESS = "on_success"

@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    supported_phases: List[PluginPhase] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    enabled: bool = True

class TestRunnerPlugin(ABC):
    """Base class for all test runner plugins."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.metadata: Optional[PluginMetadata] = None
    
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        pass
    
    def initialize(self) -> bool:
        """Initialize the plugin. Return True if successful."""
        return True
    
    def cleanup(self):
        """Clean up plugin resources."""
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate plugin configuration. Return list of errors."""
        return []

class ReporterPlugin(TestRunnerPlugin):
    """Base class for reporter plugins."""
    
    @abstractmethod
    def generate_report(self, result: TestResult, output_path: Path) -> bool:
        """Generate a report from test results."""
        pass

class AnalyzerPlugin(TestRunnerPlugin):
    """Base class for analyzer plugins."""
    
    @abstractmethod
    def analyze_results(self, result: TestResult) -> Dict[str, Any]:
        """Analyze test results and return insights."""
        pass

class ExporterPlugin(TestRunnerPlugin):
    """Base class for exporter plugins."""
    
    @abstractmethod
    def export_data(self, data: Dict[str, Any], output_path: Path, format_options: Dict[str, Any]) -> bool:
        """Export data in a specific format."""
        pass

class ValidatorPlugin(TestRunnerPlugin):
    """Base class for validator plugins."""
    
    @abstractmethod
    def validate_execution(self, execution_mode: ExecutionMode, config: Dict[str, Any]) -> List[str]:
        """Validate test execution setup. Return list of warnings/errors."""
        pass

class TransformerPlugin(TestRunnerPlugin):
    """Base class for transformer plugins."""
    
    @abstractmethod
    def transform_results(self, result: TestResult) -> TestResult:
        """Transform test results."""
        pass

class HookPlugin(TestRunnerPlugin):
    """Base class for hook plugins that run at specific phases."""
    
    @abstractmethod
    def execute_hook(self, phase: PluginPhase, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hook at specified phase."""
        pass

@dataclass
class PluginRegistry:
    """Registry of loaded plugins."""
    plugins: Dict[str, TestRunnerPlugin] = field(default_factory=dict)
    metadata: Dict[str, PluginMetadata] = field(default_factory=dict)
    enabled_plugins: Dict[str, bool] = field(default_factory=dict)

class PluginManager:
    """Manages plugin loading, execution, and lifecycle."""
    
    def __init__(self, plugin_dir: Optional[Path] = None, config_file: Optional[Path] = None):
        self.plugin_dir = plugin_dir or Path("plugins")
        self.config_file = config_file or Path("plugin_config.json")
        self.registry = PluginRegistry()
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._hooks: Dict[PluginPhase, List[HookPlugin]] = {phase: [] for phase in PluginPhase}
        
        self._load_plugin_configs()
        self._discover_and_load_plugins()
    
    def _load_plugin_configs(self):
        """Load plugin configurations from file."""
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text())
                self._plugin_configs = data.get('plugin_configs', {})
                
                # Load enabled/disabled status
                for plugin_name, enabled in data.get('enabled_plugins', {}).items():
                    self.registry.enabled_plugins[plugin_name] = enabled
                    
            except (json.JSONError, KeyError) as e:
                print(f"Warning: Could not load plugin config from {self.config_file}: {e}")
    
    def _save_plugin_configs(self):
        """Save plugin configurations to file."""
        try:
            data = {
                'plugin_configs': self._plugin_configs,
                'enabled_plugins': self.registry.enabled_plugins
            }
            self.config_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            print(f"Error saving plugin config: {e}")
    
    def _discover_and_load_plugins(self):
        """Discover and load plugins from plugin directory."""
        if not self.plugin_dir.exists():
            self.plugin_dir.mkdir(exist_ok=True)
            return
        
        # Look for Python files in plugin directory
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue  # Skip private files
            
            self._load_plugin_from_file(plugin_file)
        
        # Look for plugin packages
        for plugin_dir in self.plugin_dir.iterdir():
            if plugin_dir.is_dir() and not plugin_dir.name.startswith("_"):
                init_file = plugin_dir / "__init__.py"
                if init_file.exists():
                    self._load_plugin_from_package(plugin_dir)
    
    def _load_plugin_from_file(self, plugin_file: Path):
        """Load a plugin from a Python file."""
        try:
            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if not spec or not spec.loader:
                return
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find plugin classes in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, TestRunnerPlugin) and 
                    obj != TestRunnerPlugin and 
                    not inspect.isabstract(obj)):
                    self._register_plugin_class(obj, plugin_file.stem)
                    
        except Exception as e:
            print(f"Error loading plugin from {plugin_file}: {e}")
    
    def _load_plugin_from_package(self, plugin_dir: Path):
        """Load a plugin from a package directory."""
        try:
            # Add plugin directory to path temporarily
            if str(plugin_dir.parent) not in sys.path:
                sys.path.insert(0, str(plugin_dir.parent))
            
            module = importlib.import_module(plugin_dir.name)
            
            # Find plugin classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if (issubclass(obj, TestRunnerPlugin) and 
                    obj != TestRunnerPlugin and 
                    not inspect.isabstract(obj)):
                    self._register_plugin_class(obj, plugin_dir.name)
                    
        except Exception as e:
            print(f"Error loading plugin package from {plugin_dir}: {e}")
        finally:
            # Clean up path
            if str(plugin_dir.parent) in sys.path:
                sys.path.remove(str(plugin_dir.parent))
    
    def _register_plugin_class(self, plugin_class: Type[TestRunnerPlugin], source_name: str):
        """Register a plugin class."""
        try:
            # Get plugin configuration
            plugin_config = self._plugin_configs.get(source_name, {})
            
            # Instantiate plugin
            plugin = plugin_class(plugin_config)
            metadata = plugin.get_metadata()
            
            # Validate metadata
            if not self._validate_metadata(metadata):
                print(f"Invalid metadata for plugin {metadata.name}")
                return
            
            # Check if plugin is enabled
            is_enabled = self.registry.enabled_plugins.get(metadata.name, metadata.enabled)
            
            # Initialize plugin if enabled
            if is_enabled:
                if not plugin.initialize():
                    print(f"Failed to initialize plugin {metadata.name}")
                    return
            
            # Register plugin
            self.registry.plugins[metadata.name] = plugin
            self.registry.metadata[metadata.name] = metadata
            self.registry.enabled_plugins[metadata.name] = is_enabled
            
            # Register hooks
            if isinstance(plugin, HookPlugin):
                for phase in metadata.supported_phases:
                    self._hooks[phase].append(plugin)
            
            print(f"Loaded plugin: {metadata.name} v{metadata.version} ({'enabled' if is_enabled else 'disabled'})")
            
        except Exception as e:
            print(f"Error registering plugin class {plugin_class.__name__}: {e}")
    
    def _validate_metadata(self, metadata: PluginMetadata) -> bool:
        """Validate plugin metadata."""
        if not metadata.name or not metadata.version:
            return False
        
        if not isinstance(metadata.plugin_type, PluginType):
            return False
        
        if not all(isinstance(phase, PluginPhase) for phase in metadata.supported_phases):
            return False
        
        return True
    
    def get_plugin(self, name: str) -> Optional[TestRunnerPlugin]:
        """Get a plugin by name."""
        return self.registry.plugins.get(name)
    
    def list_plugins(self, plugin_type: Optional[PluginType] = None) -> Dict[str, PluginMetadata]:
        """List available plugins, optionally filtered by type."""
        plugins = {}
        
        for name, metadata in self.registry.metadata.items():
            if plugin_type is None or metadata.plugin_type == plugin_type:
                plugins[name] = metadata
        
        return plugins
    
    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin."""
        if name not in self.registry.plugins:
            return False
        
        plugin = self.registry.plugins[name]
        if not plugin.initialize():
            return False
        
        self.registry.enabled_plugins[name] = True
        self._save_plugin_configs()
        
        # Add to hooks if it's a hook plugin
        if isinstance(plugin, HookPlugin):
            metadata = self.registry.metadata[name]
            for phase in metadata.supported_phases:
                if plugin not in self._hooks[phase]:
                    self._hooks[phase].append(plugin)
        
        return True
    
    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin."""
        if name not in self.registry.plugins:
            return False
        
        plugin = self.registry.plugins[name]
        plugin.cleanup()
        
        self.registry.enabled_plugins[name] = False
        self._save_plugin_configs()
        
        # Remove from hooks if it's a hook plugin
        if isinstance(plugin, HookPlugin):
            metadata = self.registry.metadata[name]
            for phase in metadata.supported_phases:
                if plugin in self._hooks[phase]:
                    self._hooks[phase].remove(plugin)
        
        return True
    
    def is_plugin_enabled(self, name: str) -> bool:
        """Check if a plugin is enabled."""
        return self.registry.enabled_plugins.get(name, False)
    
    def configure_plugin(self, name: str, config: Dict[str, Any]) -> bool:
        """Configure a plugin."""
        if name not in self.registry.plugins:
            return False
        
        plugin = self.registry.plugins[name]
        
        # Validate configuration
        errors = plugin.validate_config(config)
        if errors:
            print(f"Plugin configuration validation failed: {', '.join(errors)}")
            return False
        
        # Update configuration
        self._plugin_configs[name] = config
        plugin.config = config
        
        self._save_plugin_configs()
        return True
    
    def execute_hooks(self, phase: PluginPhase, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute all hooks for a specific phase."""
        results = {}
        
        for plugin in self._hooks[phase]:
            if self.is_plugin_enabled(plugin.get_metadata().name):
                try:
                    result = plugin.execute_hook(phase, context.copy())
                    results[plugin.get_metadata().name] = result
                except Exception as e:
                    print(f"Error executing hook {plugin.get_metadata().name} in phase {phase.value}: {e}")
                    results[plugin.get_metadata().name] = {'error': str(e)}
        
        return results
    
    def generate_reports(self, result: TestResult, output_dir: Path) -> Dict[str, bool]:
        """Generate reports using all enabled reporter plugins."""
        results = {}
        
        reporter_plugins = [
            plugin for name, plugin in self.registry.plugins.items()
            if (isinstance(plugin, ReporterPlugin) and 
                self.is_plugin_enabled(name))
        ]
        
        for plugin in reporter_plugins:
            plugin_name = plugin.get_metadata().name
            try:
                plugin_output_dir = output_dir / plugin_name
                plugin_output_dir.mkdir(exist_ok=True)
                
                success = plugin.generate_report(result, plugin_output_dir)
                results[plugin_name] = success
                
            except Exception as e:
                print(f"Error in reporter plugin {plugin_name}: {e}")
                results[plugin_name] = False
        
        return results
    
    def analyze_results(self, result: TestResult) -> Dict[str, Dict[str, Any]]:
        """Analyze results using all enabled analyzer plugins."""
        analyses = {}
        
        analyzer_plugins = [
            plugin for name, plugin in self.registry.plugins.items()
            if (isinstance(plugin, AnalyzerPlugin) and 
                self.is_plugin_enabled(name))
        ]
        
        for plugin in analyzer_plugins:
            plugin_name = plugin.get_metadata().name
            try:
                analysis = plugin.analyze_results(result)
                analyses[plugin_name] = analysis
                
            except Exception as e:
                print(f"Error in analyzer plugin {plugin_name}: {e}")
                analyses[plugin_name] = {'error': str(e)}
        
        return analyses
    
    def validate_execution(self, execution_mode: ExecutionMode, config: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate execution using all enabled validator plugins."""
        validations = {}
        
        validator_plugins = [
            plugin for name, plugin in self.registry.plugins.items()
            if (isinstance(plugin, ValidatorPlugin) and 
                self.is_plugin_enabled(name))
        ]
        
        for plugin in validator_plugins:
            plugin_name = plugin.get_metadata().name
            try:
                warnings = plugin.validate_execution(execution_mode, config)
                if warnings:
                    validations[plugin_name] = warnings
                    
            except Exception as e:
                print(f"Error in validator plugin {plugin_name}: {e}")
                validations[plugin_name] = [f"Plugin error: {str(e)}"]
        
        return validations
    
    def transform_results(self, result: TestResult) -> TestResult:
        """Transform results using all enabled transformer plugins."""
        transformer_plugins = [
            plugin for name, plugin in self.registry.plugins.items()
            if (isinstance(plugin, TransformerPlugin) and 
                self.is_plugin_enabled(name))
        ]
        
        transformed_result = result
        
        for plugin in transformer_plugins:
            plugin_name = plugin.get_metadata().name
            try:
                transformed_result = plugin.transform_results(transformed_result)
                
            except Exception as e:
                print(f"Error in transformer plugin {plugin_name}: {e}")
        
        return transformed_result
    
    def export_data(self, data: Dict[str, Any], output_dir: Path, format_options: Dict[str, Any]) -> Dict[str, bool]:
        """Export data using all enabled exporter plugins."""
        results = {}
        
        exporter_plugins = [
            plugin for name, plugin in self.registry.plugins.items()
            if (isinstance(plugin, ExporterPlugin) and 
                self.is_plugin_enabled(name))
        ]
        
        for plugin in exporter_plugins:
            plugin_name = plugin.get_metadata().name
            try:
                plugin_output_path = output_dir / f"{plugin_name}_export"
                success = plugin.export_data(data, plugin_output_path, format_options)
                results[plugin_name] = success
                
            except Exception as e:
                print(f"Error in exporter plugin {plugin_name}: {e}")
                results[plugin_name] = False
        
        return results
    
    def install_plugin(self, plugin_path: Path, enable: bool = True) -> bool:
        """Install a plugin from a file or directory."""
        try:
            if plugin_path.is_file():
                # Copy file to plugin directory
                target_file = self.plugin_dir / plugin_path.name
                target_file.write_text(plugin_path.read_text())
                self._load_plugin_from_file(target_file)
                
            elif plugin_path.is_dir():
                # Copy directory to plugin directory
                target_dir = self.plugin_dir / plugin_path.name
                if target_dir.exists():
                    import shutil
                    shutil.rmtree(target_dir)
                
                import shutil
                shutil.copytree(plugin_path, target_dir)
                self._load_plugin_from_package(target_dir)
            
            else:
                return False
            
            # Enable if requested
            if enable:
                # Find the newly loaded plugin
                for name, metadata in self.registry.metadata.items():
                    if not self.is_plugin_enabled(name):
                        self.enable_plugin(name)
                        break
            
            return True
            
        except Exception as e:
            print(f"Error installing plugin from {plugin_path}: {e}")
            return False
    
    def uninstall_plugin(self, name: str) -> bool:
        """Uninstall a plugin."""
        if name not in self.registry.plugins:
            return False
        
        try:
            # Disable and cleanup
            self.disable_plugin(name)
            plugin = self.registry.plugins[name]
            plugin.cleanup()
            
            # Remove from registry
            del self.registry.plugins[name]
            del self.registry.metadata[name]
            del self.registry.enabled_plugins[name]
            
            # Remove configuration
            if name in self._plugin_configs:
                del self._plugin_configs[name]
            
            self._save_plugin_configs()
            
            # Note: We don't delete the plugin files automatically for safety
            print(f"Plugin {name} uninstalled. Plugin files remain in {self.plugin_dir}")
            
            return True
            
        except Exception as e:
            print(f"Error uninstalling plugin {name}: {e}")
            return False
    
    def get_plugin_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all plugins."""
        status = {}
        
        for name, metadata in self.registry.metadata.items():
            plugin = self.registry.plugins[name]
            
            status[name] = {
                'metadata': {
                    'name': metadata.name,
                    'version': metadata.version,
                    'description': metadata.description,
                    'author': metadata.author,
                    'type': metadata.plugin_type.value,
                    'phases': [phase.value for phase in metadata.supported_phases]
                },
                'enabled': self.is_plugin_enabled(name),
                'configuration': self._plugin_configs.get(name, {}),
                'dependencies': metadata.dependencies
            }
        
        return status
    
    def create_plugin_template(self, plugin_name: str, plugin_type: PluginType, output_path: Path) -> bool:
        """Create a plugin template file."""
        try:
            template_content = self._generate_plugin_template(plugin_name, plugin_type)
            output_path.write_text(template_content)
            return True
        except Exception as e:
            print(f"Error creating plugin template: {e}")
            return False
    
    def _generate_plugin_template(self, plugin_name: str, plugin_type: PluginType) -> str:
        """Generate plugin template code."""
        class_name = f"{plugin_name.replace('_', '').title()}Plugin"
        base_class = {
            PluginType.REPORTER: "ReporterPlugin",
            PluginType.ANALYZER: "AnalyzerPlugin", 
            PluginType.EXPORTER: "ExporterPlugin",
            PluginType.VALIDATOR: "ValidatorPlugin",
            PluginType.TRANSFORMER: "TransformerPlugin",
            PluginType.HOOK: "HookPlugin"
        }[plugin_type]
        
        template = f'''"""
{plugin_name} Plugin for Test Runner CLI
{'=' * (len(plugin_name) + 30)}

Auto-generated plugin template.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path

from plugin_manager import {base_class}, PluginMetadata, PluginType, PluginPhase
try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode


class {class_name}({base_class}):
    """Custom {plugin_type.value} plugin."""
    
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata."""
        return PluginMetadata(
            name="{plugin_name}",
            version="1.0.0", 
            description="Description for {plugin_name} plugin",
            author="Your Name",
            plugin_type=PluginType.{plugin_type.name},
            supported_phases=[
                # Add supported phases here, e.g.:
                # PluginPhase.POST_EXECUTION,
                # PluginPhase.PRE_REPORTING
            ],
            dependencies=[],
            enabled=True
        )
    
    def initialize(self) -> bool:
        """Initialize the plugin."""
        # Add initialization logic here
        return True
    
    def cleanup(self):
        """Clean up plugin resources."""
        # Add cleanup logic here
        pass
    
    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate plugin configuration."""
        errors = []
        # Add configuration validation here
        return errors
'''
        
        # Add method specific to plugin type
        if plugin_type == PluginType.REPORTER:
            template += '''
    def generate_report(self, result: TestResult, output_path: Path) -> bool:
        """Generate a report from test results."""
        try:
            # Add report generation logic here
            report_file = output_path / "report.txt"
            report_file.write_text(f"Test Report: {result.total_tests} tests executed")
            return True
        except Exception as e:
            print(f"Error generating report: {e}")
            return False
'''
        
        elif plugin_type == PluginType.ANALYZER:
            template += '''
    def analyze_results(self, result: TestResult) -> Dict[str, Any]:
        """Analyze test results and return insights."""
        return {
            "total_tests": result.total_tests,
            "success_rate": result.success_rate,
            "analysis_timestamp": "2024-01-01T00:00:00",
            # Add your analysis logic here
        }
'''
        
        elif plugin_type == PluginType.EXPORTER:
            template += '''
    def export_data(self, data: Dict[str, Any], output_path: Path, format_options: Dict[str, Any]) -> bool:
        """Export data in a specific format."""
        try:
            # Add export logic here
            output_path.mkdir(exist_ok=True)
            export_file = output_path / "exported_data.json"
            
            import json
            export_file.write_text(json.dumps(data, indent=2))
            return True
        except Exception as e:
            print(f"Error exporting data: {e}")
            return False
'''
        
        elif plugin_type == PluginType.VALIDATOR:
            template += '''
    def validate_execution(self, execution_mode: ExecutionMode, config: Dict[str, Any]) -> List[str]:
        """Validate test execution setup."""
        warnings = []
        
        # Add validation logic here
        # Example:
        # if execution_mode == ExecutionMode.FULL and config.get('timeout', 0) < 3600:
        #     warnings.append("Full execution mode may need longer timeout")
        
        return warnings
'''
        
        elif plugin_type == PluginType.TRANSFORMER:
            template += '''
    def transform_results(self, result: TestResult) -> TestResult:
        """Transform test results."""
        # Add transformation logic here
        # You can modify the result object or create a new one
        
        # Example: Add a custom field
        # result.custom_data = {"transformed": True}
        
        return result
'''
        
        elif plugin_type == PluginType.HOOK:
            template += '''
    def execute_hook(self, phase: PluginPhase, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute hook at specified phase."""
        result = {"plugin": "{plugin_name}", "phase": phase.value}
        
        if phase == PluginPhase.PRE_EXECUTION:
            # Add pre-execution logic here
            result["action"] = "pre_execution_completed"
        
        elif phase == PluginPhase.POST_EXECUTION:
            # Add post-execution logic here
            result["action"] = "post_execution_completed"
        
        # Add other phases as needed
        
        return result
'''
        
        return template
    
    def shutdown(self):
        """Shutdown plugin manager and cleanup all plugins."""
        for name, plugin in self.registry.plugins.items():
            if self.is_plugin_enabled(name):
                try:
                    plugin.cleanup()
                except Exception as e:
                    print(f"Error cleaning up plugin {name}: {e}")
        
        self.registry.plugins.clear()
        self.registry.metadata.clear()
        self._hooks = {phase: [] for phase in PluginPhase}