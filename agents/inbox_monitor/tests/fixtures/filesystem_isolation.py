"""
File system isolation for preventing test conflicts.

This module provides comprehensive file system isolation to prevent tests from
interfering with each other through shared files, directories, and configuration.
"""
import pytest
import tempfile
import shutil
import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from contextlib import contextmanager
import threading


class FileSystemManager:
    """Manages isolated file system environments for tests."""
    
    def __init__(self):
        self.temp_dirs: List[Path] = []
        self.temp_files: List[Path] = []
        self.original_cwd: Optional[Path] = None
        self.backup_files: Dict[Path, bytes] = {}
        self.monitored_paths: List[Path] = []
        self.config_backups: Dict[Path, str] = {}
        self.env_backups: Dict[str, str] = {}
        self.lock = threading.Lock()
    
    def create_temp_directory(self, prefix: str = "test_", suffix: str = "") -> Path:
        """Create a temporary directory for test use."""
        with self.lock:
            temp_dir = Path(tempfile.mkdtemp(prefix=prefix, suffix=suffix))
            self.temp_dirs.append(temp_dir)
            return temp_dir
    
    def create_temp_file(self, content: str = "", suffix: str = ".txt", 
                        directory: Optional[Path] = None, filename: Optional[str] = None) -> Path:
        """Create a temporary file with optional content."""
        if directory is None:
            directory = self.create_temp_directory("test_file_dir_")
        
        if filename:
            temp_path = directory / filename
            temp_path.write_text(content, encoding='utf-8')
        else:
            fd, path = tempfile.mkstemp(suffix=suffix, dir=str(directory))
            temp_path = Path(path)
            
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
        
        with self.lock:
            self.temp_files.append(temp_path)
            return temp_path
    
    def create_config_file(self, config_data: Dict[str, Any], filename: str = "config.json", 
                          directory: Optional[Path] = None) -> Path:
        """Create a temporary configuration file with JSON data."""
        config_content = json.dumps(config_data, indent=2)
        return self.create_temp_file(config_content, suffix=".json", 
                                   directory=directory, filename=filename)
    
    def create_env_file(self, env_vars: Dict[str, str], filename: str = ".env", 
                       directory: Optional[Path] = None) -> Path:
        """Create a temporary environment file."""
        env_content = '\n'.join(f"{key}={value}" for key, value in env_vars.items())
        return self.create_temp_file(env_content, suffix="", 
                                   directory=directory, filename=filename)
    
    def backup_file(self, file_path: Union[str, Path]):
        """Backup a file before test modifications."""
        file_path = Path(file_path)
        if file_path.exists():
            with self.lock:
                try:
                    self.backup_files[file_path] = file_path.read_bytes()
                    self.monitored_paths.append(file_path)
                except (OSError, IOError, PermissionError):
                    # Can't backup file, skip
                    pass
    
    def backup_config_file(self, file_path: Union[str, Path]):
        """Backup a configuration file with text content."""
        file_path = Path(file_path)
        if file_path.exists():
            with self.lock:
                try:
                    self.config_backups[file_path] = file_path.read_text(encoding='utf-8')
                    self.monitored_paths.append(file_path)
                except (OSError, IOError, PermissionError, UnicodeDecodeError):
                    # Can't backup config file, skip
                    pass
    
    def isolate_working_directory(self, temp_dir: Optional[Path] = None) -> Path:
        """Change to isolated working directory for test."""
        if temp_dir is None:
            temp_dir = self.create_temp_directory("test_workdir_")
        
        self.original_cwd = Path.cwd()
        try:
            os.chdir(temp_dir)
        except (OSError, IOError):
            # Can't change directory, skip isolation
            pass
        
        return temp_dir
    
    def isolate_environment_variables(self, **env_vars):
        """Temporarily set environment variables for test isolation."""
        for key, value in env_vars.items():
            if key in os.environ:
                self.env_backups[key] = os.environ[key]
            os.environ[key] = str(value)
    
    def create_project_structure(self, base_dir: Optional[Path] = None) -> Dict[str, Path]:
        """Create a typical project structure for testing."""
        if base_dir is None:
            base_dir = self.create_temp_directory("test_project_")
        
        structure = {
            'base': base_dir,
            'config': base_dir / "config",
            'logs': base_dir / "logs", 
            'data': base_dir / "data",
            'tmp': base_dir / "tmp"
        }
        
        # Create directories
        for dir_path in structure.values():
            if isinstance(dir_path, Path):
                dir_path.mkdir(parents=True, exist_ok=True)
        
        # Create common config files
        config_data = {
            "test_mode": True,
            "debug": False,
            "log_level": "INFO"
        }
        self.create_config_file(config_data, "settings.json", structure['config'])
        
        env_vars = {
            "TEST_MODE": "true",
            "LOG_LEVEL": "INFO",
            "CONFIG_DIR": str(structure['config'])
        }
        self.create_env_file(env_vars, ".env", structure['base'])
        
        return structure
    
    def cleanup_filesystem(self):
        """Clean up all temporary files and restore state."""
        with self.lock:
            # Restore original working directory
            if self.original_cwd and self.original_cwd.exists():
                try:
                    os.chdir(self.original_cwd)
                except (OSError, IOError):
                    pass  # Ignore directory restoration errors
            
            # Restore environment variables
            for key, value in self.env_backups.items():
                os.environ[key] = value
            
            # Remove temporary environment variables
            temp_env_keys = set(os.environ.keys()) - set(self.env_backups.keys())
            for key in temp_env_keys:
                if key.startswith('TEST_'):  # Only remove test-related vars
                    try:
                        del os.environ[key]
                    except KeyError:
                        pass
            
            # Restore backed up files
            for file_path, content in self.backup_files.items():
                try:
                    file_path.write_bytes(content)
                except (OSError, IOError, PermissionError):
                    pass  # File might have been deleted or is not writable
            
            # Restore backed up config files
            for file_path, content in self.config_backups.items():
                try:
                    file_path.write_text(content, encoding='utf-8')
                except (OSError, IOError, PermissionError, UnicodeDecodeError):
                    pass
            
            # Remove temporary files
            for temp_file in self.temp_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except (OSError, IOError, PermissionError):
                    pass  # Ignore file removal errors
            
            # Remove temporary directories
            for temp_dir in self.temp_dirs:
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except (OSError, IOError, PermissionError):
                    pass  # Ignore directory removal errors
            
            # Clear tracking
            self.temp_dirs.clear()
            self.temp_files.clear()
            self.backup_files.clear()
            self.config_backups.clear()
            self.env_backups.clear()
            self.monitored_paths.clear()
            self.original_cwd = None
    
    def get_filesystem_stats(self) -> Dict[str, Any]:
        """Get statistics about current filesystem isolation state."""
        return {
            'temp_directories': len(self.temp_dirs),
            'temp_files': len(self.temp_files),
            'backed_up_files': len(self.backup_files),
            'backed_up_configs': len(self.config_backups),
            'monitored_paths': len(self.monitored_paths),
            'env_backups': len(self.env_backups),
            'working_directory_changed': self.original_cwd is not None
        }


@pytest.fixture(scope="function")
def isolated_filesystem():
    """Provide isolated file system environment for each test."""
    manager = FileSystemManager()
    
    try:
        yield manager
    finally:
        manager.cleanup_filesystem()


@pytest.fixture(scope="function")
def temp_config_dir(isolated_filesystem):
    """Provide temporary configuration directory for tests."""
    config_dir = isolated_filesystem.create_temp_directory("test_config_")
    
    # Create common config files
    config_data = {
        "test_mode": True,
        "debug": False,
        "azure_endpoint": "https://test.openai.azure.com/",
        "graph_endpoint": "https://graph.microsoft.com",
        "log_level": "INFO"
    }
    isolated_filesystem.create_config_file(config_data, "settings.json", config_dir)
    
    env_vars = {
        "TEST_ENV": "true",
        "DEBUG_MODE": "false",
        "CONFIG_PATH": str(config_dir / "settings.json")
    }
    isolated_filesystem.create_env_file(env_vars, ".env", config_dir)
    
    return config_dir


@pytest.fixture(scope="function")
def temp_log_dir(isolated_filesystem):
    """Provide temporary log directory for tests."""
    log_dir = isolated_filesystem.create_temp_directory("test_logs_")
    
    # Create log file structure
    (log_dir / "app.log").touch()
    (log_dir / "error.log").touch()
    (log_dir / "debug.log").touch()
    
    return log_dir


@pytest.fixture(scope="function")
def temp_work_dir(isolated_filesystem):
    """Provide temporary working directory for tests."""
    work_dir = isolated_filesystem.create_temp_directory("test_work_")
    isolated_filesystem.isolate_working_directory(work_dir)
    return work_dir


@pytest.fixture(scope="function")
def project_structure(isolated_filesystem):
    """Provide complete isolated project structure for tests."""
    return isolated_filesystem.create_project_structure()


@contextmanager
def isolated_file_operations(file_path: Union[str, Path], backup: bool = True):
    """Context manager for isolated file operations."""
    file_path = Path(file_path)
    backup_content = None
    file_existed = file_path.exists()
    
    # Backup original content if file exists and backup is requested
    if file_existed and backup:
        try:
            backup_content = file_path.read_bytes()
        except (OSError, IOError, PermissionError):
            backup_content = None
    
    try:
        yield file_path
    finally:
        # Restore original content or remove file
        try:
            if backup_content is not None:
                file_path.write_bytes(backup_content)
            elif not file_existed and file_path.exists():
                # File was created during test, remove it
                file_path.unlink()
        except (OSError, IOError, PermissionError):
            pass  # Ignore restoration errors


@contextmanager
def isolated_config_environment(**config_vars):
    """Context manager for isolated configuration environment."""
    original_env = {}
    temp_config_file = None
    
    try:
        # Backup original environment variables
        for key in config_vars:
            if key in os.environ:
                original_env[key] = os.environ[key]
            os.environ[key] = str(config_vars[key])
        
        # Create temporary config file if requested
        if 'CONFIG_FILE' in config_vars:
            import tempfile
            import json
            
            fd, temp_path = tempfile.mkstemp(suffix='.json', prefix='test_config_')
            temp_config_file = Path(temp_path)
            
            with os.fdopen(fd, 'w') as f:
                json.dump({k: v for k, v in config_vars.items() if k != 'CONFIG_FILE'}, f)
            
            os.environ['CONFIG_FILE'] = str(temp_config_file)
        
        yield config_vars
    finally:
        # Restore original environment
        for key, value in original_env.items():
            os.environ[key] = value
        
        # Remove temporary variables
        for key in config_vars:
            if key not in original_env and key in os.environ:
                try:
                    del os.environ[key]
                except KeyError:
                    pass
        
        # Clean up temporary config file
        if temp_config_file and temp_config_file.exists():
            try:
                temp_config_file.unlink()
            except (OSError, IOError):
                pass


class FileSystemValidator:
    """Validates filesystem isolation and prevents conflicts."""
    
    def __init__(self):
        self.initial_files: Set[Path] = set()
        self.initial_dirs: Set[Path] = set()
    
    def capture_initial_state(self, monitor_path: Path = None):
        """Capture initial filesystem state."""
        if monitor_path is None:
            monitor_path = Path.cwd()
        
        try:
            self.initial_files = {f for f in monitor_path.rglob('*') if f.is_file()}
            self.initial_dirs = {d for d in monitor_path.rglob('*') if d.is_dir()}
        except (OSError, PermissionError):
            # Can't access path, skip monitoring
            pass
    
    def validate_isolation(self, monitor_path: Path = None) -> Dict[str, Any]:
        """Validate filesystem isolation after test."""
        if monitor_path is None:
            monitor_path = Path.cwd()
        
        validation_results = {
            'isolation_success': True,
            'issues': [],
            'new_files': [],
            'new_directories': []
        }
        
        try:
            current_files = {f for f in monitor_path.rglob('*') if f.is_file()}
            current_dirs = {d for d in monitor_path.rglob('*') if d.is_dir()}
            
            # Check for new files
            new_files = current_files - self.initial_files
            new_dirs = current_dirs - self.initial_dirs
            
            if new_files:
                validation_results['new_files'] = [str(f) for f in new_files]
                validation_results['issues'].append(f"Test created {len(new_files)} files")
            
            if new_dirs:
                validation_results['new_directories'] = [str(d) for d in new_dirs]
                validation_results['issues'].append(f"Test created {len(new_dirs)} directories")
            
            # Determine if isolation was successful
            validation_results['isolation_success'] = len(validation_results['issues']) == 0
            
        except (OSError, PermissionError):
            validation_results['issues'].append("Could not validate filesystem state")
            validation_results['isolation_success'] = False
        
        return validation_results


@pytest.fixture(scope="function")
def filesystem_validator():
    """Provide filesystem validation for test isolation verification."""
    validator = FileSystemValidator()
    validator.capture_initial_state()
    
    yield validator
    
    # Automatically validate at end of test
    results = validator.validate_isolation()
    if not results['isolation_success']:
        print(f"\n⚠️  Filesystem isolation issues detected:")
        for issue in results['issues']:
            print(f"   {issue}")


# Debug and troubleshooting utilities
def debug_filesystem_state(manager: FileSystemManager):
    """Debug current filesystem isolation state."""
    stats = manager.get_filesystem_stats()
    
    print(f"\n🔍 FILESYSTEM STATE DEBUG:")
    print(f"   Temp directories: {stats['temp_directories']}")
    print(f"   Temp files: {stats['temp_files']}")
    print(f"   Backed up files: {stats['backed_up_files']}")
    print(f"   Backed up configs: {stats['backed_up_configs']}")
    print(f"   Working dir changed: {stats['working_directory_changed']}")
    print(f"   Env backups: {stats['env_backups']}")


# Export commonly used fixtures and utilities
__all__ = [
    'FileSystemManager', 'FileSystemValidator',
    'isolated_filesystem', 'temp_config_dir', 'temp_log_dir', 'temp_work_dir', 'project_structure',
    'isolated_file_operations', 'isolated_config_environment',
    'filesystem_validator', 'debug_filesystem_state'
]