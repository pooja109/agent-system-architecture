# Test Marker Documentation

This document describes the test marker system used in the inbox_monitor test suite to enable selective test execution, performance optimization, and efficient CI/CD pipeline integration.

## Overview

The test suite uses pytest markers to categorize and classify tests along multiple dimensions:

- **Performance Markers**: Classify tests by execution time (fast/medium/slow)
- **Functional Markers**: Classify tests by testing approach (unit/integration/edge_case)
- **Descriptive Markers**: Classify tests by functionality or service integration
- **Execution Context Markers**: Classify tests by execution environment requirements

## Marker Categories

### Performance Markers

Performance markers enable selective test execution based on time constraints and development workflow needs.

#### `@pytest.mark.fast`
- **Execution Time**: < 5 seconds
- **Characteristics**: Unit tests with comprehensive mocking, simple validation operations, configuration tests
- **Use Cases**: Rapid development feedback, pre-commit hooks, IDE integration
- **Examples**: CLI argument parsing, model validation, configuration loading
- **Parallel Execution**: Safe for parallel execution with high concurrency

#### `@pytest.mark.medium` 
- **Execution Time**: 5-30 seconds
- **Characteristics**: Integration tests with multiple components, database operations, async workflows
- **Use Cases**: Full development testing, pre-merge validation, integration verification
- **Examples**: Service integration, database queries, file I/O operations
- **Parallel Execution**: Safe with moderate concurrency and resource management

#### `@pytest.mark.slow`
- **Execution Time**: > 30 seconds  
- **Characteristics**: End-to-end workflows, performance tests, external service integration
- **Use Cases**: Comprehensive testing, performance validation, deployment verification
- **Examples**: Complete email processing workflows, load testing, external API integration
- **Parallel Execution**: Requires sequential execution or careful resource coordination

### Functional Markers

Functional markers classify tests by their testing approach and isolation level.

#### `@pytest.mark.unit`
- **Isolation Level**: Complete isolation with mocks/stubs
- **Scope**: Single component or method testing
- **Dependencies**: No external dependencies (database, network, file system)
- **Examples**: Method validation, error handling, business logic
- **Reliability**: High reliability, deterministic results

#### `@pytest.mark.integration`
- **Isolation Level**: Multi-component interaction with controlled dependencies
- **Scope**: Service-to-service communication, component integration
- **Dependencies**: Mocked external services, test databases, controlled environments
- **Examples**: Database integration, service workflows, configuration integration
- **Reliability**: Good reliability with proper environment management

#### `@pytest.mark.edge_case`
- **Isolation Level**: Varies (unit or integration)
- **Scope**: Error conditions, boundary values, exceptional scenarios
- **Dependencies**: Depends on the scenario being tested
- **Examples**: Invalid input handling, timeout scenarios, resource exhaustion
- **Reliability**: Tests failure conditions and recovery mechanisms

### Descriptive Markers

Descriptive markers identify tests by the functionality or services they test.

#### Service Integration Markers
- `@pytest.mark.azure`: Azure services (AI Foundry, Graph API, Key Vault)
- `@pytest.mark.salesforce`: Salesforce API and data integration
- `@pytest.mark.databricks`: Databricks connections and data processing
- `@pytest.mark.email`: Email processing, parsing, and transformation
- `@pytest.mark.database`: Database operations and data persistence

#### Functionality Markers
- `@pytest.mark.cli`: Command-line interface and argument processing
- `@pytest.mark.prompt`: Prompt management and template rendering
- `@pytest.mark.monitoring`: System monitoring, health checks, metrics
- `@pytest.mark.security`: Security compliance, PII handling, access controls
- `@pytest.mark.scenario_tracking`: Scenario tracking functionality and storage

#### Specialized Testing Markers
- `@pytest.mark.retry`: Retry logic, failure recovery, timeout handling
- `@pytest.mark.performance`: Performance validation and resource usage
- `@pytest.mark.benchmark`: Performance benchmarks and system limits
- `@pytest.mark.load`: Load testing with high volume and concurrency

### Execution Context Markers

Execution context markers specify environment and execution requirements.

#### Environment Markers
- `@pytest.mark.ci_safe`: Safe for automated CI/CD execution
- `@pytest.mark.production`: Production environment compatible
- `@pytest.mark.real_database`: Requires real database connections
- `@pytest.mark.smoke`: Critical path tests for basic functionality

#### Execution Strategy Markers
- `@pytest.mark.e2e`: End-to-end system workflow tests
- `@pytest.mark.parallel_safe`: Safe for high-concurrency parallel execution
- `@pytest.mark.sequential`: Requires sequential execution due to resource conflicts

## Test Execution Strategies

### Development Workflow

#### Quick Feedback Loop (< 30 seconds)
```bash
# Run only fast unit tests for immediate feedback
pytest -m "fast and unit" --tb=short

# Run fast tests across all functionality
pytest -m "fast" --tb=short -q
```

#### Development Testing (< 2 minutes)  
```bash
# Run fast and medium tests for comprehensive coverage
pytest -m "fast or medium" --tb=short

# Run all unit and integration tests (excluding slow e2e)
pytest -m "(unit or integration) and not slow" --tb=short
```

#### Pre-commit Validation (< 5 minutes)
```bash
# Run all tests except slow external integrations
pytest -m "not slow" --tb=short

# Run CI-safe tests for automated validation
pytest -m "ci_safe" --tb=short
```

### CI/CD Pipeline Integration

#### Pull Request Validation
```bash
# Fast validation for PR checks (< 2 minutes)
pytest -m "fast and (unit or integration)" --tb=short

# Medium validation for comprehensive PR testing (< 5 minutes)  
pytest -m "(fast or medium) and ci_safe" --tb=short
```

#### Main Branch Testing
```bash
# Complete test suite except resource-intensive tests
pytest -m "not (load or real_database)" --tb=short

# Full validation including performance tests
pytest --tb=short
```

#### Release Validation
```bash
# Smoke tests for critical functionality
pytest -m "smoke" --tb=short -v

# Production readiness validation
pytest -m "production" --tb=short -v

# Complete end-to-end validation
pytest -m "e2e" --tb=short -v
```

### Parallel Execution Strategies

#### High Concurrency (Fast Tests)
```bash
# Parallel execution of fast tests (safe for high concurrency)
pytest -m "fast" -n auto --tb=short

# Parallel unit tests with maximum workers
pytest -m "unit and fast" -n 8 --tb=short
```

#### Moderate Concurrency (Medium Tests)
```bash
# Controlled parallel execution of integration tests
pytest -m "medium and integration" -n 4 --dist=worksteal --tb=short

# Resource-aware parallel execution
pytest -m "medium and not database" -n 4 --tb=short
```

#### Sequential Execution (Slow Tests)
```bash  
# Sequential execution of slow tests to avoid resource conflicts
pytest -m "slow" -n 1 --tb=short

# Load testing with dedicated resources
pytest -m "load" -n 1 -v
```

## Marker Combination Examples

### Common Marker Combinations

#### Fast Unit Tests
```python
@pytest.mark.fast
@pytest.mark.unit
def test_email_parsing_basic():
    """Fast, isolated test of email parsing logic."""
```

#### Medium Integration Tests
```python
@pytest.mark.medium
@pytest.mark.integration
@pytest.mark.database
def test_scenario_data_persistence():
    """Integration test with database operations."""
```

#### Slow E2E Tests
```python
@pytest.mark.slow
@pytest.mark.e2e
@pytest.mark.email
@pytest.mark.azure
def test_complete_email_processing_workflow():
    """End-to-end email processing with Azure integration."""
```

#### Edge Case Tests
```python
@pytest.mark.fast
@pytest.mark.edge_case
@pytest.mark.retry
def test_connection_failure_recovery():
    """Test retry logic during connection failures."""
```

### Execution Filtering Examples

#### Selective Testing by Functionality
```bash
# Test only email-related functionality
pytest -m "email" --tb=short

# Test Azure integrations with fast feedback
pytest -m "azure and fast" --tb=short

# Test all security functionality
pytest -m "security" -v
```

#### Performance-Based Selection
```bash
# Development testing (fast feedback)
pytest -m "fast" --tb=short

# Integration testing (moderate time)  
pytest -m "medium" --tb=short

# Performance validation (extended time)
pytest -m "slow or performance" --tb=short -v
```

#### Environment-Based Selection
```bash
# CI/CD safe tests only
pytest -m "ci_safe" --tb=short

# Production environment tests
pytest -m "production" --tb=short

# Tests that require real external services
pytest -m "real_database or azure" --tb=short
```

## Best Practices

### Marker Application Guidelines

1. **Every Test Must Have Performance and Functional Markers**
   - Always apply one performance marker (fast/medium/slow)
   - Always apply one functional marker (unit/integration/edge_case)
   - Apply descriptive markers when relevant

2. **Consistent Classification Logic**
   - Fast: < 5 seconds, no external dependencies
   - Medium: 5-30 seconds, controlled dependencies  
   - Slow: > 30 seconds, external services or heavy processing
   - Unit: Isolated with mocks
   - Integration: Multi-component with controlled environment
   - Edge Case: Error conditions and boundary testing

3. **Meaningful Marker Combinations**
   - Avoid conflicting markers (e.g., `fast` and `slow`)
   - Ensure logical consistency (e.g., `unit` tests should typically be `fast`)
   - Use descriptive markers to enhance filtering capabilities

### Development Workflow Integration

1. **IDE Integration**
   - Configure IDE to run `pytest -m "fast"` for quick validation
   - Use `pytest -m "fast and unit"` for focused unit testing
   - Set up `pytest -m "(fast or medium) and not azure"` for offline development

2. **Pre-commit Hooks**
   - Run `pytest -m "fast and (unit or integration)"` before commits
   - Exclude slow tests from pre-commit validation
   - Use parallel execution for faster feedback

3. **Continuous Integration**
   - Use marker-based test selection for different pipeline stages
   - Run fast tests in PR validation
   - Run comprehensive tests in main branch validation
   - Use slow tests for nightly or release builds

### Maintenance and Validation

1. **Regular Marker Validation**
   ```bash
   # Verify all tests have required markers
   python tests/utils/marker_helpers.py --stats
   
   # Check marker consistency
   python tests/utils/marker_helpers.py --validate tests/
   ```

2. **Performance Verification**
   ```bash
   # Verify fast tests are actually fast
   time pytest -m "fast" --tb=no -q
   
   # Verify medium tests complete reasonably
   time pytest -m "medium" --tb=no -q
   ```

3. **Marker Coverage Analysis**
   ```bash
   # Analyze marker distribution
   pytest --collect-only -q | grep -c "test session starts"
   pytest -m "fast" --collect-only -q | grep -c "collected"
   pytest -m "unit" --collect-only -q | grep -c "collected"
   ```

## Troubleshooting

### Common Issues

#### Tests Not Running with Expected Markers
- Verify marker spelling and case sensitivity
- Check for conflicting marker combinations
- Ensure pytest.ini includes all marker definitions

#### Performance Classification Issues
- Re-evaluate test execution time in actual environment
- Consider external dependencies that may affect timing
- Move tests between performance categories as needed

#### Parallel Execution Problems
- Check for shared resources between tests
- Verify database and file system isolation
- Use sequential execution for tests with resource conflicts

### Debugging Commands

```bash
# List all available markers
pytest --markers

# Show which tests would run for a marker combination
pytest -m "fast and unit" --collect-only

# Verify marker application
python -c "
import subprocess
result = subprocess.run(['pytest', '--collect-only', '-m', 'fast'], capture_output=True, text=True)
print('Fast tests collected:', result.stdout.count('test_'))
"

# Check for tests without required markers
grep -r "def test_" tests/ | grep -v "@pytest.mark" | head -10
```

## Summary

The test marker system enables efficient, selective test execution that supports rapid development, comprehensive validation, and optimized CI/CD pipelines. By following the classification guidelines and execution strategies outlined in this document, teams can maintain high testing standards while optimizing for development velocity and resource utilization.

The systematic marker application ensures that the ~959 test functions in the test suite can be efficiently filtered and executed based on time constraints, functionality focus, and environment requirements.