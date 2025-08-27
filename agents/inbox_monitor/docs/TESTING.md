# Test Execution Guide

Complete guide for running tests in the Inbox Monitor system with the advanced test runner CLI.

> **📚 Related Documentation:**
> - **Prerequisites:** [Setup Guide](SETUP.md) - Install and configure before testing
> - **Configuration:** [Configuration Guide](CONFIGURATION.md) - Service setup required for integration tests
> - **Understanding Tests:** [Scenarios Guide](SCENARIOS.md) - What the tests validate
> - **Utilities:** [Utilities Reference](UTILS.md) - Test scripts and utilities
> - **Need Help?** [Troubleshooting Guide](TROUBLESHOOTING.md) - Common testing issues
> - **Back to Hub:** [Documentation Hub](README.md) - All available guides

## 🚀 Quick Start

```bash
# Get help and see all options
python test_runner.py --help

# Quick development feedback (< 2 minutes)
python test_runner.py --fast

# Complete test suite for CI/CD (< 8 minutes)
python test_runner.py --all-except-slow

# Critical functionality validation (< 1 minute)
python test_runner.py --smoke
```

## 📋 Test Execution Modes

### Development Modes

| Mode | Command | Tests | Duration | Use Case |
|------|---------|-------|----------|----------|
| **Fast** | `--fast` | 42 tests | 1-3 min | Quick development feedback |
| **Smoke** | `--smoke` | 5 tests | 30-60 sec | Critical path validation |
| **Integration** | `--integration` | ~100 tests | 3-5 min | Integration testing with mocked services |
| **Edge Cases** | `--edge-cases` | ~50 tests | 2-4 min | Error handling and boundary conditions |

### Production Modes

| Mode | Command | Tests | Duration | Use Case |
|------|---------|-------|----------|----------|
| **All Except Slow** | `--all-except-slow` | ~200 tests | 6-8 min | Complete suite for CI/CD |
| **CI Safe** | `--ci-safe` | ~150 tests | 4-6 min | Automated CI environments |
| **Full** | `--full` | ~300 tests | 15-20 min | Complete validation including slow tests |

### Custom Mode

```bash
# Custom pytest marker expressions
python test_runner.py --custom "fast and azure"
python test_runner.py --custom "integration and not retry" 
python test_runner.py --custom "smoke or (fast and email)"
```

## ⚙️ Configuration Profiles

Pre-configured test execution profiles for different scenarios:

```bash
# List available profiles
python test_runner.py --list-profiles

# Development profile - fast feedback with parallel execution
python test_runner.py --profile fast-dev

# CI pull request profile - comprehensive validation
python test_runner.py --profile ci-pull-request

# CI main branch profile - full test suite
python test_runner.py --profile ci-main-branch

# Performance testing profile - benchmarking focus
python test_runner.py --profile performance-testing

# Debug profile - maximum verbosity, no timeouts
python test_runner.py --profile debug-mode

# Production smoke test profile
python test_runner.py --profile smoke-check
```

## 📊 Reporting and Analysis

### Generate Reports

```bash
# HTML report with comprehensive analytics
python test_runner.py --fast --generate-report html

# JSON report for automation
python test_runner.py --smoke --generate-report json

# XML report for CI/CD systems (JUnit compatible)
python test_runner.py --integration --generate-report xml

# CSV report for spreadsheet analysis
python test_runner.py --fast --generate-report csv

# PDF report for documentation (requires dependencies)
python test_runner.py --smoke --generate-report pdf
```

### Multi-Format Export

```bash
# Export in multiple formats simultaneously
python test_runner.py --fast --export-formats json csv html

# All supported formats
python test_runner.py --smoke --export-formats json xml csv html junit yaml markdown
```

### Test Analysis

```bash
# Run comprehensive test analysis with insights
python test_runner.py --integration --analyze

# Show performance trends over time
python test_runner.py --trends

# Combined analysis and reporting
python test_runner.py --fast --analyze --generate-report html
```

## 🔍 Advanced Development Features

### Watch Mode

Continuous testing with file system monitoring:

```bash
# Watch for changes and re-run tests automatically
python test_runner.py --fast --watch

# Watch with specific profile
python test_runner.py --profile fast-dev --watch
```

Press `Ctrl+C` to stop watching.

### Performance Benchmarking

```bash
# Performance benchmarking with multiple runs
python test_runner.py --smoke --benchmark

# Benchmark with analysis
python test_runner.py --fast --benchmark --analyze
```

### Code Coverage

```bash
# Run tests with code coverage
python test_runner.py --fast --coverage

# Generate HTML coverage report
python test_runner.py --integration --coverage --coverage-report html

# Generate XML coverage report for CI
python test_runner.py --all-except-slow --coverage --coverage-report xml
```

### Bisect Mode

Automated test failure debugging:

```bash
# Debug specific failing test
python test_runner.py --bisect --custom "test_failing_function"
```

## 🔧 CI/CD Integration

### Platform Optimization

```bash
# GitHub Actions optimization
python test_runner.py --all-except-slow --ci-mode github

# Azure DevOps optimization
python test_runner.py --ci-safe --ci-mode azure

# Jenkins optimization
python test_runner.py --integration --ci-mode jenkins

# GitLab CI optimization
python test_runner.py --smoke --ci-mode gitlab

# Generic CI optimization
python test_runner.py --ci-safe --ci-mode generic
```

### CI/CD Example Workflows

**GitHub Actions:**
```yaml
- name: Run Tests
  run: |
    python test_runner.py --all-except-slow --ci-mode github --generate-report json
    
- name: Upload Test Results
  uses: actions/upload-artifact@v3
  with:
    name: test-results
    path: test_reports/
```

**Azure DevOps:**
```yaml
- script: |
    python test_runner.py --ci-safe --ci-mode azure --export-formats xml json
  displayName: 'Run Tests'
  
- task: PublishTestResults@2
  inputs:
    testResultsFiles: 'test_reports/test_results.xml'
```

## 🎛️ Advanced Options

### Execution Control

```bash
# Stop on first failure
python test_runner.py --fast --fail-fast

# Run tests in parallel
python test_runner.py --integration --parallel

# Set overall timeout
python test_runner.py --smoke --timeout 300

# Limit number of failures
python test_runner.py --fast --max-failures 5

# Quiet mode (minimal output)
python test_runner.py --smoke --quiet

# Verbose mode (detailed output)
python test_runner.py --fast --verbose
```

### Output Control

```bash
# Save detailed results to file
python test_runner.py --integration --output test_results.json

# Preview execution without running tests
python test_runner.py --all-except-slow --dry-run
```

### Monitoring and Logging

```bash
# Enable comprehensive monitoring
python test_runner.py --fast --monitoring

# Enable specific plugins
python test_runner.py --smoke --plugins performance-tracker analytics
```

## 📖 Information Commands

```bash
# Show available test markers and descriptions
python test_runner.py --list-markers

# List configuration profiles
python test_runner.py --list-profiles

# Show available plugins
python test_runner.py --list-plugins

# Show supported export formats
python test_runner.py --supported-formats

# Estimate execution time
python test_runner.py --integration --estimate-time
```

## 🐛 Traditional pytest Commands

For direct pytest usage (advanced users):

```bash
# Basic pytest execution
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_email_processor.py

# Run with markers
pytest -m "fast and not slow"

# Run with coverage
pytest --cov=services --cov=models --cov-report=html
```

## 📁 Test Results Location

All test results and reports are saved to:
- **HTML Reports:** `test_reports/test_report.html`
- **JSON Results:** `test_reports/test_results.json`  
- **Coverage Reports:** `htmlcov/index.html`
- **Export Summary:** `test_reports/export_summary.json`

## 🆘 Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Run from the correct directory
cd /path/to/agents/inbox_monitor
python test_runner.py --smoke
```

**No Tests Found:**
```bash
# Check test markers are properly configured
python test_runner.py --list-markers

# Use dry-run to see what would be selected
python test_runner.py --fast --dry-run
```

**Performance Issues:**
```bash
# Use faster modes for development
python test_runner.py --fast

# Skip slow tests
python test_runner.py --all-except-slow
```

### Getting Help

```bash
# Show complete help
python test_runner.py --help

# Get execution time estimates
python test_runner.py --MODE --estimate-time
```

## 🔗 Related Documentation

- **[Main README](../README.md)** - Complete system documentation
- **[Setup Guide](SETUP.md)** - Installation and initial setup
- **[Configuration Guide](CONFIGURATION.md)** - Environment configuration
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions