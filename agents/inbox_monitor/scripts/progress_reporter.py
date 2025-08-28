"""
Progress Reporter for Test Runner CLI
====================================

Provides real-time progress reporting and result summarization.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult


@dataclass
class ProgressStatus:
    """Current progress status during test execution."""
    current_test: Optional[str] = None
    tests_completed: int = 0
    tests_total: Optional[int] = None
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    start_time: float = 0.0
    estimated_total_time: Optional[float] = None


class ProgressReporter:
    """Handles progress reporting and result summarization."""
    
    def __init__(self):
        self.progress_status = ProgressStatus()
        self.reporting_active = False
        self.reporting_thread: Optional[threading.Thread] = None
        self.stop_reporting = threading.Event()
    
    def start_reporting(self, mode: ExecutionMode, estimated_time: Optional[str] = None):
        """Start real-time progress reporting."""
        self.progress_status = ProgressStatus()
        self.progress_status.start_time = time.time()
        self.reporting_active = True
        self.stop_reporting.clear()
        
        print(f"\n🚀 Starting {mode.value.replace('_', ' ').title()} Test Execution")
        if estimated_time:
            print(f"📊 Estimated time: {estimated_time}")
        print("-" * 60)
        
        # Start background progress reporting thread
        self.reporting_thread = threading.Thread(
            target=self._background_progress_update,
            daemon=True
        )
        self.reporting_thread.start()
    
    def stop_progress_reporting(self):
        """Stop progress reporting."""
        self.reporting_active = False
        self.stop_reporting.set()
        if self.reporting_thread:
            self.reporting_thread.join(timeout=1)
    
    def update_progress(self, **kwargs):
        """Update progress status with new information."""
        if kwargs.get('current_test'):
            self.progress_status.current_test = kwargs['current_test']
        
        if kwargs.get('tests_completed') is not None:
            self.progress_status.tests_completed = kwargs['tests_completed']
        
        if kwargs.get('tests_total') is not None:
            self.progress_status.tests_total = kwargs['tests_total']
        
        if kwargs.get('tests_passed') is not None:
            self.progress_status.tests_passed = kwargs['tests_passed']
        
        if kwargs.get('tests_failed') is not None:
            self.progress_status.tests_failed = kwargs['tests_failed']
        
        if kwargs.get('tests_skipped') is not None:
            self.progress_status.tests_skipped = kwargs['tests_skipped']
    
    def _background_progress_update(self):
        """Background thread for periodic progress updates."""
        last_update = 0
        
        while not self.stop_reporting.is_set() and self.reporting_active:
            current_time = time.time()
            
            # Update every 5 seconds
            if current_time - last_update >= 5:
                self._print_progress_update()
                last_update = current_time
            
            time.sleep(1)
    
    def _print_progress_update(self):
        """Print current progress update."""
        if not self.reporting_active:
            return
        
        elapsed = time.time() - self.progress_status.start_time
        elapsed_str = self._format_duration(elapsed)
        
        status_parts = []
        
        # Add completion percentage if total is known
        if self.progress_status.tests_total:
            percentage = (self.progress_status.tests_completed / self.progress_status.tests_total) * 100
            status_parts.append(f"{percentage:.1f}% complete")
        
        # Add test counts
        if self.progress_status.tests_completed > 0:
            status_parts.append(f"{self.progress_status.tests_completed} tests")
        
        if self.progress_status.tests_passed > 0:
            status_parts.append(f"{self.progress_status.tests_passed} passed")
        
        if self.progress_status.tests_failed > 0:
            status_parts.append(f"{self.progress_status.tests_failed} failed")
        
        # Add current test if available
        current_test_info = ""
        if self.progress_status.current_test:
            current_test_info = f" | Current: {self.progress_status.current_test}"
        
        if status_parts:
            status = " | ".join(status_parts)
            print(f"⏱️  {elapsed_str} elapsed | {status}{current_test_info}", flush=True)
    
    def print_summary(self, result: TestResult):
        """Print comprehensive test execution summary."""
        self.stop_progress_reporting()
        
        print("\n" + "=" * 70)
        print("🏁 TEST EXECUTION SUMMARY")
        print("=" * 70)
        
        # Execution details
        print(f"Mode: {result.execution_mode.value.replace('_', ' ').title()}")
        print(f"Duration: {self._format_duration(result.total_execution_time)}")
        print(f"Command: {' '.join(result.command_executed)}")
        
        # Test results
        print(f"\n📊 RESULTS:")
        print(f"  Total Tests:   {result.total_tests}")
        print(f"  ✅ Passed:      {result.passed_tests}")
        if result.failed_tests > 0:
            print(f"  ❌ Failed:      {result.failed_tests}")
        if result.skipped_tests > 0:
            print(f"  ⏭️  Skipped:     {result.skipped_tests}")
        if result.error_tests > 0:
            print(f"  💥 Errors:      {result.error_tests}")
        
        # Success rate
        if result.total_tests > 0:
            success_rate = result.success_rate
            status_emoji = "✅" if success_rate == 100.0 else "⚠️" if success_rate >= 80.0 else "❌"
            print(f"  {status_emoji} Success Rate: {success_rate:.1f}%")
        
        # Performance insights
        if result.individual_test_times:
            self._print_performance_insights(result)
        
        # Failure details
        if result.failure_details:
            print(f"\n❌ FAILURES:")
            for failure in result.failure_details[:10]:  # Show first 10
                print(f"  {failure}")
            if len(result.failure_details) > 10:
                print(f"  ... and {len(result.failure_details) - 10} more failures")
        
        # Overall status
        overall_status = "SUCCESS" if result.return_code == 0 else "FAILURE"
        status_emoji = "✅" if result.return_code == 0 else "❌"
        print(f"\n{status_emoji} OVERALL STATUS: {overall_status}")
        print("=" * 70)
    
    def _print_performance_insights(self, result: TestResult):
        """Print performance insights from test execution."""
        if not result.individual_test_times:
            return
        
        times = list(result.individual_test_times.values())
        if not times:
            return
        
        avg_time = sum(times) / len(times)
        slowest_tests = sorted(
            result.individual_test_times.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        print(f"\n⚡ PERFORMANCE INSIGHTS:")
        print(f"  Average Test Time: {avg_time:.2f}s")
        
        if slowest_tests:
            print(f"  Slowest Tests:")
            for test_name, duration in slowest_tests:
                print(f"    {duration:6.2f}s - {test_name}")
    
    def generate_detailed_report(self, result: TestResult) -> str:
        """Generate detailed test report for file output."""
        lines = []
        lines.append("=" * 80)
        lines.append("DETAILED TEST EXECUTION REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append("")
        
        # Execution metadata
        lines.append("EXECUTION DETAILS:")
        lines.append(f"  Mode: {result.execution_mode.value}")
        lines.append(f"  Duration: {self._format_duration(result.total_execution_time)}")
        lines.append(f"  Command: {' '.join(result.command_executed)}")
        lines.append(f"  Return Code: {result.return_code}")
        lines.append("")
        
        # Test results
        lines.append("TEST RESULTS:")
        lines.append(f"  Total: {result.total_tests}")
        lines.append(f"  Passed: {result.passed_tests}")
        lines.append(f"  Failed: {result.failed_tests}")
        lines.append(f"  Skipped: {result.skipped_tests}")
        lines.append(f"  Errors: {result.error_tests}")
        lines.append(f"  Success Rate: {result.success_rate:.1f}%")
        lines.append("")
        
        # Individual test timings
        if result.individual_test_times:
            lines.append("INDIVIDUAL TEST TIMINGS:")
            sorted_tests = sorted(
                result.individual_test_times.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for test_name, duration in sorted_tests:
                lines.append(f"  {duration:6.2f}s - {test_name}")
            lines.append("")
        
        # Failure details
        if result.failure_details:
            lines.append("FAILURE DETAILS:")
            for failure in result.failure_details:
                lines.append(f"  {failure}")
            lines.append("")
        
        # Full output
        lines.append("FULL OUTPUT:")
        lines.extend(result.output_lines)
        
        return "\n".join(lines)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f"{minutes}m {secs:.1f}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours}h {minutes}m {secs:.1f}s"