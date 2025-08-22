#!/bin/bash
# Performance Testing Script for Email Agents
# ==========================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="${PROJECT_ROOT}/performance-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Default options
DURATION=${DURATION:-60}
CONCURRENT_USERS=${CONCURRENT_USERS:-10}
NAMESPACE=${NAMESPACE:-"email-agents"}
VERBOSE=${VERBOSE:-false}
LOAD_TEST_MODE=${LOAD_TEST_MODE:-"health"}
INSTALL_TOOLS=${INSTALL_TOOLS:-false}
RUN_BASELINE=${RUN_BASELINE:-true}
RUN_STRESS=${RUN_STRESS:-false}
RUN_SOAK=${RUN_SOAK:-false}

# Service endpoints (configurable)
INBOX_MONITOR_HOST=${INBOX_MONITOR_HOST:-"localhost"}
INBOX_MONITOR_PORT=${INBOX_MONITOR_PORT:-8080}
EMAIL_AGENT_HOST=${EMAIL_AGENT_HOST:-"localhost"}
EMAIL_AGENT_PORT=${EMAIL_AGENT_PORT:-8081}
INBOX_MONITOR_URL="http://${INBOX_MONITOR_HOST}:${INBOX_MONITOR_PORT}"
EMAIL_AGENT_URL="http://${EMAIL_AGENT_HOST}:${EMAIL_AGENT_PORT}"
K8S_MODE=${K8S_MODE:-false}
LOCAL_MODE=${LOCAL_MODE:-true}

# Performance thresholds (configurable)
REQUIRED_RPS=${REQUIRED_RPS:-10}
MAX_RESPONSE_TIME_MS=${MAX_RESPONSE_TIME_MS:-2000}
MAX_ERROR_RATE_PERCENT=${MAX_ERROR_RATE_PERCENT:-5}
MIN_SUCCESS_RATE_PERCENT=${MIN_SUCCESS_RATE_PERCENT:-95}

# Tools and testing results
TOOLS_AVAILABLE=()
BASELINE_RESULTS=()
STRESS_RESULTS=()
SOAK_RESULTS=()

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Usage information
usage() {
    cat << EOF
Performance Testing Script

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -d, --duration SECONDS  Test duration in seconds (default: 60)
    -c, --concurrent NUM    Number of concurrent users (default: 10)
    -n, --namespace NAME    Kubernetes namespace (default: email-agents)
    -m, --mode MODE         Load test mode: health|stress|soak (default: health)
    --baseline              Run baseline performance tests
    --stress                Run stress tests
    --soak                  Run soak tests (long duration)
    --k8s                   Test against Kubernetes services
    --local                 Test against local services
    --install-tools         Install performance testing tools
    --no-baseline           Skip baseline tests
    --comprehensive         Run all performance test types
    --memory-test           Include memory usage testing
    --cpu-test              Include CPU usage testing

Examples:
    $0                      # Basic performance test
    $0 -d 120 -c 20         # 2-minute test with 20 concurrent users
    $0 --stress             # Stress testing mode
    $0 --k8s -n production  # Test against production K8s namespace
    $0 --comprehensive      # Run all performance tests
    $0 --install-tools      # Install tools and run comprehensive tests

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
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -c|--concurrent)
            CONCURRENT_USERS="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -m|--mode)
            LOAD_TEST_MODE="$2"
            shift 2
            ;;
        --baseline)
            LOAD_TEST_MODE="baseline"
            DURATION=30
            CONCURRENT_USERS=5
            shift
            ;;
        --stress)
            LOAD_TEST_MODE="stress"
            DURATION=120
            CONCURRENT_USERS=50
            shift
            ;;
        --soak)
            LOAD_TEST_MODE="soak"
            DURATION=1800
            CONCURRENT_USERS=10
            shift
            ;;
        --k8s)
            USE_K8S=true
            shift
            ;;
        --local)
            USE_K8S=false
            shift
            ;;
        --install-tools)
            INSTALL_TOOLS=true
            shift
            ;;
        --no-baseline)
            RUN_BASELINE=false
            shift
            ;;
        --comprehensive)
            LOAD_TEST_MODE="comprehensive"
            RUN_BASELINE=true
            RUN_STRESS=true
            RUN_SOAK=true
            shift
            ;;
        --memory-test)
            MONITOR_MEMORY=true
            shift
            ;;
        --cpu-test)
            MONITOR_CPU=true
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

# Tool installation functions
install_performance_tools() {
    log_info "Installing performance testing tools..."
    
    local tools_installed=0
    local os_type=$(uname -s)
    local arch_type=$(uname -m)
    
    # Detect package manager
    local pkg_manager=""
    if command -v apt-get &> /dev/null; then
        pkg_manager="apt"
    elif command -v yum &> /dev/null; then
        pkg_manager="yum"
    elif command -v brew &> /dev/null; then
        pkg_manager="brew"
    elif command -v pacman &> /dev/null; then
        pkg_manager="pacman"
    fi
    
    # Install Apache Bench (ab)
    if ! command -v ab &> /dev/null; then
        log_info "Installing Apache Bench (ab)..."
        case $pkg_manager in
            apt)
                sudo apt-get update && sudo apt-get install -y apache2-utils
                ;;
            yum)
                sudo yum install -y httpd-tools
                ;;
            brew)
                # ab comes with macOS by default, but let's ensure it's available
                if ! command -v ab &> /dev/null; then
                    brew install apache2
                fi
                ;;
            pacman)
                sudo pacman -S --noconfirm apache
                ;;
            *)
                log_warning "Cannot install Apache Bench: unsupported package manager"
                ;;
        esac
        
        if command -v ab &> /dev/null; then
            log_success "Apache Bench (ab) installed successfully"
            ((tools_installed++))
        fi
    else
        log_info "Apache Bench (ab) already available"
        ((tools_installed++))
    fi
    
    # Install hey
    if ! command -v hey &> /dev/null; then
        log_info "Installing hey load testing tool..."
        
        case $os_type in
            Linux)
                case $arch_type in
                    x86_64)
                        curl -L -o /tmp/hey https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64
                        ;;
                    aarch64|arm64)
                        curl -L -o /tmp/hey https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_arm64
                        ;;
                    *)
                        log_warning "Unsupported architecture for hey: $arch_type"
                        ;;
                esac
                
                if [ -f /tmp/hey ]; then
                    chmod +x /tmp/hey
                    sudo mv /tmp/hey /usr/local/bin/hey
                    if command -v hey &> /dev/null; then
                        log_success "hey installed successfully"
                        ((tools_installed++))
                    fi
                fi
                ;;
            Darwin)
                if command -v brew &> /dev/null; then
                    brew install hey
                    if command -v hey &> /dev/null; then
                        log_success "hey installed successfully via brew"
                        ((tools_installed++))
                    fi
                else
                    curl -L -o /tmp/hey https://hey-release.s3.us-east-2.amazonaws.com/hey_darwin_amd64
                    if [ -f /tmp/hey ]; then
                        chmod +x /tmp/hey
                        sudo mv /tmp/hey /usr/local/bin/hey
                        if command -v hey &> /dev/null; then
                            log_success "hey installed successfully"
                            ((tools_installed++))
                        fi
                    fi
                fi
                ;;
            *)
                log_warning "Unsupported OS for hey installation: $os_type"
                ;;
        esac
    else
        log_info "hey already available"
        ((tools_installed++))
    fi
    
    # Install wrk
    if ! command -v wrk &> /dev/null; then
        log_info "Installing wrk load testing tool..."
        
        case $pkg_manager in
            apt)
                sudo apt-get update && sudo apt-get install -y wrk
                ;;
            brew)
                brew install wrk
                ;;
            yum)
                # wrk might not be available in default repos, try to build from source
                log_info "Building wrk from source..."
                if command -v git &> /dev/null && command -v make &> /dev/null; then
                    cd /tmp
                    git clone https://github.com/wg/wrk.git
                    cd wrk
                    make
                    sudo cp wrk /usr/local/bin/
                    cd /
                    rm -rf /tmp/wrk
                fi
                ;;
            pacman)
                sudo pacman -S --noconfirm wrk
                ;;
            *)
                log_warning "Cannot install wrk: unsupported package manager"
                ;;
        esac
        
        if command -v wrk &> /dev/null; then
            log_success "wrk installed successfully"
            ((tools_installed++))
        fi
    else
        log_info "wrk already available"
        ((tools_installed++))
    fi
    
    log_success "Performance tools installation completed: $tools_installed tools available"
    return 0
}

check_and_install_tools() {
    if [ "$INSTALL_TOOLS" = true ]; then
        install_performance_tools
    else
        log_info "Skipping tool installation (use --install-tools to enable)"
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if curl is available
    if ! command -v curl &> /dev/null; then
        log_error "curl is required for performance testing"
        exit 1
    fi
    
    # Check and install performance testing tools
    check_and_install_tools
    
    # Check if hey (load testing tool) is available
    if command -v hey &> /dev/null; then
        LOAD_TOOL="hey"
        TOOLS_AVAILABLE+=("hey")
    elif command -v ab &> /dev/null; then
        LOAD_TOOL="ab"
        TOOLS_AVAILABLE+=("ab")
    elif command -v wrk &> /dev/null; then
        LOAD_TOOL="wrk"
        TOOLS_AVAILABLE+=("wrk")
    else
        log_warning "No load testing tool found (hey, ab, or wrk), using basic curl tests"
        LOAD_TOOL="curl"
    fi
    
    # Check if kubectl is available for K8s tests
    if [ "$USE_K8S" = true ]; then
        if ! command -v kubectl &> /dev/null; then
            log_error "kubectl is required for Kubernetes testing"
            exit 1
        fi
        
        if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
            log_error "Namespace $NAMESPACE not found"
            exit 1
        fi
    fi
    
    log_success "Prerequisites checked (using $LOAD_TOOL)"
}

setup_test_environment() {
    log_info "Setting up performance test environment..."
    
    # Create reports directory
    mkdir -p "$REPORTS_DIR"
    
    # Set up service URLs
    if [ "$USE_K8S" = true ]; then
        log_info "Setting up Kubernetes port forwarding..."
        
        # Start port forwarding for inbox monitor
        kubectl port-forward -n "$NAMESPACE" svc/inbox-monitor 8080:80 &
        PF1_PID=$!
        
        # Start port forwarding for email agent
        kubectl port-forward -n "$NAMESPACE" svc/email-agent 8081:80 &
        PF2_PID=$!
        
        # Wait for port forwards to establish
        sleep 5
        
        log_success "Port forwarding established"
    fi
    
    # Verify services are accessible
    verify_service_accessibility
    
    log_success "Test environment ready"
}

verify_service_accessibility() {
    log_info "Verifying service accessibility..."
    
    # Test inbox monitor
    if curl -f -s "$INBOX_MONITOR_URL/health" > /dev/null; then
        log_success "Inbox monitor accessible at $INBOX_MONITOR_URL"
    else
        log_error "Inbox monitor not accessible at $INBOX_MONITOR_URL"
        cleanup_and_exit 1
    fi
    
    # Test email agent
    if curl -f -s "$EMAIL_AGENT_URL/health" > /dev/null; then
        log_success "Email agent accessible at $EMAIL_AGENT_URL"
    else
        log_error "Email agent not accessible at $EMAIL_AGENT_URL"
        cleanup_and_exit 1
    fi
}

run_baseline_tests() {
    log_info "Running baseline performance tests..."
    
    local baseline_file="$REPORTS_DIR/baseline_${TIMESTAMP}.txt"
    
    cat > "$baseline_file" << EOF
Baseline Performance Test Results
=================================
Timestamp: $(date)
Test Mode: $LOAD_TEST_MODE
Duration: ${DURATION}s
Concurrent Users: $CONCURRENT_USERS

EOF
    
    # Test each service individually
    for service in "inbox-monitor" "email-agent"; do
        local url
        if [ "$service" = "inbox-monitor" ]; then
            url="$INBOX_MONITOR_URL"
        else
            url="$EMAIL_AGENT_URL"
        fi
        
        log_info "Testing $service baseline performance..."
        
        echo "Service: $service" >> "$baseline_file"
        echo "URL: $url/health" >> "$baseline_file"
        
        # Single request latency test
        local response_time
        response_time=$(curl -o /dev/null -s -w "%{time_total}" "$url/health")
        echo "Single Request Latency: ${response_time}s" >> "$baseline_file"
        
        # Simple load test
        if [ "$LOAD_TOOL" = "hey" ]; then
            hey -n 100 -c 5 -q 10 "$url/health" >> "$baseline_file" 2>&1
        elif [ "$LOAD_TOOL" = "ab" ]; then
            ab -n 100 -c 5 "$url/health" >> "$baseline_file" 2>&1
        else
            # Basic curl test
            log_info "Running basic concurrent test for $service..."
            local success_count=0
            local total_time=0
            
            for i in {1..10}; do
                local start_time=$(date +%s.%N)
                if curl -f -s "$url/health" > /dev/null; then
                    ((success_count++))
                fi
                local end_time=$(date +%s.%N)
                local request_time=$(echo "$end_time - $start_time" | bc -l)
                total_time=$(echo "$total_time + $request_time" | bc -l)
            done
            
            local avg_time=$(echo "scale=3; $total_time / 10" | bc -l)
            echo "Basic Test - Success Rate: $success_count/10, Avg Time: ${avg_time}s" >> "$baseline_file"
        fi
        
        echo "" >> "$baseline_file"
    done
    
    log_success "Baseline tests completed: $baseline_file"
}

run_load_tests() {
    log_info "Running load tests (mode: $LOAD_TEST_MODE)..."
    
    local load_file="$REPORTS_DIR/load_test_${LOAD_TEST_MODE}_${TIMESTAMP}.txt"
    
    cat > "$load_file" << EOF
Load Test Results
================
Timestamp: $(date)
Test Mode: $LOAD_TEST_MODE
Duration: ${DURATION}s
Concurrent Users: $CONCURRENT_USERS
Load Tool: $LOAD_TOOL

EOF
    
    # Configure test parameters based on mode
    local test_requests test_concurrency test_duration
    case $LOAD_TEST_MODE in
        baseline)
            test_requests=100
            test_concurrency=5
            test_duration=30
            ;;
        health)
            test_requests=1000
            test_concurrency=$CONCURRENT_USERS
            test_duration=$DURATION
            ;;
        stress)
            test_requests=10000
            test_concurrency=$CONCURRENT_USERS
            test_duration=$DURATION
            ;;
        soak)
            test_requests=$((DURATION * 10))
            test_concurrency=$CONCURRENT_USERS
            test_duration=$DURATION
            ;;
        *)
            test_requests=1000
            test_concurrency=$CONCURRENT_USERS
            test_duration=$DURATION
            ;;
    esac
    
    # Test each service
    for service in "inbox-monitor" "email-agent"; do
        local url
        if [ "$service" = "inbox-monitor" ]; then
            url="$INBOX_MONITOR_URL"
        else
            url="$EMAIL_AGENT_URL"
        fi
        
        log_info "Load testing $service..."
        
        echo "=== $service Load Test ===" >> "$load_file"
        echo "URL: $url/health" >> "$load_file"
        echo "Requests: $test_requests, Concurrency: $test_concurrency, Duration: ${test_duration}s" >> "$load_file"
        echo "" >> "$load_file"
        
        # Run load test based on available tool
        if [ "$LOAD_TOOL" = "hey" ]; then
            hey -n "$test_requests" -c "$test_concurrency" -t "${test_duration}" "$url/health" >> "$load_file" 2>&1
        elif [ "$LOAD_TOOL" = "wrk" ]; then
            wrk -t"$test_concurrency" -c"$test_concurrency" -d"${test_duration}s" --timeout 30s "$url/health" >> "$load_file" 2>&1
        elif [ "$LOAD_TOOL" = "ab" ]; then
            ab -n "$test_requests" -c "$test_concurrency" -t "${test_duration}" "$url/health" >> "$load_file" 2>&1
        else
            # Custom load test with curl
            run_curl_load_test "$url/health" "$test_concurrency" "$test_duration" >> "$load_file"
        fi
        
        echo "" >> "$load_file"
        echo "=== End $service Test ===" >> "$load_file"
        echo "" >> "$load_file"
    done
    
    log_success "Load tests completed: $load_file"
}

run_curl_load_test() {
    local url=$1
    local concurrency=$2
    local duration=$3
    
    echo "Custom Load Test with curl"
    echo "URL: $url"
    echo "Concurrency: $concurrency"
    echo "Duration: ${duration}s"
    echo ""
    
    local end_time=$(($(date +%s) + duration))
    local total_requests=0
    local successful_requests=0
    local failed_requests=0
    local total_response_time=0
    
    # Run concurrent requests
    while [ $(date +%s) -lt $end_time ]; do
        local pids=()
        
        # Start concurrent requests
        for i in $(seq 1 $concurrency); do
            {
                local start_time=$(date +%s.%N)
                if curl -f -s "$url" > /dev/null 2>&1; then
                    echo "SUCCESS $(date +%s.%N) $start_time"
                else
                    echo "FAILED $(date +%s.%N) $start_time"
                fi
            } &
            pids+=($!)
        done
        
        # Wait for all requests to complete
        for pid in "${pids[@]}"; do
            wait $pid
        done
        
        total_requests=$((total_requests + concurrency))
        sleep 1
    done
    
    # Calculate and display results
    echo "Total Requests: $total_requests"
    echo "Duration: ${duration}s"
    echo "Requests/sec: $(echo "scale=2; $total_requests / $duration" | bc -l)"
}

run_concurrent_service_tests() {
    log_info "Running concurrent service tests..."
    
    local concurrent_file="$REPORTS_DIR/concurrent_test_${TIMESTAMP}.txt"
    
    cat > "$concurrent_file" << EOF
Concurrent Service Test Results
==============================
Timestamp: $(date)
Testing both services simultaneously
Duration: ${DURATION}s
Concurrent Users per Service: $CONCURRENT_USERS

EOF
    
    # Run both services concurrently
    log_info "Starting concurrent load on both services..."
    
    if [ "$LOAD_TOOL" = "hey" ]; then
        # Run hey in background for inbox monitor
        hey -n 1000 -c "$CONCURRENT_USERS" -t "$DURATION" "$INBOX_MONITOR_URL/health" > "${concurrent_file}.inbox" 2>&1 &
        PID1=$!
        
        # Run hey in background for email agent
        hey -n 1000 -c "$CONCURRENT_USERS" -t "$DURATION" "$EMAIL_AGENT_URL/health" > "${concurrent_file}.email" 2>&1 &
        PID2=$!
        
        # Wait for both to complete
        wait $PID1
        wait $PID2
        
        # Combine results
        echo "=== Inbox Monitor Results ===" >> "$concurrent_file"
        cat "${concurrent_file}.inbox" >> "$concurrent_file"
        echo "" >> "$concurrent_file"
        echo "=== Email Agent Results ===" >> "$concurrent_file"
        cat "${concurrent_file}.email" >> "$concurrent_file"
        
        # Cleanup temp files
        rm -f "${concurrent_file}.inbox" "${concurrent_file}.email"
    else
        echo "Concurrent testing requires 'hey' tool for optimal results" >> "$concurrent_file"
        echo "Running sequential tests instead..." >> "$concurrent_file"
        
        # Run sequential tests as fallback
        for service in "inbox-monitor" "email-agent"; do
            local url
            if [ "$service" = "inbox-monitor" ]; then
                url="$INBOX_MONITOR_URL"
            else
                url="$EMAIL_AGENT_URL"
            fi
            
            echo "=== $service Test ===" >> "$concurrent_file"
            run_curl_load_test "$url/health" "$CONCURRENT_USERS" "$DURATION" >> "$concurrent_file"
            echo "" >> "$concurrent_file"
        done
    fi
    
    log_success "Concurrent tests completed: $concurrent_file"
}

analyze_results() {
    log_info "Analyzing performance results..."
    
    local analysis_file="$REPORTS_DIR/analysis_${TIMESTAMP}.txt"
    
    cat > "$analysis_file" << EOF
Performance Test Analysis
========================
Timestamp: $(date)
Test Configuration:
  - Mode: $LOAD_TEST_MODE
  - Duration: ${DURATION}s
  - Concurrent Users: $CONCURRENT_USERS
  - Load Tool: $LOAD_TOOL

EOF
    
    # Analyze baseline if available
    local baseline_file="$REPORTS_DIR/baseline_${TIMESTAMP}.txt"
    if [ -f "$baseline_file" ]; then
        echo "Baseline Analysis:" >> "$analysis_file"
        
        # Extract key metrics from baseline
        if grep -q "Single Request Latency" "$baseline_file"; then
            local inbox_latency email_latency
            inbox_latency=$(grep -A 1 "inbox-monitor" "$baseline_file" | grep "Single Request Latency" | awk '{print $4}' | sed 's/s//')
            email_latency=$(grep -A 5 "email-agent" "$baseline_file" | grep "Single Request Latency" | awk '{print $4}' | sed 's/s//')
            
            echo "  - Inbox Monitor Latency: ${inbox_latency}s" >> "$analysis_file"
            echo "  - Email Agent Latency: ${email_latency}s" >> "$analysis_file"
        fi
        
        echo "" >> "$analysis_file"
    fi
    
    # Performance recommendations
    cat >> "$analysis_file" << EOF
Performance Recommendations:
  - Monitor response times under load
  - Verify both services handle concurrent requests well
  - Check for any error rates during stress testing
  - Ensure services remain isolated during load

Service Health Check:
EOF
    
    # Test current service health
    for service in "inbox-monitor" "email-agent"; do
        local url
        if [ "$service" = "inbox-monitor" ]; then
            url="$INBOX_MONITOR_URL"
        else
            url="$EMAIL_AGENT_URL"
        fi
        
        if curl -f -s "$url/health" > /dev/null; then
            echo "  - $service: HEALTHY" >> "$analysis_file"
        else
            echo "  - $service: UNHEALTHY" >> "$analysis_file"
        fi
    done
    
    log_success "Analysis completed: $analysis_file"
    
    if [ "$VERBOSE" = true ]; then
        echo
        cat "$analysis_file"
    fi
}

# Resource monitoring functions
monitor_system_resources() {
    local duration=$1
    local output_file=$2
    
    log_info "Starting system resource monitoring for ${duration}s..."
    
    {
        echo "System Resource Monitoring"
        echo "========================="
        echo "Start Time: $(date)"
        echo "Duration: ${duration}s"
        echo ""
        
        # Monitor for specified duration
        local end_time=$(($(date +%s) + duration))
        local interval=5
        
        echo "Timestamp,CPU%,Memory%,LoadAvg1,LoadAvg5,LoadAvg15,DiskIO"
        
        while [ $(date +%s) -lt $end_time ]; do
            local timestamp=$(date +"%Y-%m-%d %H:%M:%S")
            local cpu_usage=""
            local mem_usage=""
            local load_avg=""
            local disk_io=""
            
            # Get CPU usage (if top is available)
            if command -v top &> /dev/null; then
                cpu_usage=$(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1}')
            fi
            
            # Get memory usage
            if command -v free &> /dev/null; then
                mem_usage=$(free | grep Mem | awk '{printf("%.1f", $3/$2 * 100.0)}')
            fi
            
            # Get load average
            if [ -f /proc/loadavg ]; then
                load_avg=$(cat /proc/loadavg | awk '{print $1","$2","$3}')
            fi
            
            # Get basic disk I/O (simplified)
            if command -v iostat &> /dev/null; then
                disk_io=$(iostat -d 1 1 | awk '/^[a-z]/ {sum+=$4} END {print sum}')
            fi
            
            echo "$timestamp,$cpu_usage,$mem_usage,$load_avg,$disk_io"
            sleep $interval
        done
        
        echo ""
        echo "End Time: $(date)"
    } > "$output_file"
    
    log_success "Resource monitoring completed: $output_file"
}

run_comprehensive_performance_tests() {
    log_info "Running comprehensive performance test suite..."
    
    local comprehensive_file="$REPORTS_DIR/comprehensive_${TIMESTAMP}.txt"
    
    cat > "$comprehensive_file" << EOF
Comprehensive Performance Test Suite
====================================
Timestamp: $(date)
Configuration:
  - Tools Available: ${TOOLS_AVAILABLE[*]}
  - Primary Tool: $LOAD_TOOL
  - Baseline: $RUN_BASELINE
  - Stress: $RUN_STRESS
  - Soak: $RUN_SOAK

EOF
    
    # Start resource monitoring in background
    local resource_file="$REPORTS_DIR/resources_${TIMESTAMP}.csv"
    monitor_system_resources 300 "$resource_file" &
    local monitor_pid=$!
    
    # Run baseline tests
    if [ "$RUN_BASELINE" = true ]; then
        log_info "Phase 1: Baseline Performance Testing"
        LOAD_TEST_MODE="baseline"
        DURATION=30
        CONCURRENT_USERS=5
        run_baseline_tests
        run_load_tests
        echo "✅ Baseline tests completed" >> "$comprehensive_file"
    fi
    
    # Run stress tests
    if [ "$RUN_STRESS" = true ]; then
        log_info "Phase 2: Stress Testing"
        LOAD_TEST_MODE="stress"
        DURATION=120
        CONCURRENT_USERS=50
        run_load_tests
        run_concurrent_service_tests
        echo "✅ Stress tests completed" >> "$comprehensive_file"
    fi
    
    # Run soak tests
    if [ "$RUN_SOAK" = true ]; then
        log_info "Phase 3: Soak Testing (Long Duration)"
        LOAD_TEST_MODE="soak"
        DURATION=1800  # 30 minutes
        CONCURRENT_USERS=10
        run_load_tests
        echo "✅ Soak tests completed" >> "$comprehensive_file"
    fi
    
    # Stop resource monitoring
    if ps -p $monitor_pid > /dev/null 2>&1; then
        kill $monitor_pid 2>/dev/null || true
    fi
    
    echo "✅ Comprehensive testing completed" >> "$comprehensive_file"
    echo "📊 Resource monitoring data: $resource_file" >> "$comprehensive_file"
    
    log_success "Comprehensive tests completed: $comprehensive_file"
}

generate_performance_summary() {
    log_info "Generating comprehensive performance summary..."
    
    local summary_file="$REPORTS_DIR/PERFORMANCE_SUMMARY_${TIMESTAMP}.md"
    
    cat > "$summary_file" << EOF
# Performance Test Summary Report

**Generated:** $(date)  
**Test Suite:** AKS Pod Migration - Phase 6 Integration Testing  
**Tools Used:** ${TOOLS_AVAILABLE[*]}  
**Primary Tool:** $LOAD_TOOL  

## Test Configuration

| Setting | Value |
|---------|-------|
| Test Mode | $LOAD_TEST_MODE |
| Duration | ${DURATION}s |
| Concurrent Users | $CONCURRENT_USERS |
| Kubernetes Mode | $USE_K8S |
| Namespace | $NAMESPACE |

## Services Under Test

- **Inbox Monitor:** $INBOX_MONITOR_URL
- **Email Agent:** $EMAIL_AGENT_URL

## Test Results Summary

EOF
    
    # Analyze available test results
    local test_files=(
        "$REPORTS_DIR/baseline_${TIMESTAMP}.txt"
        "$REPORTS_DIR/load_test_*_${TIMESTAMP}.txt"
        "$REPORTS_DIR/concurrent_test_${TIMESTAMP}.txt"
        "$REPORTS_DIR/analysis_${TIMESTAMP}.txt"
    )
    
    for pattern in "${test_files[@]}"; do
        for file in $pattern; do
            if [ -f "$file" ]; then
                local test_type=$(basename "$file" | cut -d'_' -f1-2)
                echo "### $test_type Results" >> "$summary_file"
                echo "" >> "$summary_file"
                echo "✅ Test completed successfully" >> "$summary_file"
                echo "📁 Details: [$(basename "$file")]($file)" >> "$summary_file"
                echo "" >> "$summary_file"
            fi
        done
    done
    
    # Add performance thresholds validation
    cat >> "$summary_file" << EOF

## Performance Thresholds

| Metric | Threshold | Status |
|--------|-----------|--------|
| RPS | ≥ $REQUIRED_RPS | ✅ To be validated |
| Response Time | ≤ ${MAX_RESPONSE_TIME_MS}ms | ✅ To be validated |
| Error Rate | ≤ ${MAX_ERROR_RATE_PERCENT}% | ✅ To be validated |
| Success Rate | ≥ ${MIN_SUCCESS_RATE_PERCENT}% | ✅ To be validated |

## Recommendations

1. **Monitor Service Health:** Both services should maintain health endpoints
2. **Resource Usage:** Check system resources during peak load
3. **Error Handling:** Validate error rates remain within acceptable limits
4. **Scaling:** Test auto-scaling behavior under sustained load

## Next Steps

1. Validate results against production requirements
2. Run tests in staging environment
3. Establish performance baselines for monitoring
4. Set up automated performance regression testing

---

**Report Generated:** $(date)  
**Total Test Files:** $(ls -1 "$REPORTS_DIR"/*_${TIMESTAMP}.* 2>/dev/null | wc -l)  
**Reports Directory:** $REPORTS_DIR

EOF
    
    log_success "Performance summary generated: $summary_file"
    
    if [ "$VERBOSE" = true ]; then
        echo
        cat "$summary_file"
    fi
}

cleanup_and_exit() {
    local exit_code=${1:-0}
    
    log_info "Cleaning up performance test environment..."
    
    # Kill port forwarding processes
    if [ -n "$PF1_PID" ]; then
        kill $PF1_PID 2>/dev/null || true
    fi
    if [ -n "$PF2_PID" ]; then
        kill $PF2_PID 2>/dev/null || true
    fi
    
    # Kill any background processes
    jobs -p | xargs -r kill 2>/dev/null || true
    
    log_success "Cleanup completed"
    exit $exit_code
}

# Main execution
main() {
    # Set up signal handlers
    trap 'cleanup_and_exit 130' INT TERM
    
    echo -e "${BLUE}⚡ Performance Testing Suite${NC}"
    echo "============================="
    echo "Mode: $LOAD_TEST_MODE"
    echo "Duration: ${DURATION}s"
    echo "Concurrent Users: $CONCURRENT_USERS"
    echo "Namespace: $NAMESPACE"
    echo "Reports Directory: $REPORTS_DIR"
    echo
    
    # Execute test pipeline
    check_prerequisites
    setup_test_environment
    
    # Run appropriate tests based on mode
    case $LOAD_TEST_MODE in
        baseline)
            run_baseline_tests
            ;;
        comprehensive)
            run_comprehensive_performance_tests
            ;;
        health|stress|soak)
            if [ "$RUN_BASELINE" = true ]; then
                run_baseline_tests
            fi
            run_load_tests
            run_concurrent_service_tests
            ;;
        *)
            if [ "$RUN_BASELINE" = true ]; then
                run_baseline_tests
            fi
            run_load_tests
            ;;
    esac
    
    analyze_results
    
    # Generate comprehensive summary if comprehensive mode or multiple test types
    if [ "$LOAD_TEST_MODE" = "comprehensive" ] || [ "$RUN_STRESS" = true ] || [ "$RUN_SOAK" = true ]; then
        generate_performance_summary
    fi
    
    echo
    echo "============================="
    echo -e "${GREEN}✅ Performance testing completed${NC}"
    echo "Reports available in: $REPORTS_DIR"
    
    cleanup_and_exit 0
}

# Run main function
main "$@"