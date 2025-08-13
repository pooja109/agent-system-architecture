"""
E2E Demo Package - Clean, Modular, Professional
"""

from .runner import DemoRunner
from .config import DemoConfig, ConfigManager, OutputMode
from .scenario_loader import Scenario, ScenarioResult, ScenarioFactory
from .formatters import OutputFormat, FormatterFactory
from .cli_parser import CLIParser
from .output_manager import OutputManager

__all__ = [
    'DemoRunner',
    'DemoConfig',
    'ConfigManager',
    'OutputMode',
    'Scenario',
    'ScenarioResult',
    'ScenarioFactory',
    'OutputFormat',
    'FormatterFactory',
    'CLIParser',
    'OutputManager'
]

__version__ = '2.0.0'