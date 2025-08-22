#!/bin/bash
# Integration Test Runner Script
# =============================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TESTS_DIR="${PROJECT_ROOT}/tests/integration"
REPORTS_DIR="${PROJECT_ROOT}/test-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default options
VERBOSE=false
DOCKER_TESTS=false
KUBERNETES_TESTS=false
LIVE_TESTS=false
QUICK_MODE=false
GENERATE_REPORT=true
PARALLEL=false

# Usage information
usage() {
    cat << EOF
Integration Test Runner

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -d, --docker            Include Docker container tests
    -k, --kubernetes        Include Kubernetes tests
    -l, --live              Include live service tests (requires running services)
    -q, --quick             Quick mode (skip slow tests)
    -r, --no-report         Skip test report generation
    -p, --parallel          Run tests in parallel
    --isolation-only        Run only isolation tests
    --container-only        Run only container tests
    --kubernetes-only       Run only Kubernetes tests
    --communication-only    Run only service communication tests
    --scaling-only          Run only scaling and resilience tests

Examples:
    $0                      # Run basic integration tests
    $0 -v -d                # Run with Docker tests and verbose output
    $0 -k -l                # Run Kubernetes and live service tests
    $0 --quick              # Quick test run
    $0 --isolation-only     # Run only isolation tests

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            usage
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -d|--docker)
            DOCKER_TESTS=true
            shift
            ;;
        -k|--kubernetes)
            KUBERNETES_TESTS=true
            shift
            ;;
        -l|--live)
            LIVE_TESTS=true
            shift
            ;;
        -q|--quick)
            QUICK_MODE=true
            shift
            ;;
        -r|--no-report)
            GENERATE_REPORT=false
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        --isolation-only)
            TEST_SUITE="isolation"
            shift
            ;;
        --container-only)
            TEST_SUITE="container"
            shift
            ;;
        --kubernetes-only)
            TEST_SUITE="kubernetes"
            shift
            ;;
        --communication-only)
            TEST_SUITE="communication"
            shift
            ;;
        --scaling-only)
            TEST_SUITE="scaling"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if pytest is available
    if ! command -v pytest &> /dev/null; then
        log_error "pytest is not installed. Install with: pip install pytest"
        exit 1
    fi
    
    # Check if tests directory exists
    if [ ! -d "$TESTS_DIR" ]; then
        log_error "Tests directory not found: $TESTS_DIR"
        exit 1
    fi
    
    # Check Docker availability if Docker tests are requested
    if [ "$DOCKER_TESTS" = true ]; then
        if ! command -v docker &> /dev/null; then
            log_warning "Docker not available, skipping Docker tests"
            DOCKER_TESTS=false
        elif ! docker info &> /dev/null; then
            log_warning "Docker daemon not running, skipping Docker tests"
            DOCKER_TESTS=false
        fi
    fi
    
    # Check kubectl availability if Kubernetes tests are requested
    if [ "$KUBERNETES_TESTS" = true ]; then
        if ! command -v kubectl &> /dev/null; then
            log_warning "kubectl not available, skipping Kubernetes tests"
            KUBERNETES_TESTS=false
        elif ! kubectl cluster-info &> /dev/null; then
            log_warning "Kubernetes cluster not accessible, skipping live Kubernetes tests"
        fi
    fi
    
    log_success "Prerequisites checked"
}

setup_test_environment() {
    log_info "Setting up test environment..."
    
    # Create reports directory
    mkdir -p "$REPORTS_DIR"
    
    # Set environment variables for tests
    export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"
    export TEST_TIMESTAMP="$TIMESTAMP"
    export TEST_REPORTS_DIR="$REPORTS_DIR"
    
    log_success "Test environment ready"
}

build_pytest_args() {
    local pytest_args=()
    
    # Base arguments
    pytest_args+=("$TESTS_DIR")
    
    # Verbosity
    if [ "$VERBOSE" = true ]; then
        pytest_args+=("-v" "--tb=long")
    else
        pytest_args+=("--tb=short")
    fi
    
    # Quick mode
    if [ "$QUICK_MODE" = true ]; then
        pytest_args+=("-m" "not slow")
    fi
    
    # Parallel execution
    if [ "$PARALLEL" = true ]; then
        if command -v pytest-xdist &> /dev/null; then
            pytest_args+=("-n" "auto")
        else
            log_warning "pytest-xdist not available, running tests sequentially"
        fi
    fi
    
    # Test markers based on options
    local markers=()
    
    if [ "$DOCKER_TESTS" = false ]; then
        markers+=("not docker")
    fi
    
    if [ "$KUBERNETES_TESTS" = false ]; then
        markers+=("not kubernetes")
    fi
    
    if [ "$LIVE_TESTS" = false ]; then
        markers+=("not live")
    fi
    
    # Combine markers
    if [ ${#markers[@]} -gt 0 ]; then
        local marker_expr
        marker_expr=$(IFS=" and "; echo "${markers[*]}")
        pytest_args+=("-m" "$marker_expr")
    fi
    
    # Specific test suite
    if [ -n "$TEST_SUITE" ]; then
        case $TEST_SUITE in
            isolation)
                pytest_args=("$TESTS_DIR/test_isolation_complete.py" "${pytest_args[@]:1}")
                ;;
            container)
                pytest_args=("$TESTS_DIR/test_container_deployment.py" "${pytest_args[@]:1}")
                ;;
            kubernetes)
                pytest_args=("$TESTS_DIR/test_kubernetes_deployment.py" "${pytest_args[@]:1}")
                ;;
            communication)
                pytest_args=("$TESTS_DIR/test_service_communication.py" "${pytest_args[@]:1}")
                ;;
            scaling)
                pytest_args=("$TESTS_DIR/test_scaling_resilience.py" "${pytest_args[@]:1}")
                ;;
        esac
    fi
    
    # Report generation
    if [ "$GENERATE_REPORT" = true ]; then
        pytest_args+=("--html=${REPORTS_DIR}/integration_test_report_${TIMESTAMP}.html" "--self-contained-html")
        pytest_args+=("--junit-xml=${REPORTS_DIR}/integration_test_results_${TIMESTAMP}.xml")
    fi
    
    echo "${pytest_args[@]}"
}

run_pre_test_checks() {
    log_info "Running pre-test checks..."
    
    # Check if services are running (for live tests)
    if [ "$LIVE_TESTS" = true ]; then
        local services_running=0
        
        # Check inbox monitor
        if curl -f -s http://localhost:8080/health > /dev/null 2>&1; then
            log_success "Inbox monitor service is running"
            ((services_running++))
        else
            log_warning "Inbox monitor service not running on port 8080"
        fi
        
        # Check email agent
        if curl -f -s http://localhost:8081/health > /dev/null 2>&1; then
            log_success "Email agent service is running"
            ((services_running++))
        else
            log_warning "Email agent service not running on port 8081"
        fi
        
        if [ $services_running -eq 0 ]; then
            log_warning "No services running, some live tests may be skipped"
        fi
    fi
    
    # Test Docker images (for Docker tests)
    if [ "$DOCKER_TESTS" = true ]; then
        local images_available=0
        
        if docker image inspect inbox-monitor:latest > /dev/null 2>&1; then
            log_success "Docker image inbox-monitor:latest found"
            ((images_available++))
        else
            log_warning "Docker image inbox-monitor:latest not found"
        fi
        
        if docker image inspect email-agent:latest > /dev/null 2>&1; then
            log_success "Docker image email-agent:latest found"
            ((images_available++))
        else
            log_warning "Docker image email-agent:latest not found"
        fi
        
        if [ $images_available -eq 0 ]; then
            log_warning "No Docker images found, container tests may be skipped"
        fi
    fi
    
    log_success "Pre-test checks completed"
}

run_tests() {
    log_info "Running integration tests..."
    
    local pytest_args
    pytest_args=$(build_pytest_args)
    
    log_info "Test command: pytest $pytest_args"
    
    # Run the tests
    local exit_code=0
    if [ "$VERBOSE" = true ]; then
        echo "Running: pytest $pytest_args"
    fi
    
    # Execute pytest with proper error handling
    if ! pytest $pytest_args; then
        exit_code=$?
        log_error "Some tests failed (exit code: $exit_code)"
    else
        log_success "All tests passed!"
    fi
    
    return $exit_code
}

generate_summary() {
    log_info "Generating test summary..."
    
    local summary_file="${REPORTS_DIR}/test_summary_${TIMESTAMP}.txt"
    
    cat > "$summary_file" << EOF
Integration Test Summary
========================

Timestamp: $(date)
Test Configuration:
  - Verbose: $VERBOSE
  - Docker Tests: $DOCKER_TESTS
  - Kubernetes Tests: $KUBERNETES_TESTS
  - Live Tests: $LIVE_TESTS
  - Quick Mode: $QUICK_MODE
  - Parallel: $PARALLEL
  - Test Suite: ${TEST_SUITE:-"all"}

Test Results:
EOF
    
    # Add test results if available
    if [ -f "${REPORTS_DIR}/integration_test_results_${TIMESTAMP}.xml" ]; then
        if command -v xmllint &> /dev/null; then
            local total_tests passed_tests failed_tests
            total_tests=$(xmllint --xpath "count(//testcase)" "${REPORTS_DIR}/integration_test_results_${TIMESTAMP}.xml" 2>/dev/null || echo "N/A")
            failed_tests=$(xmllint --xpath "count(//testcase[failure or error])" "${REPORTS_DIR}/integration_test_results_${TIMESTAMP}.xml" 2>/dev/null || echo "N/A")
            passed_tests=$((total_tests - failed_tests))
            
            cat >> "$summary_file" << EOF
  - Total Tests: $total_tests
  - Passed: $passed_tests
  - Failed: $failed_tests
EOF
        fi
    fi
    
    cat >> "$summary_file" << EOF

Reports Generated:
  - Summary: $summary_file
EOF
    
    if [ "$GENERATE_REPORT" = true ]; then
        cat >> "$summary_file" << EOF
  - HTML Report: ${REPORTS_DIR}/integration_test_report_${TIMESTAMP}.html
  - JUnit XML: ${REPORTS_DIR}/integration_test_results_${TIMESTAMP}.xml
EOF
    fi
    
    log_success "Summary generated: $summary_file"
    
    # Display summary
    if [ "$VERBOSE" = true ]; then
        echo
        cat "$summary_file"
    fi
}

cleanup() {
    log_info "Cleaning up test environment..."
    
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    
    # Clean up any test containers
    if [ "$DOCKER_TESTS" = true ] && command -v docker &> /dev/null; then
        local test_containers
        test_containers=$(docker ps -q --filter "name=test-" 2>/dev/null || true)
        if [ -n "$test_containers" ]; then
            log_info "Cleaning up test containers..."
            docker stop $test_containers 2>/dev/null || true
        fi
    fi
    
    log_success "Cleanup completed"
}

# Main execution
main() {
    # Set up signal handlers
    trap cleanup EXIT
    trap 'log_error "Script interrupted"; exit 130' INT TERM
    
    echo -e "${BLUE}🧪 Integration Test Runner${NC}"
    echo "=============================="
    echo "Timestamp: $(date)"
    echo "Project Root: $PROJECT_ROOT"
    echo "Tests Directory: $TESTS_DIR"
    echo "Reports Directory: $REPORTS_DIR"
    echo
    
    # Execute test pipeline
    check_prerequisites
    setup_test_environment
    run_pre_test_checks
    
    local exit_code=0
    if run_tests; then
        log_success "Integration tests completed successfully!"
    else
        exit_code=$?
        log_error "Integration tests completed with failures"
    fi
    
    if [ "$GENERATE_REPORT" = true ]; then
        generate_summary
    fi
    
    echo
    echo "=============================="
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Test run completed successfully${NC}"
    else
        echo -e "${RED}❌ Test run completed with failures${NC}"
    fi
    echo "Reports available in: $REPORTS_DIR"
    
    exit $exit_code
}

# Run main function
main "$@"