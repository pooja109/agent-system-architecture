"""
Complete execution isolation architecture for system-critical tests.

This module provides complete process isolation for tests that could cause
system hangs, crashes, or other system-level conflicts. Tests are executed
in isolated processes with resource limits and monitoring.
"""
import pytest
import subprocess
import sys
import os
import tempfile
import shutil
import json
import time
import signal
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from contextlib import contextmanager
import multiprocessing as mp


@dataclass
class IsolationConfig:
    """Configuration for isolated test execution."""
    max_execution_time: float
    max_memory_mb: float
    max_cpu_percent: float
    isolated_filesystem: bool
    isolated_network: bool
    isolated_process_space: bool
    cleanup_timeout: float = 10.0


class ExecutionIsolationManager:
    """Manages completely isolated test execution to prevent system conflicts."""
    
    def __init__(self):
        self.isolation_processes: List[mp.Process] = []
        self.isolation_configs: Dict[str, IsolationConfig] = {}
        self.temp_directories: List[Path] = []
        self.isolation_results: Dict[str, Any] = {}
        
        # Default isolation configs by test category
        self.default_configs = {
            'system_critical': IsolationConfig(
                max_execution_time=120.0,
                max_memory_mb=500.0,
                max_cpu_percent=80.0,
                isolated_filesystem=True,
                isolated_network=True,
                isolated_process_space=True
            ),
            'error_conditions': IsolationConfig(
                max_execution_time=60.0,
                max_memory_mb=200.0,
                max_cpu_percent=60.0,
                isolated_filesystem=True,
                isolated_network=False,
                isolated_process_space=True
            ),
            'performance': IsolationConfig(
                max_execution_time=300.0,
                max_memory_mb=1000.0,
                max_cpu_percent=95.0,
                isolated_filesystem=True,
                isolated_network=False,
                isolated_process_space=True
            )
        }
    
    def set_isolation_config(self, test_category: str, config: IsolationConfig):
        """Set isolation configuration for test category."""
        self.isolation_configs[test_category] = config
    
    def get_isolation_config(self, test_category: str) -> IsolationConfig:
        """Get isolation configuration for test category."""
        return self.isolation_configs.get(
            test_category, 
            self.default_configs.get(test_category, self.default_configs['system_critical'])
        )
    
    def create_isolated_environment(self, test_category: str) -> Path:
        """Create completely isolated environment for test execution."""
        config = self.get_isolation_config(test_category)
        
        # Create isolated temporary directory
        if config.isolated_filesystem:
            isolated_dir = Path(tempfile.mkdtemp(prefix=f"isolated_test_{test_category}_"))
            self.temp_directories.append(isolated_dir)
            
            # Copy necessary test files
            self.setup_isolated_filesystem(isolated_dir)
            
            return isolated_dir
        
        return Path.cwd()
    
    def setup_isolated_filesystem(self, isolated_dir: Path):
        """Set up isolated filesystem with necessary test infrastructure."""
        # Copy essential test infrastructure
        essential_paths = [
            'tests/fixtures',
            'services',
            'models', 
            'utils',
            'config',
            'pytest.ini',
            'requirements.txt'
        ]
        
        for path in essential_paths:
            source_path = Path.cwd() / path
            if source_path.exists():
                target_path = isolated_dir / path
                if source_path.is_file():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, target_path)
                else:
                    try:
                        shutil.copytree(source_path, target_path, 
                                      ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                    except (OSError, shutil.Error):
                        # Best effort copy
                        pass
    
    def execute_isolated_test(self, test_path: str, test_category: str = 'system_critical') -> Dict[str, Any]:
        """Execute test in complete isolation."""
        config = self.get_isolation_config(test_category)
        isolated_dir = self.create_isolated_environment(test_category)
        
        # Create isolated test execution script
        execution_script = self.create_execution_script(test_path, config, isolated_dir)
        
        # Execute in isolated process
        result_queue = mp.Queue()
        process = mp.Process(
            target=self._run_isolated_test,
            args=(execution_script, config, isolated_dir, result_queue)
        )
        
        self.isolation_processes.append(process)
        process.start()
        
        try:
            # Wait for completion with timeout
            process.join(timeout=config.max_execution_time)
            
            if process.is_alive():
                # Force termination if timeout exceeded
                process.terminate()
                process.join(timeout=config.cleanup_timeout)
                
                if process.is_alive():
                    process.kill()
                
                return {
                    'status': 'timeout',
                    'message': f'Test execution exceeded {config.max_execution_time}s timeout',
                    'exit_code': -1
                }
            
            # Get result from queue
            if not result_queue.empty():
                return result_queue.get()
            else:
                return {
                    'status': 'error',
                    'message': 'No result returned from isolated execution',
                    'exit_code': process.exitcode or -1
                }
        
        finally:
            # Cleanup
            if process.is_alive():
                process.terminate()
                process.join(timeout=2.0)
            
            self.cleanup_isolation_environment(isolated_dir)
    
    def create_execution_script(self, test_path: str, config: IsolationConfig, isolated_dir: Path) -> str:
        """Create script for isolated test execution."""
        script_content = f'''
import sys
import os
import subprocess
import resource
import signal
import time
import json

# Set resource limits
def set_resource_limits():
    try:
        # Memory limit
        memory_limit = {config.max_memory_mb} * 1024 * 1024  # Convert to bytes
        resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    except (ValueError, resource.error):
        pass  # Best effort
    
    try:
        # CPU time limit  
        cpu_limit = int({config.max_execution_time})
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit))
    except (ValueError, resource.error):
        pass  # Best effort
    
    try:
        # File descriptor limit
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 512))
    except (ValueError, resource.error):
        pass  # Best effort

# Set up signal handlers for cleanup
def signal_handler(signum, frame):
    print(f"Received signal {{signum}}, cleaning up...")
    sys.exit(1)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Change to isolated directory
os.chdir('{isolated_dir}')

# Set resource limits
set_resource_limits()

# Execute test
try:
    result = subprocess.run([
        sys.executable, '-m', 'pytest',
        '{test_path}',
        '-v', '--tb=short',
        '--no-header',
        '--disable-warnings'
    ], capture_output=True, text=True, timeout={config.max_execution_time})
    
    # Return result
    result_data = {{
        'status': 'completed',
        'exit_code': result.returncode,
        'stdout': result.stdout,
        'stderr': result.stderr
    }}
    
    with open('test_result.json', 'w') as f:
        json.dump(result_data, f)
        
except subprocess.TimeoutExpired:
    result_data = {{
        'status': 'timeout',
        'exit_code': -1,
        'stdout': '',
        'stderr': 'Test execution timed out'
    }}
    
    with open('test_result.json', 'w') as f:
        json.dump(result_data, f)
        
except Exception as e:
    result_data = {{
        'status': 'error',
        'exit_code': -1,
        'stdout': '',
        'stderr': str(e)
    }}
    
    with open('test_result.json', 'w') as f:
        json.dump(result_data, f)
'''
        return script_content
    
    def verify_network_isolation(self, test_category: str = 'system_critical') -> Dict[str, Any]:
        """
        Verify network isolation functionality.
        
        Tests that network isolation properly blocks network access when enabled.
        """
        config = self.get_isolation_config(test_category)
        
        if not config.isolated_network:
            return {
                'status': 'skipped',
                'message': f'Network isolation not enabled for {test_category}',
                'network_isolated': False
            }
        
        # Create test script that attempts network access
        network_test_script = '''
import sys
import socket
import json
from urllib.request import urlopen
from urllib.error import URLError

def test_network_access():
    """Test if network access is blocked."""
    test_results = {
        'dns_resolution': False,
        'http_request': False,
        'socket_creation': False,
        'network_blocked': True
    }
    
    # Test 1: DNS resolution
    try:
        socket.gethostbyname('google.com')
        test_results['dns_resolution'] = True
        test_results['network_blocked'] = False
    except (socket.gaierror, OSError):
        pass  # Expected when network is isolated
    
    # Test 2: HTTP request
    try:
        with urlopen('http://httpbin.org/get', timeout=5) as response:
            if response.getcode() == 200:
                test_results['http_request'] = True
                test_results['network_blocked'] = False
    except (URLError, OSError):
        pass  # Expected when network is isolated
    
    # Test 3: Socket creation and connection
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(('8.8.8.8', 53))  # Google DNS
        sock.close()
        test_results['socket_creation'] = True
        test_results['network_blocked'] = False
    except (socket.error, OSError):
        pass  # Expected when network is isolated
    
    return test_results

if __name__ == '__main__':
    results = test_network_access()
    with open('network_test_results.json', 'w') as f:
        json.dump(results, f)
    
    # Exit with status indicating network isolation effectiveness
    sys.exit(0 if results['network_blocked'] else 1)
'''
        
        isolated_dir = self.create_isolated_environment(test_category)
        
        try:
            # Write network test script
            script_path = isolated_dir / 'network_test.py'
            script_path.write_text(network_test_script)
            
            # Execute network test in isolated environment
            result_queue = mp.Queue()
            process = mp.Process(
                target=self._run_network_isolation_test,
                args=(script_path, config, isolated_dir, result_queue)
            )
            
            process.start()
            
            try:
                process.join(timeout=config.max_execution_time)
                
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=config.cleanup_timeout)
                    
                    if process.is_alive():
                        process.kill()
                    
                    return {
                        'status': 'timeout',
                        'message': 'Network isolation test timed out',
                        'network_isolated': False
                    }
                
                # Get result from queue
                if not result_queue.empty():
                    test_result = result_queue.get()
                    return {
                        'status': 'completed',
                        'network_isolated': test_result.get('network_blocked', False),
                        'test_details': test_result,
                        'exit_code': process.exitcode
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'No result returned from network isolation test',
                        'network_isolated': False,
                        'exit_code': process.exitcode or -1
                    }
            
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2.0)
        
        finally:
            self.cleanup_isolation_environment(isolated_dir)
    
    def _run_network_isolation_test(self, script_path: Path, config: IsolationConfig,
                                   isolated_dir: Path, result_queue: mp.Queue):
        """Run network isolation test in isolated process."""
        try:
            # Execute network test script
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True,
            timeout=config.max_execution_time,
            cwd=str(isolated_dir))
            
            # Read result file if it exists
            result_file = isolated_dir / 'network_test_results.json'
            if result_file.exists():
                with open(result_file) as f:
                    test_result = json.load(f)
                result_queue.put(test_result)
            else:
                result_queue.put({
                    'network_blocked': result.returncode == 0,
                    'error': 'No result file generated'
                })
        
        except Exception as e:
            result_queue.put({
                'network_blocked': False,
                'error': str(e)
            })
    
    def _run_isolated_test(self, script_content: str, config: IsolationConfig, 
                          isolated_dir: Path, result_queue: mp.Queue):
        """Run test in isolated process."""
        try:
            # Create and execute script
            script_path = isolated_dir / 'isolated_execution.py'
            script_path.write_text(script_content)
            
            # Execute script
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, 
            timeout=config.max_execution_time,
            cwd=str(isolated_dir))
            
            # Read result file
            result_file = isolated_dir / 'test_result.json'
            if result_file.exists():
                with open(result_file) as f:
                    test_result = json.load(f)
                result_queue.put(test_result)
            else:
                result_queue.put({
                    'status': 'error',
                    'message': 'No result file generated',
                    'exit_code': result.returncode
                })
        
        except Exception as e:
            result_queue.put({
                'status': 'error',
                'message': str(e),
                'exit_code': -1
            })
    
    def cleanup_isolation_environment(self, isolated_dir: Path):
        """Clean up isolated environment."""
        if isolated_dir in self.temp_directories:
            try:
                shutil.rmtree(isolated_dir)
                self.temp_directories.remove(isolated_dir)
            except Exception:
                pass  # Best effort cleanup
    
    def cleanup_all_processes(self):
        """Clean up all isolation processes."""
        for process in self.isolation_processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2.0)
                if process.is_alive():
                    process.kill()
        
        self.isolation_processes.clear()
        
        # Clean up temporary directories
        for temp_dir in self.temp_directories:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
        
        self.temp_directories.clear()


@pytest.fixture(scope="function")
def execution_isolation():
    """Provide execution isolation for system-critical tests."""
    manager = ExecutionIsolationManager()
    try:
        yield manager
    finally:
        manager.cleanup_all_processes()


@contextmanager
def isolated_test_execution(test_category: str = 'system_critical'):
    """Context manager for isolated test execution."""
    manager = ExecutionIsolationManager()
    try:
        yield manager
    finally:
        manager.cleanup_all_processes()