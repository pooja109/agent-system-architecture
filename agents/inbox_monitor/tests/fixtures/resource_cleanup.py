"""
Basic resource cleanup and monitoring for recovered tests.

This module provides automatic cleanup of system resources to prevent
memory leaks and resource exhaustion in recovered tests.
"""
import pytest
import gc
import os
import threading
import tempfile
import weakref
from typing import List, Dict, Any, Set, Optional
from contextlib import contextmanager
from pathlib import Path


class ResourceTracker:
    """Track and manage system resources during test execution."""
    
    def __init__(self):
        self.temp_files: Set[str] = set()
        self.temp_dirs: Set[str] = set()
        self.open_files: List[weakref.ref] = []
        self.active_threads: Set[threading.Thread] = set()
        self.cleanup_callbacks: List[callable] = []
        self.initial_memory = None
        self.memory_threshold_mb = 100  # Alert if memory grows by >100MB
    
    def track_temp_file(self, filepath: str):
        """Track temporary file for cleanup."""
        self.temp_files.add(filepath)
    
    def track_temp_dir(self, dirpath: str):
        """Track temporary directory for cleanup."""
        self.temp_dirs.add(dirpath)
    
    def track_file_handle(self, file_obj):
        """Track file handle for cleanup."""
        self.open_files.append(weakref.ref(file_obj))
    
    def track_thread(self, thread: threading.Thread):
        """Track thread for cleanup."""
        self.active_threads.add(thread)
    
    def register_cleanup_callback(self, callback: callable):
        """Register cleanup callback."""
        self.cleanup_callbacks.append(callback)
    
    def cleanup_all(self):
        """Clean up all tracked resources."""
        # Close file handles
        for file_ref in self.open_files:
            file_obj = file_ref()
            if file_obj and hasattr(file_obj, 'close'):
                try:
                    file_obj.close()
                except:
                    pass  # Ignore close errors
        
        # Clean up temporary files
        for filepath in self.temp_files.copy():
            try:
                if os.path.exists(filepath):
                    os.unlink(filepath)
                self.temp_files.remove(filepath)
            except:
                pass  # Ignore cleanup errors
        
        # Clean up temporary directories
        for dirpath in self.temp_dirs.copy():
            try:
                if os.path.exists(dirpath):
                    os.rmdir(dirpath)
                self.temp_dirs.remove(dirpath)
            except:
                pass  # Ignore cleanup errors
        
        # Join threads (with timeout)
        for thread in self.active_threads.copy():
            try:
                if thread.is_alive():
                    thread.join(timeout=1.0)  # Wait max 1 second
                self.active_threads.remove(thread)
            except:
                pass  # Ignore thread cleanup errors
        
        # Run custom cleanup callbacks
        for callback in self.cleanup_callbacks:
            try:
                callback()
            except:
                pass  # Ignore callback errors
        
        # Clear collections
        self.open_files.clear()
        self.cleanup_callbacks.clear()
        
        # Force garbage collection
        gc.collect()
    
    def get_resource_stats(self) -> Dict[str, int]:
        """Get current resource usage statistics."""
        return {
            'temp_files': len(self.temp_files),
            'temp_dirs': len(self.temp_dirs),
            'open_files': len([ref for ref in self.open_files if ref() is not None]),
            'active_threads': len(self.active_threads),
            'cleanup_callbacks': len(self.cleanup_callbacks)
        }


class ManagedTempFile:
    """Managed temporary file that automatically cleans up."""
    
    def __init__(self, tracker: ResourceTracker, **kwargs):
        self.tracker = tracker
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, **kwargs)
        self.filepath = self.temp_file.name
        self.tracker.track_temp_file(self.filepath)
        self.tracker.track_file_handle(self.temp_file)
    
    def __enter__(self):
        return self.temp_file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if hasattr(self.temp_file, 'close'):
            self.temp_file.close()
    
    @property
    def name(self):
        return self.filepath


class ManagedTempDir:
    """Managed temporary directory that automatically cleans up."""
    
    def __init__(self, tracker: ResourceTracker, **kwargs):
        self.tracker = tracker
        self.temp_dir = tempfile.mkdtemp(**kwargs)
        self.tracker.track_temp_dir(self.temp_dir)
    
    def __enter__(self):
        return self.temp_dir
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Directory cleanup handled by tracker
        pass
    
    @property
    def path(self):
        return self.temp_dir


@contextmanager
def managed_thread(tracker: ResourceTracker, target, args=(), kwargs=None):
    """Context manager for managed thread execution."""
    if kwargs is None:
        kwargs = {}
    
    thread = threading.Thread(target=target, args=args, kwargs=kwargs)
    tracker.track_thread(thread)
    
    try:
        thread.start()
        yield thread
    finally:
        if thread.is_alive():
            thread.join(timeout=2.0)  # Wait up to 2 seconds


@pytest.fixture(scope="function")
def resource_tracker():
    """Provide resource tracking for test."""
    tracker = ResourceTracker()
    try:
        yield tracker
    finally:
        tracker.cleanup_all()


@pytest.fixture(scope="function")
def managed_temp_file(resource_tracker):
    """Provide managed temporary file."""
    def _create_temp_file(**kwargs):
        return ManagedTempFile(resource_tracker, **kwargs)
    return _create_temp_file


@pytest.fixture(scope="function")
def managed_temp_dir(resource_tracker):
    """Provide managed temporary directory."""
    def _create_temp_dir(**kwargs):
        return ManagedTempDir(resource_tracker, **kwargs)
    return _create_temp_dir


class MemoryLeakDetector:
    """Detect potential memory leaks during test execution."""
    
    def __init__(self, threshold_mb: float = 50.0):
        self.threshold_mb = threshold_mb
        self.initial_memory: Optional[float] = None
        self.peak_memory: Optional[float] = None
    
    def start_monitoring(self):
        """Start memory monitoring."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            self.initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            self.peak_memory = self.initial_memory
        except ImportError:
            self.initial_memory = 0.0
            self.peak_memory = 0.0
    
    def check_memory(self) -> bool:
        """Check current memory usage and update peak."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            if current_memory > self.peak_memory:
                self.peak_memory = current_memory
            
            # Check for memory leak
            if self.initial_memory is not None:
                memory_growth = current_memory - self.initial_memory
                return memory_growth > self.threshold_mb
        except ImportError:
            return False
        
        return False
    
    def get_memory_stats(self) -> Dict[str, float]:
        """Get memory usage statistics."""
        return {
            'initial_memory': self.initial_memory or 0.0,
            'peak_memory': self.peak_memory or 0.0,
            'memory_growth': (self.peak_memory or 0.0) - (self.initial_memory or 0.0)
        }


@pytest.fixture(scope="function")
def memory_leak_detector():
    """Provide memory leak detection for test."""
    detector = MemoryLeakDetector()
    detector.start_monitoring()
    
    yield detector
    
    # Check for memory leaks at end of test
    if detector.check_memory():
        stats = detector.get_memory_stats()
        print(f"\n⚠️  Potential memory leak detected:")
        print(f"   Initial memory: {stats['initial_memory']:.1f}MB")
        print(f"   Peak memory: {stats['peak_memory']:.1f}MB") 
        print(f"   Memory growth: {stats['memory_growth']:.1f}MB")


@pytest.fixture(scope="function", autouse=True)
def auto_resource_cleanup(resource_tracker, memory_leak_detector):
    """Automatically provide resource cleanup for all tests."""
    # Pre-test setup
    yield
    
    # Post-test cleanup and validation
    stats = resource_tracker.get_resource_stats()
    memory_stats = memory_leak_detector.get_memory_stats()
    
    # Report resource usage if significant
    if any(stats.values()) or memory_stats['memory_growth'] > 10.0:
        print(f"\n📊 Resource Usage Summary:")
        if stats['temp_files'] > 0:
            print(f"   Temp files cleaned: {stats['temp_files']}")
        if stats['temp_dirs'] > 0:
            print(f"   Temp dirs cleaned: {stats['temp_dirs']}")
        if stats['active_threads'] > 0:
            print(f"   Threads cleaned: {stats['active_threads']}")
        if memory_stats['memory_growth'] > 0:
            print(f"   Memory growth: {memory_stats['memory_growth']:.1f}MB")
    
    # Automatic cleanup is handled by resource_tracker fixture teardown