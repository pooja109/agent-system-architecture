"""
Test Execution Engine for Test Runner CLI
=========================================

Handles the actual execution of pytest processes with progress monitoring.
"""

import subprocess
import time
import threading
import queue
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    # When imported as module
    from .config.runner_config import RunnerConfig, ExecutionMode
except ImportError:
    # When run directly
    from config.runner_config import RunnerConfig, ExecutionMode

# Import thread manager if available
# Phase 4 monitoring system removed - ThreadLifecycleManager no longer available
THREAD_MANAGER_AVAILABLE = False


class TestStatus(Enum):
    """Status of individual test execution."""
    PENDING = "pending"
    RUNNING = "running" 
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:
    """Results from test execution."""
    execution_mode: ExecutionMode
    command_executed: List[str]
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    error_tests: int = 0
    total_execution_time: float = 0.0
    individual_test_times: Dict[str, float] = field(default_factory=dict)
    failure_details: List[str] = field(default_factory=list)
    output_lines: List[str] = field(default_factory=list)
    return_code: int = 0
    
    @property
    def has_failures(self) -> bool:
        """Check if there were any test failures."""
        return self.failed_tests > 0
    
    @property
    def has_errors(self) -> bool:
        """Check if there were any test errors.""" 
        return self.error_tests > 0
    
    @property
    def success_rate(self) -> float:
        """Calculate test success rate as percentage."""
        if self.total_tests == 0:
            return 100.0
        return (self.passed_tests / self.total_tests) * 100.0


class TestExecutor:
    """Handles test execution with progress monitoring."""
    
    def __init__(self, config: RunnerConfig):
        self.config = config
        self.current_process: Optional[subprocess.Popen] = None
        self.output_queue = queue.Queue()
        self.stop_execution = threading.Event()
        
        # Initialize thread manager if available
        if THREAD_MANAGER_AVAILABLE:
            self.thread_manager = ThreadLifecycleManager()
        else:
            self.thread_manager = None
    
    def execute_tests(self, **kwargs) -> TestResult:
        """Execute tests based on provided configuration."""
        mode = kwargs['mode']
        
        # Validate environment
        env_issues = self.config.validate_environment()
        if env_issues:
            raise RuntimeError(f"Environment validation failed: {'; '.join(env_issues)}")
        
        # Build pytest command
        kwargs_copy = kwargs.copy()
        kwargs_copy.pop('mode', None)  # Remove mode from kwargs since it's passed separately
        cmd = self.config.get_pytest_command(mode, **kwargs_copy)
        
        # Handle dry run
        if kwargs.get('dry_run'):
            return self._handle_dry_run(cmd, mode)
        
        # Execute the actual test run
        return self._execute_pytest_process(cmd, mode, **kwargs_copy)
    
    def _handle_dry_run(self, cmd: List[str], mode: ExecutionMode) -> TestResult:
        """Handle dry run mode - show what would be executed."""
        print("DRY RUN - Command that would be executed:")
        print(" ".join(cmd))
        print()
        
        # Run collection only to show selected tests
        collection_cmd = cmd + ['--collect-only', '-q']
        try:
            result = subprocess.run(
                collection_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # Parse test collection output format: "filename: count"
                test_lines = [line for line in result.stdout.split('\n') 
                             if line.strip() and ':' in line and line.strip().endswith(('py:', ) + tuple(str(i) for i in range(10)))]
                total_tests = 0
                for line in test_lines:
                    if ':' in line:
                        try:
                            count_part = line.split(':')[-1].strip()
                            if count_part.isdigit():
                                total_tests += int(count_part)
                        except (ValueError, IndexError):
                            continue
                
                print(f"Would execute {total_tests} tests:")
                for line in test_lines[:10]:  # Show first 10
                    print(f"  {line.strip()}")
                if len(test_lines) > 10:
                    print(f"  ... and {len(test_lines) - 10} more files")
            else:
                print(f"Test collection failed: {result.stderr}")
        
        except Exception as e:
            print(f"Failed to collect tests for dry run: {e}")
        
        # Return result with test counts for dry run
        dry_run_result = TestResult(
            execution_mode=mode,
            command_executed=cmd,
            return_code=0
        )
        
        # Set test counts from collection if successful
        if 'total_tests' in locals():
            dry_run_result.total_tests = total_tests
            # For dry run, assume all tests would pass
            dry_run_result.passed_tests = total_tests
        
        return dry_run_result
    
    def _execute_pytest_process(self, cmd: List[str], mode: ExecutionMode, **kwargs) -> TestResult:
        """Execute the pytest process with monitoring."""
        result = TestResult(
            execution_mode=mode,
            command_executed=cmd
        )
        
        start_time = time.time()
        output_thread = None
        memory_thread = None
        
        try:
            # Set up environment for pytest execution
            import os
            env = os.environ.copy()
            env['PYTEST_STRICT_MARKERS'] = 'false'  # Disable strict marker validation
            
            # Set default timeout to prevent indefinite hangs
            timeout = kwargs.get('timeout', 300)  # Default 5 minutes
            
            print(f"Starting pytest with {timeout}s timeout...")
            
            # Start pytest process with resource limits
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
                preexec_fn=self._set_process_limits if hasattr(os, 'setrlimit') else None
            )
            
            # Start output monitoring thread
            output_thread = threading.Thread(
                target=self._monitor_output,
                args=(self.current_process.stdout, result),
                daemon=False,  # Don't use daemon threads for proper cleanup
                name="OutputMonitor"
            )
            output_thread.start()
            
            # Start memory monitoring thread
            memory_thread = threading.Thread(
                target=self._monitor_memory_usage,
                daemon=False,
                name="MemoryMonitor"
            )
            memory_thread.start()
            
            # Register threads with manager if available
            if self.thread_manager:
                self.thread_manager.register_thread(output_thread)
                self.thread_manager.register_thread(memory_thread)
            
            # Wait for process completion with timeout
            try:
                return_code = self.current_process.wait(timeout=timeout)
                result.return_code = return_code
                print(f"\nProcess completed with return code: {return_code}")
                
                # Signal monitoring threads to stop now that the process has completed
                self.stop_execution.set()
                
            except subprocess.TimeoutExpired:
                print(f"\n⚠️ Test execution timed out after {timeout} seconds - terminating...")
                self._force_cleanup()
                result.return_code = -1
                result.failure_details.append(f"Execution timed out after {timeout} seconds")
            
            # Wait for monitoring threads to finish with timeout
            if output_thread and output_thread.is_alive():
                print("Waiting for output monitoring to complete...")
                output_thread.join(timeout=10)
                if output_thread.is_alive():
                    print("⚠️ Output monitoring thread did not terminate cleanly")
            
            if memory_thread and memory_thread.is_alive():
                print("Waiting for memory monitoring to complete...")
                memory_thread.join(timeout=3)
                if memory_thread.is_alive():
                    print("⚠️ Memory monitoring thread did not terminate cleanly")
            
        except KeyboardInterrupt:
            print("\n🛑 Test execution interrupted by user")
            self.stop_execution.set()  # Signal threads to stop
            self._force_cleanup()
            result.return_code = -3
        except Exception as e:
            print(f"\n❌ Error during test execution: {e}")
            self.stop_execution.set()  # Signal threads to stop
            self._force_cleanup()
            result.return_code = -2
        
        finally:
            # Ensure the stop signal is set regardless of how execution ended
            self.stop_execution.set()
            result.total_execution_time = time.time() - start_time
            
            # Ensure proper cleanup
            if self.current_process:
                try:
                    if self.current_process.poll() is None:
                        print("Force terminating remaining process...")
                        self.current_process.terminate()
                        time.sleep(2)
                        if self.current_process.poll() is None:
                            self.current_process.kill()
                            time.sleep(1)
                except:
                    pass
            
            self.current_process = None
            
            # Join monitoring threads if still alive
            if output_thread and output_thread.is_alive():
                try:
                    output_thread.join(timeout=3)
                except:
                    pass
            
            if memory_thread and memory_thread.is_alive():
                try:
                    memory_thread.join(timeout=1)
                except:
                    pass
        
        return result
    
    def _monitor_output(self, stdout, result: TestResult):
        """Monitor pytest output and update result in real-time."""
        current_test = None
        test_start_time = None
        
        try:
            for line in iter(stdout.readline, ''):
                if not line:
                    break
                
                line = line.rstrip()
                result.output_lines.append(line)
                
                # Parse different types of pytest output
                self._parse_output_line(line, result)
                
                # Print line for real-time feedback (if not quiet mode)
                print(line, flush=True)
                
                # Check for stop signal
                if self.stop_execution.is_set():
                    break
        
        except Exception as e:
            print(f"Error monitoring output: {e}")
    
    def _parse_output_line(self, line: str, result: TestResult):
        """Parse a single line of pytest output to update result."""
        line = line.strip()
        
        # Count test results from progress indicators (quiet mode)
        # Format: E...F..                                                                  [100%]
        import re
        progress_match = re.search(r'^([\.EFsxX]+)\s+\[100%\]$', line)
        if progress_match:
            progress_chars = progress_match.group(1)
            result.passed_tests = progress_chars.count('.')
            result.failed_tests = progress_chars.count('F')
            result.error_tests = progress_chars.count('E')
            result.skipped_tests = progress_chars.count('s') + progress_chars.count('x')
            result.total_tests = len(progress_chars)
        
        # Count test results from summary line (verbose mode)
        elif "passed" in line and ("failed" in line or "skipped" in line or "error" in line):
            # Parse summary line like "25 passed, 3 failed, 2 skipped"
            passed_match = re.search(r'(\d+) passed', line)
            if passed_match:
                result.passed_tests = int(passed_match.group(1))
            
            failed_match = re.search(r'(\d+) failed', line)
            if failed_match:
                result.failed_tests = int(failed_match.group(1))
            
            skipped_match = re.search(r'(\d+) skipped', line)
            if skipped_match:
                result.skipped_tests = int(skipped_match.group(1))
            
            error_match = re.search(r'(\d+) error', line)
            if error_match:
                result.error_tests = int(error_match.group(1))
            
            result.total_tests = (result.passed_tests + result.failed_tests + 
                                result.skipped_tests + result.error_tests)
        
        # Alternative parsing for simple passed count
        elif line.endswith(" passed") and "failed" not in line:
            match = re.search(r'(\d+) passed', line)
            if match:
                result.passed_tests = int(match.group(1))
                result.total_tests = result.passed_tests
        
        # Capture failure details
        if line.startswith("FAILED "):
            result.failure_details.append(line)
        
        # Parse individual test timings from durations output
        if " PASSED " in line or " FAILED " in line:
            # Extract test timing if present
            timing_match = re.search(r'(\d+\.\d+)s', line)
            test_match = re.search(r'(tests/[^:]+::[^\s]+)', line)
            
            if timing_match and test_match:
                duration = float(timing_match.group(1))
                test_name = test_match.group(1)
                result.individual_test_times[test_name] = duration
    
    def interrupt_execution(self):
        """Interrupt the current test execution."""
        self.stop_execution.set()
        self._force_cleanup()
    
    def _force_cleanup(self):
        """Force cleanup of subprocess and threads."""
        if self.current_process:
            try:
                print("Terminating test process...")
                self.current_process.terminate()
                
                # Wait for graceful termination
                try:
                    self.current_process.wait(timeout=5)
                    print("Process terminated gracefully")
                except subprocess.TimeoutExpired:
                    print("Process did not terminate gracefully, killing...")
                    self.current_process.kill()
                    try:
                        self.current_process.wait(timeout=3)
                        print("Process killed successfully")
                    except subprocess.TimeoutExpired:
                        print("⚠️ Process could not be killed - may be orphaned")
            except Exception as e:
                print(f"Error during force cleanup: {e}")
    
    def _set_process_limits(self):
        """Set resource limits for the subprocess (Unix only)."""
        try:
            import resource
            
            # Set memory limit (4GB virtual memory)
            resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, resource.RLIM_INFINITY))
            
            # Set CPU time limit (10 minutes)
            resource.setrlimit(resource.RLIMIT_CPU, (600, resource.RLIM_INFINITY))
            
            # Set process count limit
            resource.setrlimit(resource.RLIMIT_NPROC, (100, resource.RLIM_INFINITY))
            
        except (ImportError, OSError):
            # Resource limits not available on this platform
            pass
    
    def _monitor_memory_usage(self):
        """Monitor memory usage during test execution."""
        try:
            import psutil
            process = psutil.Process()
            
            while (self.current_process and 
                   self.current_process.poll() is None and 
                   not self.stop_execution.is_set()):
                
                memory_mb = process.memory_info().rss / 1024 / 1024
                
                if memory_mb > 2048:  # 2GB threshold
                    print(f"⚠️ High memory usage: {memory_mb:.1f}MB")
                    
                if memory_mb > 4096:  # 4GB hard limit
                    print("🛑 Memory limit exceeded - terminating test execution")
                    self._force_cleanup()
                    break
                
                # Use stop_execution event for interruptible sleep
                if self.stop_execution.wait(timeout=10):
                    break  # Stop event was set
                
        except ImportError:
            # psutil not available
            pass
        except Exception as e:
            print(f"Memory monitoring error: {e}")