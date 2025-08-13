"""
Configuration Management - Simple, Flexible, Professional
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import argparse


class OutputMode(Enum):
    """Output detail modes."""
    BUSINESS = "business"
    TECHNICAL = "technical"
    VERBOSE = "verbose"


@dataclass
class DemoConfig:
    """Complete configuration for demo execution."""
    # Execution
    mock_mode: bool = True
    scenario: Optional[int] = None
    filter_tags: Optional[List[str]] = None
    
    # Output
    output_format: str = "dashboard"
    output_file: Optional[str] = None
    use_color: bool = True
    quiet_mode: bool = False
    detail_level: OutputMode = OutputMode.BUSINESS
    show_timing: bool = False
    
    # Safety
    skip_confirmation: bool = False
    dry_run: bool = False
    
    # Performance
    timeout: int = 30
    retries: int = 3
    
    # Metadata
    config_source: str = "defaults"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert enums to strings
        if isinstance(data.get('detail_level'), OutputMode):
            data['detail_level'] = data['detail_level'].value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DemoConfig':
        """Create from dictionary."""
        # Convert string to enum
        if 'detail_level' in data and isinstance(data['detail_level'], str):
            data['detail_level'] = OutputMode(data['detail_level'])
        return cls(**data)


class ConfigManager:
    """Manages configuration from multiple sources."""
    
    def __init__(self):
        self.default_config = self._get_defaults()
        self.file_config = {}
        self.cli_config = {}
        self.final_config = None
        
        # Auto-load default config if it exists
        default_config_path = Path("demo_config.yaml")
        if default_config_path.exists():
            self.load_from_file(str(default_config_path))
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            'mock_mode': True,
            'output_format': 'dashboard',
            'use_color': True,
            'quiet_mode': False,
            'detail_level': 'business',
            'show_timing': False,
            'skip_confirmation': False,
            'dry_run': False,
            'timeout': 30,
            'retries': 3,
            'config_source': 'defaults'
        }
    
    def load_from_file(self, filepath: str) -> bool:
        """Load configuration from YAML file."""
        try:
            path = Path(filepath)
            if not path.exists():
                print(f"Warning: Config file not found: {filepath}")
                return False
            
            with open(path, 'r') as f:
                self.file_config = yaml.safe_load(f) or {}
            
            # Validate configuration
            self._validate_config(self.file_config)
            return True
            
        except yaml.YAMLError as e:
            print(f"Error parsing config file: {e}")
            return False
        except Exception as e:
            print(f"Error loading config: {e}")
            return False
    
    def load_from_cli(self, args: argparse.Namespace):
        """Load configuration from CLI arguments."""
        # Convert namespace to dict, filtering None values
        cli_dict = {
            k: v for k, v in vars(args).items()
            if v is not None and k not in ['help', 'config', 'save_config']
        }
        
        # Map CLI args to config keys - only add values that were actually provided
        self.cli_config = {}
        
        # Only set values if they were explicitly provided by user
        if 'live' in cli_dict:
            self.cli_config['mock_mode'] = not cli_dict['live']
        elif 'mock' in cli_dict:
            self.cli_config['mock_mode'] = cli_dict['mock']
        
        if 'scenario' in cli_dict:
            self.cli_config['scenario'] = cli_dict['scenario']
        
        if 'filter' in cli_dict:
            self.cli_config['filter_tags'] = self._parse_filter_tags(cli_dict['filter'])
        
        if 'format' in cli_dict:
            self.cli_config['output_format'] = cli_dict['format']
        
        if 'output' in cli_dict:
            self.cli_config['output_file'] = cli_dict['output']
        
        if 'use_color' in cli_dict:
            self.cli_config['use_color'] = cli_dict['use_color']
        
        if 'quiet' in cli_dict:
            self.cli_config['quiet_mode'] = cli_dict['quiet']
        
        if 'detail_level' in cli_dict:
            self.cli_config['detail_level'] = cli_dict['detail_level']
        
        if 'timing' in cli_dict:
            self.cli_config['show_timing'] = cli_dict['timing']
        
        if 'yes' in cli_dict:
            self.cli_config['skip_confirmation'] = cli_dict['yes']
        
        if 'dry_run' in cli_dict:
            self.cli_config['dry_run'] = cli_dict['dry_run']
        
        if 'timeout' in cli_dict:
            self.cli_config['timeout'] = cli_dict['timeout']
        
        if 'retries' in cli_dict:
            self.cli_config['retries'] = cli_dict['retries']
    
    def _parse_filter_tags(self, filter_str: Optional[str]) -> Optional[List[str]]:
        """Parse filter tags from string."""
        if not filter_str:
            return None
        
        # Split by comma and clean
        tags = [tag.strip().lower() for tag in filter_str.split(',')]
        
        # Validate tags
        valid_tags = {'support', 'inquiry', 'no_longer_works'}
        invalid = set(tags) - valid_tags
        if invalid:
            print(f"Warning: Invalid filter tags ignored: {invalid}")
        
        return [tag for tag in tags if tag in valid_tags]
    
    def _validate_config(self, config: Dict[str, Any]):
        """Validate configuration values."""
        # Validate output format
        valid_formats = {'dashboard', 'simple', 'json', 'table', 'markdown'}
        if 'output_format' in config and config['output_format'] not in valid_formats:
            raise ValueError(f"Invalid output format: {config['output_format']}")
        
        # Validate detail level
        valid_levels = {'business', 'technical', 'verbose'}
        if 'detail_level' in config and config['detail_level'] not in valid_levels:
            raise ValueError(f"Invalid detail level: {config['detail_level']}")
        
        # Validate numeric ranges
        if 'timeout' in config and not (1 <= config['timeout'] <= 300):
            raise ValueError(f"Timeout must be between 1 and 300 seconds")
        
        if 'retries' in config and not (0 <= config['retries'] <= 10):
            raise ValueError(f"Retries must be between 0 and 10")
    
    def get_final_config(self) -> DemoConfig:
        """Get merged configuration with precedence: CLI > File > Defaults."""
        # Start with defaults
        final = self.default_config.copy()
        
        # Merge file config
        final.update(self.file_config)
        
        # Merge CLI config (highest priority)
        final.update(self.cli_config)
        
        # Track config source
        if self.cli_config:
            final['config_source'] = 'cli'
        elif self.file_config:
            final['config_source'] = 'file'
        
        # Convert to DemoConfig object
        self.final_config = DemoConfig.from_dict(final)
        return self.final_config
    
    def save_to_file(self, filepath: str, config: Optional[DemoConfig] = None):
        """Save configuration to YAML file."""
        config = config or self.final_config
        if not config:
            raise ValueError("No configuration to save")
        
        try:
            path = Path(filepath)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to dict and clean
            data = config.to_dict()
            
            # Remove runtime-only fields
            data.pop('config_source', None)
            
            # Write YAML with comments
            with open(path, 'w') as f:
                f.write("# E2E Demo Configuration\n")
                f.write("# Generated automatically - modify as needed\n\n")
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            print(f"Configuration saved to: {filepath}")
            
        except Exception as e:
            print(f"Error saving configuration: {e}")
            raise