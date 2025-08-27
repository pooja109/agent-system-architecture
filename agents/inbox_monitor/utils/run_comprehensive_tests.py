#!/usr/bin/env python3
"""
Comprehensive Test Runner
=========================

Advanced test runner script that executes all test suites with coverage analysis,
performance benchmarking, and detailed reporting.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Add current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))


class TestSuite:
    """Test suite configuration."""

    def __init__(
        self,
        name: str,
        pattern: str,
        markers: list[str] | None = None,
        timeout: int = 300,
        description: str = "",
    ):
        self.name = name
        self.pattern = pattern
        self.markers = markers or []
        self.timeout = timeout
        self.description = description


class TestRunner:
    """Advanced test runner with comprehensive reporting."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.test_dir = base_dir / "tests"
        self.output_dir = base_dir / "test_output"
        self.coverage_dir = base_dir / "coverage"
        self.results = {}

        # Ensure output directories exist
        self.output_dir.mkdir(exist_ok=True)
        self.coverage_dir.mkdir(exist_ok=True)

        # Define test suites
        self.test_suites = [
            TestSuite(
                "unit_tests",
                "test_*.py",
                ["unit"],
                timeout=120,
                description="Unit tests for individual components",
            ),
            TestSuite(
                "comprehensive_unit",
                "test_comprehensive_unit.py",
                ["unit"],
                timeout=180,
                description="Comprehensive unit tests for all public methods",
            ),
            TestSuite(
                "graph_api_comprehensive",
                "test_graph_api_comprehensive.py",
                ["unit"],
                timeout=120,
                description="Comprehensive Graph API client tests",
            ),
            TestSuite(
                "edge_cases",
                "test_comprehensive_edge_cases.py",
                ["edge_case"],
                timeout=180,
                description="Edge cases and boundary condition tests",
            ),
            TestSuite(
                "error_conditions",
                "test_comprehensive_errors.py",
                ["error_condition"],
                timeout=180,
                description="Error conditions and failure scenario tests",
            ),
            TestSuite(
                "performance_integration",
                "test_performance_integration.py",
                ["performance", "integration"],
                timeout=300,
                description="Performance and integration tests",
            ),
            TestSuite(
                "existing_tests",
                "test_models.py test_monitor.py test_graph_api_client.py test_email_processor.py",
                [],
                timeout=120,
                description="Existing test suite",
            ),
        ]

    def run_command(self, command: list[str], timeout: int = 300) -> dict[str, Any]:
        """Run a command and return results."""
        print(f"Running: {' '.join(command)}")

        start_time = time.time()
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, cwd=self.base_dir
            )

            execution_time = time.time() - start_time

            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": execution_time,
                "command": " ".join(command),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "execution_time": timeout,
                "command": " ".join(command),
            }

        except Exception as e:
            return {
                "success": False,
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "execution_time": time.time() - start_time,
                "command": " ".join(command),
            }

    def run_test_suite(
        self,
        suite: TestSuite,
        coverage: bool = False,
        verbose: bool = False,
        fail_fast: bool = False,
    ) -> dict[str, Any]:
        """Run a specific test suite."""
        print(f"\n{'='*60}")
        print(f"Running Test Suite: {suite.name}")
        print(f"Description: {suite.description}")
        print(f"Pattern: {suite.pattern}")
        print(f"Markers: {suite.markers}")
        print(f"{'='*60}")

        # Build pytest command
        cmd = ["python", "-m", "pytest"]

        # Add test patterns
        if suite.pattern:
            if " " in suite.pattern:
                # Multiple files
                cmd.extend(suite.pattern.split())
            else:
                # Single pattern
                cmd.append(suite.pattern)

        # Add markers
        if suite.markers:
            for marker in suite.markers:
                cmd.extend(["-m", marker])

        # Add coverage
        if coverage:
            cmd.extend(
                [
                    "--cov=.",
                    "--cov-report=term-missing",
                    "--cov-report=html:" + str(self.coverage_dir / f"{suite.name}_coverage"),
                    "--cov-report=json:" + str(self.coverage_dir / f"{suite.name}_coverage.json"),
                ]
            )

        # Add verbosity
        if verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")

        # Add fail fast
        if fail_fast:
            cmd.append("--maxfail=1")

        # Add output options
        cmd.extend(
            [
                "--tb=short",
                "--durations=10",
                "--color=yes",
                "--disable-warnings",
            ]
        )

        # Add JSON report
        json_report = self.output_dir / f"{suite.name}_report.json"
        cmd.extend(["--json-report", "--json-report-file", str(json_report)])

        # Run the command
        result = self.run_command(cmd, timeout=suite.timeout)

        # Parse JSON report if available
        test_results = {}
        if json_report.exists():
            try:
                with open(json_report) as f:
                    test_results = json.load(f)
            except Exception as e:
                print(f"Warning: Could not parse JSON report: {e}")

        # Combine results
        suite_result = {
            "suite_name": suite.name,
            "suite_description": suite.description,
            "command_result": result,
            "test_results": test_results,
            "coverage_dir": str(self.coverage_dir / f"{suite.name}_coverage") if coverage else None,
        }

        # Print summary
        if result["success"]:
            print(f"✅ {suite.name} PASSED")
            if test_results:
                summary = test_results.get("summary", {})
                print(f"   Tests: {summary.get('total', 0)}")
                print(f"   Passed: {summary.get('passed', 0)}")
                print(f"   Failed: {summary.get('failed', 0)}")
                print(f"   Skipped: {summary.get('skipped', 0)}")
        else:
            print(f"❌ {suite.name} FAILED")
            if result["stderr"]:
                print(f"   Error: {result['stderr'][:200]}...")

        print(f"   Time: {result['execution_time']:.2f}s")

        return suite_result

    def run_coverage_analysis(self) -> dict[str, Any]:
        """Run comprehensive coverage analysis."""
        print(f"\n{'='*60}")
        print("Running Coverage Analysis")
        print(f"{'='*60}")

        # Run all tests with coverage
        cmd = [
            "python",
            "-m",
            "pytest",
            "tests/",
            "--cov=.",
            "--cov-report=term-missing",
            "--cov-report=html:" + str(self.coverage_dir / "combined_coverage"),
            "--cov-report=json:" + str(self.coverage_dir / "combined_coverage.json"),
            "--cov-report=xml:" + str(self.coverage_dir / "combined_coverage.xml"),
            "--cov-fail-under=90",
            "-q",
            "--tb=short",
        ]

        result = self.run_command(cmd, timeout=600)

        # Parse coverage results
        coverage_data = {}
        coverage_json = self.coverage_dir / "combined_coverage.json"
        if coverage_json.exists():
            try:
                with open(coverage_json) as f:
                    coverage_data = json.load(f)
            except Exception as e:
                print(f"Warning: Could not parse coverage JSON: {e}")

        coverage_result = {
            "command_result": result,
            "coverage_data": coverage_data,
            "coverage_html": str(self.coverage_dir / "combined_coverage"),
            "coverage_xml": str(self.coverage_dir / "combined_coverage.xml"),
        }

        # Print coverage summary
        if result["success"]:
            print("✅ Coverage analysis PASSED (≥90%)")
        else:
            print("❌ Coverage analysis FAILED (<90%)")

        if coverage_data:
            totals = coverage_data.get("totals", {})
            coverage_percent = totals.get("percent_covered", 0)
            print(f"   Coverage: {coverage_percent:.1f}%")
            print(f"   Lines: {totals.get('num_statements', 0)}")
            print(f"   Missing: {totals.get('missing_lines', 0)}")

        return coverage_result

    def run_linting_and_type_checking(self) -> dict[str, Any]:
        """Run linting and type checking."""
        print(f"\n{'='*60}")
        print("Running Linting and Type Checking")
        print(f"{'='*60}")

        results = {}

        # Black formatting check
        print("\nRunning Black formatting check...")
        black_result = self.run_command(["python", "-m", "black", "--check", "--diff", "."])
        results["black"] = black_result

        # Ruff linting
        print("\nRunning Ruff linting...")
        ruff_result = self.run_command(["python", "-m", "ruff", "check", "."])
        results["ruff"] = ruff_result

        # MyPy type checking
        print("\nRunning MyPy type checking...")
        mypy_result = self.run_command(["python", "-m", "mypy", ".", "--strict"])
        results["mypy"] = mypy_result

        # Bandit security check
        print("\nRunning Bandit security check...")
        bandit_result = self.run_command(["python", "-m", "bandit", "-r", "."])
        results["bandit"] = bandit_result

        # Print summary
        all_passed = all(result["success"] for result in results.values())
        if all_passed:
            print("✅ All linting and type checking PASSED")
        else:
            print("❌ Some linting or type checking FAILED")

        for tool, result in results.items():
            status = "✅ PASSED" if result["success"] else "❌ FAILED"
            print(f"   {tool}: {status}")

        return results

    def generate_summary_report(self) -> dict[str, Any]:
        """Generate comprehensive summary report."""
        print(f"\n{'='*60}")
        print("Generating Summary Report")
        print(f"{'='*60}")

        # Calculate overall statistics
        total_suites = len(self.results.get("test_suites", []))
        passed_suites = sum(
            1 for suite in self.results.get("test_suites", []) if suite["command_result"]["success"]
        )

        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        skipped_tests = 0

        for suite in self.results.get("test_suites", []):
            test_results = suite.get("test_results", {})
            summary = test_results.get("summary", {})
            total_tests += summary.get("total", 0)
            passed_tests += summary.get("passed", 0)
            failed_tests += summary.get("failed", 0)
            skipped_tests += summary.get("skipped", 0)

        # Coverage information
        coverage_info = self.results.get("coverage_analysis", {})
        coverage_data = coverage_info.get("coverage_data", {})
        coverage_percent = coverage_data.get("totals", {}).get("percent_covered", 0)

        # Quality checks
        quality_checks = self.results.get("quality_checks", {})
        quality_passed = sum(1 for result in quality_checks.values() if result["success"])

        summary = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "test_suites": {
                "total": total_suites,
                "passed": passed_suites,
                "failed": total_suites - passed_suites,
                "success_rate": (passed_suites / total_suites * 100) if total_suites > 0 else 0,
            },
            "tests": {
                "total": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "skipped": skipped_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            },
            "coverage": {
                "percentage": coverage_percent,
                "meets_requirement": coverage_percent >= 90,
                "html_report": coverage_info.get("coverage_html"),
            },
            "quality_checks": {
                "total": len(quality_checks),
                "passed": quality_passed,
                "failed": len(quality_checks) - quality_passed,
                "tools": list(quality_checks.keys()),
            },
            "overall_success": (
                passed_suites == total_suites
                and coverage_percent >= 90
                and quality_passed == len(quality_checks)
            ),
        }

        # Print summary
        print(f"\n{'='*60}")
        print("COMPREHENSIVE TEST SUMMARY")
        print(f"{'='*60}")

        print(
            f"Test Suites: {passed_suites}/{total_suites} passed ({summary['test_suites']['success_rate']:.1f}%)"
        )
        print(
            f"Tests: {passed_tests}/{total_tests} passed ({summary['tests']['success_rate']:.1f}%)"
        )
        print(
            f"Coverage: {coverage_percent:.1f}% ({'✅ MEETS' if coverage_percent >= 90 else '❌ BELOW'} 90% requirement)"
        )
        print(f"Quality: {quality_passed}/{len(quality_checks)} checks passed")

        overall_status = "✅ OVERALL SUCCESS" if summary["overall_success"] else "❌ OVERALL FAILURE"
        print(f"\n{overall_status}")

        # Save summary to file
        summary_file = self.output_dir / "test_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nDetailed results saved to: {self.output_dir}")
        if coverage_info.get("coverage_html"):
            print(f"Coverage report: {coverage_info['coverage_html']}/index.html")

        return summary

    def run_all_tests(
        self,
        coverage: bool = True,
        verbose: bool = False,
        fail_fast: bool = False,
        quality_checks: bool = True,
    ) -> dict[str, Any]:
        """Run all test suites and generate comprehensive report."""
        print("Starting Comprehensive Test Run")
        print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        start_time = time.time()

        # Initialize results
        self.results = {
            "start_time": start_time,
            "test_suites": [],
            "coverage_analysis": {},
            "quality_checks": {},
            "summary": {},
        }

        # Run each test suite
        for suite in self.test_suites:
            suite_result = self.run_test_suite(
                suite,
                coverage=False,  # Individual coverage is disabled to save time
                verbose=verbose,
                fail_fast=fail_fast,
            )
            self.results["test_suites"].append(suite_result)

            # Stop if fail_fast is enabled and suite failed
            if fail_fast and not suite_result["command_result"]["success"]:
                print(f"\n❌ Stopping due to failure in {suite.name}")
                break

        # Run coverage analysis
        if coverage:
            self.results["coverage_analysis"] = self.run_coverage_analysis()

        # Run quality checks
        if quality_checks:
            self.results["quality_checks"] = self.run_linting_and_type_checking()

        # Generate summary
        self.results["summary"] = self.generate_summary_report()
        self.results["end_time"] = time.time()
        self.results["total_time"] = self.results["end_time"] - start_time

        print(f"\nTotal execution time: {self.results['total_time']:.2f}s")

        return self.results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for inbox monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_comprehensive_tests.py                    # Run all tests
  python run_comprehensive_tests.py --no-coverage     # Skip coverage analysis
  python run_comprehensive_tests.py --verbose         # Verbose output
  python run_comprehensive_tests.py --fail-fast       # Stop on first failure
  python run_comprehensive_tests.py --suite unit_tests # Run specific suite
        """,
    )

    parser.add_argument("--no-coverage", action="store_true", help="Skip coverage analysis")

    parser.add_argument(
        "--no-quality", action="store_true", help="Skip quality checks (linting, type checking)"
    )

    parser.add_argument("--verbose", action="store_true", help="Verbose test output")

    parser.add_argument("--fail-fast", action="store_true", help="Stop on first test failure")

    parser.add_argument("--suite", help="Run specific test suite only")

    parser.add_argument("--list-suites", action="store_true", help="List available test suites")

    parser.add_argument("--output-dir", help="Output directory for test results")

    args = parser.parse_args()

    # Set up test runner
    base_dir = Path(__file__).parent
    runner = TestRunner(base_dir)

    # Override output directory if specified
    if args.output_dir:
        runner.output_dir = Path(args.output_dir)
        runner.output_dir.mkdir(exist_ok=True)

    # List suites if requested
    if args.list_suites:
        print("Available test suites:")
        for suite in runner.test_suites:
            print(f"  {suite.name}: {suite.description}")
        return 0

    # Run specific suite if requested
    if args.suite:
        suite_names = [s.name for s in runner.test_suites]
        if args.suite not in suite_names:
            print(f"Error: Suite '{args.suite}' not found")
            print(f"Available suites: {', '.join(suite_names)}")
            return 1

        suite = next(s for s in runner.test_suites if s.name == args.suite)
        result = runner.run_test_suite(
            suite, coverage=not args.no_coverage, verbose=args.verbose, fail_fast=args.fail_fast
        )

        return 0 if result["command_result"]["success"] else 1

    # Run all tests
    try:
        results = runner.run_all_tests(
            coverage=not args.no_coverage,
            verbose=args.verbose,
            fail_fast=args.fail_fast,
            quality_checks=not args.no_quality,
        )

        # Return appropriate exit code
        return 0 if results["summary"]["overall_success"] else 1

    except KeyboardInterrupt:
        print("\n❌ Test run interrupted by user")
        return 1

    except Exception as e:
        print(f"\n❌ Test run failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
