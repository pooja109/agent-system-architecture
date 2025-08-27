"""
Test Result Analysis Engine for Test Runner CLI
===============================================

Provides advanced test result analysis, insight generation, and trend tracking.
"""

import json
import sqlite3
import statistics
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import re

try:
    from .test_execution import TestResult
except ImportError:
    from test_execution import TestResult
try:
    from .config.runner_config import ExecutionMode
except ImportError:
    from config.runner_config import ExecutionMode

@dataclass
class TestTrendData:
    """Historical trend data for a specific test."""
    test_name: str
    execution_times: List[float] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time: float = 0.0
    trend_direction: str = "stable"  # "improving", "degrading", "stable"
    reliability_score: float = 100.0

@dataclass 
class PerformanceMetrics:
    """Performance analysis metrics."""
    avg_test_time: float = 0.0
    median_test_time: float = 0.0
    p95_test_time: float = 0.0
    slowest_tests: List[Tuple[str, float]] = field(default_factory=list)
    performance_regression_candidates: List[str] = field(default_factory=list)
    time_distribution: Dict[str, int] = field(default_factory=dict)

@dataclass
class ReliabilityMetrics:
    """Test reliability analysis metrics."""
    flaky_tests: List[str] = field(default_factory=list)
    consistently_failing_tests: List[str] = field(default_factory=list)
    recently_fixed_tests: List[str] = field(default_factory=list)
    failure_rate_by_category: Dict[str, float] = field(default_factory=dict)
    error_pattern_analysis: Dict[str, int] = field(default_factory=dict)

@dataclass
class TestQualityReport:
    """Comprehensive test quality analysis report."""
    overall_score: float = 0.0
    performance_metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    reliability_metrics: ReliabilityMetrics = field(default_factory=ReliabilityMetrics)
    trend_analysis: List[TestTrendData] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    risk_areas: List[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

class TestAnalyzer:
    """Advanced test result analyzer with trend tracking and insights."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path('test_data/test_history.db')
        self._ensure_database_exists()
    
    def _ensure_database_exists(self):
        """Ensure the database exists and has the required tables."""
        if not self.db_path.exists():
            self.db_path.parent.mkdir(exist_ok=True, parents=True)
        
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
    
    def analyze_test_results(self, result: TestResult, days_of_history: int = 30) -> TestQualityReport:
        """Perform comprehensive analysis of test results."""
        report = TestQualityReport()
        
        # Load historical data
        historical_data = self._load_historical_data(days_of_history)
        
        # Analyze performance metrics
        report.performance_metrics = self._analyze_performance(result, historical_data)
        
        # Analyze reliability metrics
        report.reliability_metrics = self._analyze_reliability(result, historical_data)
        
        # Generate trend analysis
        report.trend_analysis = self._analyze_trends(historical_data)
        
        # Calculate overall quality score
        report.overall_score = self._calculate_quality_score(report)
        
        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)
        
        # Identify risk areas
        report.risk_areas = self._identify_risk_areas(report)
        
        return report
    
    def _load_historical_data(self, days: int) -> List[Dict[str, Any]]:
        """Load historical test data from database."""
        conn = sqlite3.connect(self.db_path)
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor = conn.execute('''
            SELECT tr.*, trun.timestamp, trun.execution_mode
            FROM test_results tr
            JOIN test_runs trun ON tr.run_id = trun.id
            WHERE trun.timestamp > ?
            ORDER BY trun.timestamp DESC
        ''', (cutoff_date,))
        
        data = []
        for row in cursor:
            data.append({
                'test_name': row[2],
                'status': row[3],
                'execution_time': row[4],
                'error_message': row[5],
                'timestamp': row[6],
                'execution_mode': row[7]
            })
        
        conn.close()
        return data
    
    def _analyze_performance(self, result: TestResult, historical_data: List[Dict]) -> PerformanceMetrics:
        """Analyze performance metrics from current and historical data."""
        metrics = PerformanceMetrics()
        
        if not result.individual_test_times:
            return metrics
        
        times = list(result.individual_test_times.values())
        
        # Basic statistics
        metrics.avg_test_time = statistics.mean(times)
        metrics.median_test_time = statistics.median(times)
        metrics.p95_test_time = sorted(times)[int(0.95 * len(times))] if times else 0.0
        
        # Slowest tests
        metrics.slowest_tests = sorted(
            result.individual_test_times.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Time distribution analysis
        metrics.time_distribution = self._categorize_test_times(times)
        
        # Performance regression detection
        metrics.performance_regression_candidates = self._detect_performance_regressions(
            result, historical_data
        )
        
        return metrics
    
    def _analyze_reliability(self, result: TestResult, historical_data: List[Dict]) -> ReliabilityMetrics:
        """Analyze test reliability metrics."""
        metrics = ReliabilityMetrics()
        
        # Detect flaky tests
        metrics.flaky_tests = self._detect_flaky_tests(historical_data)
        
        # Find consistently failing tests
        metrics.consistently_failing_tests = self._find_consistently_failing_tests(historical_data)
        
        # Find recently fixed tests
        metrics.recently_fixed_tests = self._find_recently_fixed_tests(historical_data)
        
        # Analyze failure rates by category
        metrics.failure_rate_by_category = self._analyze_failure_rates_by_category(historical_data)
        
        # Analyze error patterns
        metrics.error_pattern_analysis = self._analyze_error_patterns(result, historical_data)
        
        return metrics
    
    def _analyze_trends(self, historical_data: List[Dict]) -> List[TestTrendData]:
        """Analyze trends for individual tests."""
        test_data = defaultdict(lambda: {'times': [], 'statuses': []})
        
        # Group data by test name
        for record in historical_data:
            test_name = record['test_name']
            test_data[test_name]['times'].append(record['execution_time'])
            test_data[test_name]['statuses'].append(record['status'])
        
        trends = []
        for test_name, data in test_data.items():
            if len(data['times']) < 3:  # Need at least 3 data points for trend
                continue
            
            trend = TestTrendData(test_name=test_name)
            trend.execution_times = data['times']
            trend.success_count = data['statuses'].count('passed')
            trend.failure_count = len(data['statuses']) - trend.success_count
            trend.avg_execution_time = statistics.mean(data['times']) if data['times'] else 0.0
            trend.reliability_score = (trend.success_count / len(data['statuses'])) * 100
            
            # Determine trend direction
            trend.trend_direction = self._calculate_trend_direction(data['times'])
            
            trends.append(trend)
        
        # Sort by reliability score (worst first)
        return sorted(trends, key=lambda x: x.reliability_score)
    
    def _calculate_quality_score(self, report: TestQualityReport) -> float:
        """Calculate overall test suite quality score (0-100)."""
        score_components = []
        
        # Performance component (25% weight)
        perf_score = 100.0
        if report.performance_metrics.avg_test_time > 10:  # 10 seconds threshold
            perf_score -= min(50, (report.performance_metrics.avg_test_time - 10) * 2)
        if len(report.performance_metrics.performance_regression_candidates) > 0:
            perf_score -= len(report.performance_metrics.performance_regression_candidates) * 5
        score_components.append(('performance', perf_score, 0.25))
        
        # Reliability component (50% weight)
        reliability_score = 100.0
        reliability_score -= len(report.reliability_metrics.flaky_tests) * 10
        reliability_score -= len(report.reliability_metrics.consistently_failing_tests) * 15
        score_components.append(('reliability', max(0, reliability_score), 0.50))
        
        # Trend component (25% weight)
        trend_score = 100.0
        degrading_trends = [t for t in report.trend_analysis if t.trend_direction == 'degrading']
        trend_score -= len(degrading_trends) * 5
        score_components.append(('trend', max(0, trend_score), 0.25))
        
        # Calculate weighted average
        total_score = sum(score * weight for _, score, weight in score_components)
        return round(total_score, 1)
    
    def _generate_recommendations(self, report: TestQualityReport) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Performance recommendations
        if report.performance_metrics.avg_test_time > 5:
            recommendations.append(
                f"Average test time is {report.performance_metrics.avg_test_time:.1f}s. "
                "Consider optimizing slow tests or splitting into faster categories."
            )
        
        if len(report.performance_metrics.slowest_tests) > 0:
            slowest_time = report.performance_metrics.slowest_tests[0][1]
            if slowest_time > 30:
                recommendations.append(
                    f"Slowest test takes {slowest_time:.1f}s. Review for optimization opportunities."
                )
        
        # Reliability recommendations
        if report.reliability_metrics.flaky_tests:
            recommendations.append(
                f"Found {len(report.reliability_metrics.flaky_tests)} flaky tests. "
                "These should be prioritized for stabilization."
            )
        
        if report.reliability_metrics.consistently_failing_tests:
            recommendations.append(
                f"Found {len(report.reliability_metrics.consistently_failing_tests)} "
                "consistently failing tests. These need immediate attention."
            )
        
        # Trend recommendations
        degrading_trends = [t for t in report.trend_analysis if t.trend_direction == 'degrading']
        if degrading_trends:
            recommendations.append(
                f"Found {len(degrading_trends)} tests with degrading performance trends. "
                "Monitor these for continued deterioration."
            )
        
        # Quality score recommendations
        if report.overall_score < 70:
            recommendations.append(
                "Overall test quality score is below 70. Focus on reliability improvements."
            )
        elif report.overall_score < 85:
            recommendations.append(
                "Test quality is good but has room for improvement. "
                "Address performance and reliability issues."
            )
        
        return recommendations
    
    def _identify_risk_areas(self, report: TestQualityReport) -> List[str]:
        """Identify high-risk areas that need attention."""
        risks = []
        
        # High-risk reliability issues
        if len(report.reliability_metrics.consistently_failing_tests) > 5:
            risks.append("High number of consistently failing tests indicates systematic issues")
        
        # Performance risks
        if report.performance_metrics.avg_test_time > 15:
            risks.append("Very slow average test time may impact developer productivity")
        
        # Trend risks
        high_risk_trends = [
            t for t in report.trend_analysis 
            if t.reliability_score < 50 and t.trend_direction == 'degrading'
        ]
        if high_risk_trends:
            risks.append("Critical tests showing both low reliability and degrading trends")
        
        # Overall quality risks
        if report.overall_score < 60:
            risks.append("Overall test quality is critically low and needs immediate attention")
        
        return risks
    
    def _categorize_test_times(self, times: List[float]) -> Dict[str, int]:
        """Categorize test times into buckets."""
        categories = {
            'very_fast': 0,    # < 1s
            'fast': 0,         # 1-5s
            'medium': 0,       # 5-15s
            'slow': 0,         # 15-60s
            'very_slow': 0     # > 60s
        }
        
        for time in times:
            if time < 1:
                categories['very_fast'] += 1
            elif time < 5:
                categories['fast'] += 1
            elif time < 15:
                categories['medium'] += 1
            elif time < 60:
                categories['slow'] += 1
            else:
                categories['very_slow'] += 1
        
        return categories
    
    def _detect_performance_regressions(self, result: TestResult, historical_data: List[Dict]) -> List[str]:
        """Detect tests with potential performance regressions."""
        if not result.individual_test_times:
            return []
        
        # Group historical data by test name
        historical_times = defaultdict(list)
        for record in historical_data:
            if record['execution_time'] and record['execution_time'] > 0:
                historical_times[record['test_name']].append(record['execution_time'])
        
        regressions = []
        for test_name, current_time in result.individual_test_times.items():
            if test_name in historical_times and len(historical_times[test_name]) >= 5:
                historical_avg = statistics.mean(historical_times[test_name])
                
                # Flag as regression if current time is 50% slower than historical average
                if current_time > historical_avg * 1.5 and current_time > 5:  # Only flag if > 5s
                    regressions.append(test_name)
        
        return regressions
    
    def _detect_flaky_tests(self, historical_data: List[Dict]) -> List[str]:
        """Detect flaky tests from historical data."""
        test_results = defaultdict(list)
        
        for record in historical_data:
            test_results[record['test_name']].append(record['status'])
        
        flaky_tests = []
        for test_name, statuses in test_results.items():
            if len(statuses) >= 10:  # Need sufficient data
                passed_count = statuses.count('passed')
                failed_count = len(statuses) - passed_count
                
                # Test is flaky if it has both passes and failures and success rate is 20-80%
                if passed_count > 0 and failed_count > 0:
                    success_rate = passed_count / len(statuses)
                    if 0.2 <= success_rate <= 0.8:
                        flaky_tests.append(test_name)
        
        return flaky_tests
    
    def _find_consistently_failing_tests(self, historical_data: List[Dict]) -> List[str]:
        """Find tests that consistently fail."""
        test_results = defaultdict(list)
        
        for record in historical_data[-50:]:  # Look at last 50 runs
            test_results[record['test_name']].append(record['status'])
        
        failing_tests = []
        for test_name, statuses in test_results.items():
            if len(statuses) >= 5:  # Need at least 5 runs
                failure_rate = (len(statuses) - statuses.count('passed')) / len(statuses)
                if failure_rate >= 0.8:  # 80% failure rate
                    failing_tests.append(test_name)
        
        return failing_tests
    
    def _find_recently_fixed_tests(self, historical_data: List[Dict]) -> List[str]:
        """Find tests that were recently fixed."""
        test_results = defaultdict(list)
        
        # Group by test name and sort by timestamp
        for record in historical_data:
            test_results[record['test_name']].append(record)
        
        fixed_tests = []
        for test_name, records in test_results.items():
            if len(records) >= 10:
                # Sort by timestamp
                records.sort(key=lambda x: x['timestamp'])
                
                # Check if last 5 runs are successful after previous failures
                recent_statuses = [r['status'] for r in records[-5:]]
                older_statuses = [r['status'] for r in records[-15:-5]]
                
                if (all(status == 'passed' for status in recent_statuses) and
                    any(status != 'passed' for status in older_statuses)):
                    fixed_tests.append(test_name)
        
        return fixed_tests
    
    def _analyze_failure_rates_by_category(self, historical_data: List[Dict]) -> Dict[str, float]:
        """Analyze failure rates by test category."""
        category_results = defaultdict(lambda: {'total': 0, 'failed': 0})
        
        for record in historical_data:
            # Extract category from test name (assumes naming convention)
            test_name = record['test_name']
            category = self._extract_test_category(test_name)
            
            category_results[category]['total'] += 1
            if record['status'] != 'passed':
                category_results[category]['failed'] += 1
        
        failure_rates = {}
        for category, results in category_results.items():
            if results['total'] > 0:
                failure_rates[category] = (results['failed'] / results['total']) * 100
        
        return failure_rates
    
    def _analyze_error_patterns(self, result: TestResult, historical_data: List[Dict]) -> Dict[str, int]:
        """Analyze common error patterns."""
        error_patterns = Counter()
        
        # Analyze current failures
        for failure in result.failure_details:
            pattern = self._extract_error_pattern(failure)
            if pattern:
                error_patterns[pattern] += 1
        
        # Analyze historical errors
        for record in historical_data:
            if record['error_message']:
                pattern = self._extract_error_pattern(record['error_message'])
                if pattern:
                    error_patterns[pattern] += 1
        
        return dict(error_patterns.most_common(10))
    
    def _extract_test_category(self, test_name: str) -> str:
        """Extract category from test name."""
        # Common patterns: test_integration_*, test_unit_*, test_*_integration
        if 'integration' in test_name.lower():
            return 'integration'
        elif 'unit' in test_name.lower():
            return 'unit'
        elif 'edge' in test_name.lower():
            return 'edge_case'
        elif 'performance' in test_name.lower():
            return 'performance'
        elif 'smoke' in test_name.lower():
            return 'smoke'
        else:
            return 'other'
    
    def _extract_error_pattern(self, error_message: str) -> Optional[str]:
        """Extract common error pattern from error message."""
        if not error_message:
            return None
        
        # Common patterns
        patterns = {
            r'AssertionError': 'Assertion Failure',
            r'TimeoutError|timeout': 'Timeout',
            r'ConnectionError|Connection refused': 'Connection Issue',
            r'KeyError': 'Missing Key',
            r'AttributeError': 'Attribute Error',
            r'TypeError': 'Type Error',
            r'ValueError': 'Value Error',
            r'ImportError|ModuleNotFoundError': 'Import Error'
        }
        
        for pattern, category in patterns.items():
            if re.search(pattern, error_message, re.IGNORECASE):
                return category
        
        return 'Other Error'
    
    def _calculate_trend_direction(self, times: List[float]) -> str:
        """Calculate trend direction for test execution times."""
        if len(times) < 3:
            return "stable"
        
        # Use simple linear trend analysis
        recent_avg = statistics.mean(times[-3:])
        older_avg = statistics.mean(times[:-3]) if len(times) > 3 else recent_avg
        
        if recent_avg > older_avg * 1.2:
            return "degrading"
        elif recent_avg < older_avg * 0.8:
            return "improving"
        else:
            return "stable"
    
    def generate_trend_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive trend report."""
        historical_data = self._load_historical_data(days)
        
        # Overall trends
        execution_times_by_day = defaultdict(list)
        success_rates_by_day = defaultdict(list)
        
        for record in historical_data:
            day = record['timestamp'][:10]  # Extract date part
            if record['execution_time']:
                execution_times_by_day[day].append(record['execution_time'])
            success_rates_by_day[day].append(1 if record['status'] == 'passed' else 0)
        
        daily_trends = {}
        for day in execution_times_by_day:
            daily_trends[day] = {
                'avg_execution_time': statistics.mean(execution_times_by_day[day]),
                'success_rate': statistics.mean(success_rates_by_day[day]) * 100,
                'test_count': len(execution_times_by_day[day])
            }
        
        return {
            'daily_trends': daily_trends,
            'analysis_period_days': days,
            'total_test_runs': len(historical_data),
            'generated_at': datetime.now().isoformat()
        }
    
    def export_analysis_report(self, report: TestQualityReport, output_path: Path, format_type: str = 'json'):
        """Export analysis report to file."""
        output_path.parent.mkdir(exist_ok=True, parents=True)
        
        if format_type.lower() == 'json':
            # Convert dataclass to dict for JSON serialization
            report_dict = {
                'overall_score': report.overall_score,
                'performance_metrics': {
                    'avg_test_time': report.performance_metrics.avg_test_time,
                    'median_test_time': report.performance_metrics.median_test_time,
                    'p95_test_time': report.performance_metrics.p95_test_time,
                    'slowest_tests': report.performance_metrics.slowest_tests,
                    'performance_regression_candidates': report.performance_metrics.performance_regression_candidates,
                    'time_distribution': report.performance_metrics.time_distribution
                },
                'reliability_metrics': {
                    'flaky_tests': report.reliability_metrics.flaky_tests,
                    'consistently_failing_tests': report.reliability_metrics.consistently_failing_tests,
                    'recently_fixed_tests': report.reliability_metrics.recently_fixed_tests,
                    'failure_rate_by_category': report.reliability_metrics.failure_rate_by_category,
                    'error_pattern_analysis': report.reliability_metrics.error_pattern_analysis
                },
                'recommendations': report.recommendations,
                'risk_areas': report.risk_areas,
                'generated_at': report.generated_at
            }
            
            output_path.write_text(json.dumps(report_dict, indent=2))
        
        else:
            raise ValueError(f"Unsupported export format: {format_type}")