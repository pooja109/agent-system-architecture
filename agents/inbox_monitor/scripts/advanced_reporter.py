"""
Advanced Progress Reporter for Test Runner CLI
=============================================

Provides comprehensive reporting, analytics, and visualization capabilities.
"""

import json
import time
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3

try:
    from .test_execution import TestResult, TestStatus
except ImportError:
    from test_execution import TestResult, TestStatus
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

@dataclass
class TestAnalytics:
    """Advanced analytics data for test execution."""
    execution_history: List[TestResult] = field(default_factory=list)
    performance_trends: Dict[str, List[float]] = field(default_factory=dict)
    failure_patterns: Dict[str, int] = field(default_factory=dict)
    flaky_tests: List[str] = field(default_factory=list)
    slowest_tests: List[tuple] = field(default_factory=list)
    coverage_data: Optional[Dict] = None

@dataclass
class TestInsights:
    """Actionable insights from test analysis."""
    recommendations: List[str] = field(default_factory=list)
    performance_issues: List[str] = field(default_factory=list)
    reliability_concerns: List[str] = field(default_factory=list)
    optimization_opportunities: List[str] = field(default_factory=list)

class AdvancedProgressReporter:
    """Enhanced progress reporter with analytics and advanced features."""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path('test_data')
        self.data_dir.mkdir(exist_ok=True)
        self.db_path = self.data_dir / 'test_history.db'
        self.analytics = TestAnalytics()
        self._init_database()
        self._load_historical_data()
    
    def _init_database(self):
        """Initialize SQLite database for test history tracking."""
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS test_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                execution_mode TEXT,
                total_tests INTEGER,
                passed_tests INTEGER,
                failed_tests INTEGER,
                skipped_tests INTEGER,
                execution_time REAL,
                success_rate REAL
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                test_name TEXT,
                status TEXT,
                execution_time REAL,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES test_runs (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_historical_data(self):
        """Load historical test data for trend analysis."""
        conn = sqlite3.connect(self.db_path)
        
        # Load recent test runs for trend analysis
        cursor = conn.execute('''
            SELECT * FROM test_runs 
            ORDER BY timestamp DESC 
            LIMIT 50
        ''')
        
        for row in cursor:
            # Convert to TestResult format for compatibility
            result = TestResult(
                execution_mode=ExecutionMode(row[2]),
                command_executed=[],
                total_tests=row[3],
                passed_tests=row[4],
                failed_tests=row[5],
                skipped_tests=row[6],
                total_execution_time=row[7]
            )
            self.analytics.execution_history.append(result)
        
        conn.close()
    
    def start_reporting(self, mode: ExecutionMode, estimated_time: Optional[str] = None):
        """Start advanced progress reporting with enhanced features."""
        print(f"🚀 Starting {mode.name.replace('_', ' ').title()} Test Execution")
        
        if estimated_time:
            print(f"⏱️  Estimated time: {estimated_time}")
        
        # Show historical context if available
        if self.analytics.execution_history:
            recent_runs = self.analytics.execution_history[:5]
            avg_time = statistics.mean(r.total_execution_time for r in recent_runs if r.total_execution_time > 0)
            avg_success = statistics.mean(r.success_rate for r in recent_runs)
            
            print(f"📊 Recent performance: {avg_time:.1f}s avg time, {avg_success:.1f}% success rate")
        
        print("-" * 60)
    
    def update_progress(self, current: int, total: int, current_test: str = None):
        """Update progress with enhanced visualization."""
        percentage = (current / total) * 100 if total > 0 else 0
        
        # Create progress bar
        bar_length = 40
        filled_length = int(bar_length * percentage // 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        status_line = f"\r[{bar}] {percentage:6.1f}% ({current}/{total})"
        
        if current_test:
            # Truncate test name if too long
            display_test = current_test[-40:] if len(current_test) > 40 else current_test
            status_line += f" - {display_test}"
        
        print(status_line, end="", flush=True)
    
    def print_summary(self, result: TestResult):
        """Print enhanced summary with analytics and insights."""
        print("\n" + "=" * 60)
        print("📋 TEST EXECUTION SUMMARY")
        print("=" * 60)
        
        # Basic statistics
        print(f"Mode: {result.execution_mode.name.replace('_', ' ').title()}")
        print(f"Total Tests: {result.total_tests}")
        print(f"✅ Passed: {result.passed_tests}")
        print(f"❌ Failed: {result.failed_tests}")
        print(f"⏭️  Skipped: {result.skipped_tests}")
        print(f"⚠️  Errors: {result.error_tests}")
        print(f"⏱️  Execution Time: {result.total_execution_time:.2f}s")
        print(f"📈 Success Rate: {result.success_rate:.1f}%")
        
        # Performance analysis
        if result.individual_test_times:
            self._print_performance_analysis(result)
        
        # Failure analysis
        if result.failure_details:
            self._print_failure_analysis(result)
        
        # Historical comparison
        self._print_historical_comparison(result)
        
        # Insights and recommendations
        insights = self._generate_insights(result)
        if insights.recommendations:
            print("\n💡 RECOMMENDATIONS:")
            for rec in insights.recommendations:
                print(f"   • {rec}")
    
    def _print_performance_analysis(self, result: TestResult):
        """Print detailed performance analysis."""
        print("\n⚡ PERFORMANCE ANALYSIS:")
        
        times = list(result.individual_test_times.values())
        if times:
            print(f"   Average test time: {statistics.mean(times):.3f}s")
            print(f"   Median test time: {statistics.median(times):.3f}s")
            print(f"   Slowest test: {max(times):.3f}s")
            
            # Show slowest tests
            slowest = sorted(result.individual_test_times.items(), key=lambda x: x[1], reverse=True)[:5]
            print("\n   🐌 Slowest tests:")
            for test_name, duration in slowest:
                print(f"      {duration:6.3f}s - {test_name}")
    
    def _print_failure_analysis(self, result: TestResult):
        """Print failure analysis and patterns."""
        print(f"\n💥 FAILURE ANALYSIS ({len(result.failure_details)} failures):")
        
        # Group failures by pattern
        failure_patterns = {}
        for failure in result.failure_details:
            # Extract test module for pattern analysis
            if "::" in failure:
                module = failure.split("::")[0]
                failure_patterns[module] = failure_patterns.get(module, 0) + 1
        
        if failure_patterns:
            print("   Failures by module:")
            for module, count in sorted(failure_patterns.items(), key=lambda x: x[1], reverse=True):
                print(f"      {count:2d} failures - {module}")
    
    def _print_historical_comparison(self, result: TestResult):
        """Print comparison with historical data."""
        if not self.analytics.execution_history:
            return
        
        print("\n📊 HISTORICAL COMPARISON:")
        
        # Compare with recent runs of same mode
        same_mode_runs = [r for r in self.analytics.execution_history 
                         if r.execution_mode == result.execution_mode][:10]
        
        if same_mode_runs:
            avg_time = statistics.mean(r.total_execution_time for r in same_mode_runs if r.total_execution_time > 0)
            avg_success = statistics.mean(r.success_rate for r in same_mode_runs)
            
            time_change = result.total_execution_time - avg_time
            success_change = result.success_rate - avg_success
            
            time_indicator = "⬆️" if time_change > 5 else "⬇️" if time_change < -5 else "➡️"
            success_indicator = "⬆️" if success_change > 2 else "⬇️" if success_change < -2 else "➡️"
            
            print(f"   {time_indicator} Time vs avg: {time_change:+.1f}s ({result.total_execution_time:.1f}s vs {avg_time:.1f}s avg)")
            print(f"   {success_indicator} Success vs avg: {success_change:+.1f}% ({result.success_rate:.1f}% vs {avg_success:.1f}% avg)")
    
    def _generate_insights(self, result: TestResult) -> TestInsights:
        """Generate actionable insights from test results."""
        insights = TestInsights()
        
        # Performance recommendations
        if result.total_execution_time > 300:  # 5 minutes
            insights.recommendations.append("Consider breaking down slow test categories for faster feedback")
        
        if result.individual_test_times:
            slow_tests = [name for name, time in result.individual_test_times.items() if time > 30]
            if len(slow_tests) > 5:
                insights.recommendations.append(f"Review {len(slow_tests)} slow tests for optimization opportunities")
        
        # Reliability recommendations
        if result.success_rate < 95:
            insights.recommendations.append("Consider investigating failing tests - success rate below 95%")
        
        # Historical insights
        if len(self.analytics.execution_history) > 5:
            recent_success_rates = [r.success_rate for r in self.analytics.execution_history[:5]]
            if result.success_rate < min(recent_success_rates) - 5:
                insights.recommendations.append("Success rate declined significantly - investigate new failures")
        
        return insights
    
    def save_result_to_history(self, result: TestResult):
        """Save test result to historical database."""
        conn = sqlite3.connect(self.db_path)
        
        # Insert main test run record
        cursor = conn.execute('''
            INSERT INTO test_runs 
            (timestamp, execution_mode, total_tests, passed_tests, failed_tests, 
             skipped_tests, execution_time, success_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            result.execution_mode.value,
            result.total_tests,
            result.passed_tests,
            result.failed_tests,
            result.skipped_tests,
            result.total_execution_time,
            result.success_rate
        ))
        
        run_id = cursor.lastrowid
        
        # Insert individual test results if available
        for test_name, duration in result.individual_test_times.items():
            status = "passed"  # Default - would need more sophisticated parsing
            conn.execute('''
                INSERT INTO test_results (run_id, test_name, status, execution_time)
                VALUES (?, ?, ?, ?)
            ''', (run_id, test_name, status, duration))
        
        conn.commit()
        conn.close()
    
    def generate_html_report(self, result: TestResult, output_path: Path) -> str:
        """Generate comprehensive HTML report."""
        html_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Test Execution Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { background: #f0f8ff; padding: 20px; border-radius: 8px; }
        .metrics { display: flex; gap: 20px; margin: 20px 0; }
        .metric { background: #f9f9f9; padding: 15px; border-radius: 5px; text-align: center; }
        .metric h3 { margin: 0; color: #333; }
        .metric .value { font-size: 24px; font-weight: bold; color: #2196F3; }
        .section { margin: 30px 0; }
        .failure { background: #ffebee; padding: 10px; margin: 5px 0; border-left: 4px solid #f44336; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #f5f5f5; }
        .success { color: #4CAF50; }
        .failure-text { color: #f44336; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Test Execution Report</h1>
        <p><strong>Mode:</strong> {mode}</p>
        <p><strong>Executed:</strong> {timestamp}</p>
        <p><strong>Duration:</strong> {duration:.2f} seconds</p>
    </div>
    
    <div class="metrics">
        <div class="metric">
            <h3>Total Tests</h3>
            <div class="value">{total_tests}</div>
        </div>
        <div class="metric">
            <h3>Passed</h3>
            <div class="value success">{passed_tests}</div>
        </div>
        <div class="metric">
            <h3>Failed</h3>
            <div class="value failure-text">{failed_tests}</div>
        </div>
        <div class="metric">
            <h3>Success Rate</h3>
            <div class="value">{success_rate:.1f}%</div>
        </div>
    </div>
    
    {performance_section}
    {failure_section}
</body>
</html>
        '''
        
        # Generate performance section
        performance_section = ""
        if result.individual_test_times:
            slowest = sorted(result.individual_test_times.items(), key=lambda x: x[1], reverse=True)[:10]
            performance_section = f'''
            <div class="section">
                <h2>Performance Analysis</h2>
                <table>
                    <tr><th>Test Name</th><th>Duration (seconds)</th></tr>
                    {''.join(f'<tr><td>{name}</td><td>{duration:.3f}</td></tr>' for name, duration in slowest)}
                </table>
            </div>
            '''
        
        # Generate failure section  
        failure_section = ""
        if result.failure_details:
            failure_section = f'''
            <div class="section">
                <h2>Failures</h2>
                {''.join(f'<div class="failure">{failure}</div>' for failure in result.failure_details[:20])}
            </div>
            '''
        
        html_content = html_template.format(
            mode=result.execution_mode.name.replace('_', ' ').title(),
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            duration=result.total_execution_time,
            total_tests=result.total_tests,
            passed_tests=result.passed_tests,
            failed_tests=result.failed_tests,
            success_rate=result.success_rate,
            performance_section=performance_section,
            failure_section=failure_section
        )
        
        output_path.write_text(html_content)
        return str(output_path)
    
    def export_results(self, result: TestResult, format_type: str, output_path: Path):
        """Export results in various formats."""
        if format_type.lower() == 'json':
            self._export_json(result, output_path)
        elif format_type.lower() == 'xml':
            self._export_xml(result, output_path)
        elif format_type.lower() == 'csv':
            self._export_csv(result, output_path)
        elif format_type.lower() == 'html':
            self.generate_html_report(result, output_path)
        else:
            raise ValueError(f"Unsupported export format: {format_type}")
    
    def _export_json(self, result: TestResult, output_path: Path):
        """Export results as JSON."""
        data = {
            'execution_mode': result.execution_mode.value,
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_tests': result.total_tests,
                'passed_tests': result.passed_tests,
                'failed_tests': result.failed_tests,
                'skipped_tests': result.skipped_tests,
                'error_tests': result.error_tests,
                'success_rate': result.success_rate,
                'total_execution_time': result.total_execution_time
            },
            'individual_test_times': result.individual_test_times,
            'failure_details': result.failure_details,
            'command_executed': result.command_executed
        }
        
        output_path.write_text(json.dumps(data, indent=2))
    
    def _export_xml(self, result: TestResult, output_path: Path):
        """Export results as XML (JUnit format)."""
        xml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuites tests="{result.total_tests}" failures="{result.failed_tests}" 
           skips="{result.skipped_tests}" time="{result.total_execution_time:.3f}">
    <testsuite name="{result.execution_mode.value}" tests="{result.total_tests}" 
               failures="{result.failed_tests}" skips="{result.skipped_tests}" 
               time="{result.total_execution_time:.3f}">
'''
        
        # Add individual test cases
        for test_name, duration in result.individual_test_times.items():
            status = "failure" if test_name in result.failure_details else "success"
            xml_content += f'        <testcase name="{test_name}" time="{duration:.3f}"'
            if status == "failure":
                xml_content += '>\n            <failure message="Test failed"/>\n        </testcase>\n'
            else:
                xml_content += '/>\n'
        
        xml_content += '''    </testsuite>
</testsuites>'''
        
        output_path.write_text(xml_content)
    
    def _export_csv(self, result: TestResult, output_path: Path):
        """Export results as CSV."""
        csv_content = "test_name,status,duration,execution_mode,timestamp\n"
        
        timestamp = datetime.now().isoformat()
        for test_name, duration in result.individual_test_times.items():
            status = "FAILED" if test_name in result.failure_details else "PASSED"
            csv_content += f'"{test_name}",{status},{duration:.3f},{result.execution_mode.value},{timestamp}\n'
        
        output_path.write_text(csv_content)
    
    def get_performance_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get performance trends over specified number of days."""
        conn = sqlite3.connect(self.db_path)
        
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.execute('''
            SELECT timestamp, execution_mode, execution_time, success_rate
            FROM test_runs 
            WHERE timestamp > ?
            ORDER BY timestamp
        ''', (cutoff_date,))
        
        trends = {
            'execution_times': [],
            'success_rates': [],
            'mode_performance': {}
        }
        
        for row in cursor:
            trends['execution_times'].append({
                'timestamp': row[0],
                'time': row[2]
            })
            trends['success_rates'].append({
                'timestamp': row[0], 
                'rate': row[3]
            })
            
            mode = row[1]
            if mode not in trends['mode_performance']:
                trends['mode_performance'][mode] = []
            trends['mode_performance'][mode].append({
                'timestamp': row[0],
                'time': row[2],
                'success_rate': row[3]
            })
        
        conn.close()
        return trends
    
    def detect_flaky_tests(self, min_runs: int = 5) -> List[str]:
        """Detect potentially flaky tests based on inconsistent results."""
        conn = sqlite3.connect(self.db_path)
        
        # Find tests that have both passed and failed in recent runs
        cursor = conn.execute('''
            SELECT test_name, status, COUNT(*) as count
            FROM test_results
            WHERE run_id IN (
                SELECT id FROM test_runs 
                ORDER BY timestamp DESC 
                LIMIT 50
            )
            GROUP BY test_name, status
            HAVING count >= ?
        ''', (min_runs,))
        
        test_statuses = {}
        for row in cursor:
            test_name, status, count = row
            if test_name not in test_statuses:
                test_statuses[test_name] = {}
            test_statuses[test_name][status] = count
        
        flaky_tests = []
        for test_name, statuses in test_statuses.items():
            # Test is flaky if it has both passed and failed results
            if len(statuses) > 1:
                flaky_tests.append(test_name)
        
        conn.close()
        return flaky_tests