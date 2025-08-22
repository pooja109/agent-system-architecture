#!/bin/bash
# Monitoring Integration Validation Script
# ========================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="${PROJECT_ROOT}/monitoring-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Default options
VALIDATE_PROMETHEUS=${VALIDATE_PROMETHEUS:-true}
VALIDATE_GRAFANA=${VALIDATE_GRAFANA:-true}
VALIDATE_ALERTMANAGER=${VALIDATE_ALERTMANAGER:-true}
VALIDATE_HEALTH_ENDPOINTS=${VALIDATE_HEALTH_ENDPOINTS:-true}
VALIDATE_METRICS=${VALIDATE_METRICS:-true}
VERBOSE=${VERBOSE:-false}

# Service endpoints
PROMETHEUS_URL=${PROMETHEUS_URL:-"http://localhost:9090"}
GRAFANA_URL=${GRAFANA_URL:-"http://localhost:3000"}
ALERTMANAGER_URL=${ALERTMANAGER_URL:-"http://localhost:9093"}
INBOX_MONITOR_URL=${INBOX_MONITOR_URL:-"http://localhost:8080"}
EMAIL_AGENT_URL=${EMAIL_AGENT_URL:-"http://localhost:8081"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Usage information
usage() {
    cat << EOF
Monitoring Integration Validation Script

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    --prometheus URL        Prometheus URL (default: http://localhost:9090)
    --grafana URL           Grafana URL (default: http://localhost:3000)
    --alertmanager URL      AlertManager URL (default: http://localhost:9093)
    --inbox-monitor URL     Inbox Monitor URL (default: http://localhost:8080)
    --email-agent URL       Email Agent URL (default: http://localhost:8081)
    --skip-prometheus       Skip Prometheus validation
    --skip-grafana          Skip Grafana validation
    --skip-alertmanager     Skip AlertManager validation
    --skip-health           Skip health endpoint validation
    --skip-metrics          Skip metrics validation

Examples:
    $0                      # Full monitoring validation
    $0 --verbose            # Verbose monitoring validation
    $0 --skip-grafana       # Skip Grafana validation
    $0 --prometheus http://prometheus.example.com:9090

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
        --prometheus)
            PROMETHEUS_URL="$2"
            shift 2
            ;;
        --grafana)
            GRAFANA_URL="$2"
            shift 2
            ;;
        --alertmanager)
            ALERTMANAGER_URL="$2"
            shift 2
            ;;
        --inbox-monitor)
            INBOX_MONITOR_URL="$2"
            shift 2
            ;;
        --email-agent)
            EMAIL_AGENT_URL="$2"
            shift 2
            ;;
        --skip-prometheus)
            VALIDATE_PROMETHEUS=false
            shift
            ;;
        --skip-grafana)
            VALIDATE_GRAFANA=false
            shift
            ;;
        --skip-alertmanager)
            VALIDATE_ALERTMANAGER=false
            shift
            ;;
        --skip-health)
            VALIDATE_HEALTH_ENDPOINTS=false
            shift
            ;;
        --skip-metrics)
            VALIDATE_METRICS=false
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

check_url_accessible() {
    local url=$1
    local timeout=${2:-10}
    
    if curl -s --max-time "$timeout" --fail "$url" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

validate_health_endpoints() {
    log_info "Validating health endpoints..."
    
    local health_report="$REPORTS_DIR/health_endpoints_${TIMESTAMP}.txt"
    
    cat > "$health_report" << EOF
Health Endpoints Validation Report
=================================
Timestamp: $(date)

EOF
    
    # Test inbox monitor health
    log_info "Testing inbox monitor health endpoint..."
    if check_url_accessible "$INBOX_MONITOR_URL/health"; then
        local response=$(curl -s "$INBOX_MONITOR_URL/health")
        echo "✅ Inbox Monitor Health: ACCESSIBLE" >> "$health_report"
        echo "Response: $response" >> "$health_report"
        log_success "Inbox monitor health endpoint accessible"
    else
        echo "❌ Inbox Monitor Health: INACCESSIBLE" >> "$health_report"
        log_error "Inbox monitor health endpoint not accessible"
    fi
    
    echo "" >> "$health_report"
    
    # Test email agent health
    log_info "Testing email agent health endpoint..."
    if check_url_accessible "$EMAIL_AGENT_URL/health"; then
        local response=$(curl -s "$EMAIL_AGENT_URL/health")
        echo "✅ Email Agent Health: ACCESSIBLE" >> "$health_report"
        echo "Response: $response" >> "$health_report"
        log_success "Email agent health endpoint accessible"
    else
        echo "❌ Email Agent Health: INACCESSIBLE" >> "$health_report"
        log_error "Email agent health endpoint not accessible"
    fi
    
    log_success "Health endpoints validation completed: $health_report"
}

validate_metrics_endpoints() {
    log_info "Validating metrics endpoints..."
    
    local metrics_report="$REPORTS_DIR/metrics_endpoints_${TIMESTAMP}.txt"
    
    cat > "$metrics_report" << EOF
Metrics Endpoints Validation Report
===================================
Timestamp: $(date)

EOF
    
    # Test inbox monitor metrics
    log_info "Testing inbox monitor metrics endpoint..."
    if check_url_accessible "$INBOX_MONITOR_URL/metrics"; then
        local metrics_count=$(curl -s "$INBOX_MONITOR_URL/metrics" | grep -c "^[a-zA-Z]" || echo 0)
        echo "✅ Inbox Monitor Metrics: ACCESSIBLE" >> "$metrics_report"
        echo "Metrics Count: $metrics_count" >> "$metrics_report"
        log_success "Inbox monitor metrics endpoint accessible ($metrics_count metrics)"
    else
        echo "❌ Inbox Monitor Metrics: INACCESSIBLE" >> "$metrics_report"
        log_error "Inbox monitor metrics endpoint not accessible"
    fi
    
    echo "" >> "$metrics_report"
    
    # Test email agent metrics
    log_info "Testing email agent metrics endpoint..."
    if check_url_accessible "$EMAIL_AGENT_URL/metrics"; then
        local metrics_count=$(curl -s "$EMAIL_AGENT_URL/metrics" | grep -c "^[a-zA-Z]" || echo 0)
        echo "✅ Email Agent Metrics: ACCESSIBLE" >> "$metrics_report"
        echo "Metrics Count: $metrics_count" >> "$metrics_report"
        log_success "Email agent metrics endpoint accessible ($metrics_count metrics)"
    else
        echo "❌ Email Agent Metrics: INACCESSIBLE" >> "$metrics_report"
        log_error "Email agent metrics endpoint not accessible"
    fi
    
    log_success "Metrics endpoints validation completed: $metrics_report"
}

validate_prometheus() {
    log_info "Validating Prometheus integration..."
    
    local prometheus_report="$REPORTS_DIR/prometheus_${TIMESTAMP}.txt"
    
    cat > "$prometheus_report" << EOF
Prometheus Integration Validation Report
========================================
Timestamp: $(date)

EOF
    
    # Test Prometheus health
    log_info "Testing Prometheus health..."
    if check_url_accessible "$PROMETHEUS_URL/-/healthy"; then
        echo "✅ Prometheus Health: HEALTHY" >> "$prometheus_report"
        log_success "Prometheus is healthy"
    else
        echo "❌ Prometheus Health: UNHEALTHY" >> "$prometheus_report"
        log_error "Prometheus is not accessible"
        return 1
    fi
    
    # Test basic queries
    log_info "Testing Prometheus queries..."
    local queries=("up" "http_requests_total" "process_cpu_seconds_total")
    
    for query in "${queries[@]}"; do
        local encoded_query=$(printf '%s' "$query" | jq -sRr @uri)
        local response=$(curl -s "$PROMETHEUS_URL/api/v1/query?query=$encoded_query")
        
        if echo "$response" | jq -e '.status == "success"' > /dev/null 2>&1; then
            local result_count=$(echo "$response" | jq '.data.result | length')
            echo "✅ Query '$query': SUCCESS ($result_count results)" >> "$prometheus_report"
            log_success "Query '$query' successful"
        else
            echo "❌ Query '$query': FAILED" >> "$prometheus_report"
            log_error "Query '$query' failed"
        fi
    done
    
    # Test targets discovery
    log_info "Testing target discovery..."
    local targets_response=$(curl -s "$PROMETHEUS_URL/api/v1/targets")
    
    if echo "$targets_response" | jq -e '.status == "success"' > /dev/null 2>&1; then
        local active_targets=$(echo "$targets_response" | jq '.data.activeTargets | length')
        local healthy_targets=$(echo "$targets_response" | jq '[.data.activeTargets[] | select(.health == "up")] | length')
        
        echo "Target Discovery:" >> "$prometheus_report"
        echo "  Active Targets: $active_targets" >> "$prometheus_report"
        echo "  Healthy Targets: $healthy_targets" >> "$prometheus_report"
        
        log_success "Target discovery: $healthy_targets/$active_targets healthy"
    else
        echo "❌ Target Discovery: FAILED" >> "$prometheus_report"
        log_error "Target discovery failed"
    fi
    
    log_success "Prometheus validation completed: $prometheus_report"
}

validate_grafana() {
    log_info "Validating Grafana integration..."
    
    local grafana_report="$REPORTS_DIR/grafana_${TIMESTAMP}.txt"
    
    cat > "$grafana_report" << EOF
Grafana Integration Validation Report
=====================================
Timestamp: $(date)

EOF
    
    # Test Grafana health
    log_info "Testing Grafana health..."
    if check_url_accessible "$GRAFANA_URL/api/health"; then
        local health_response=$(curl -s "$GRAFANA_URL/api/health")
        echo "✅ Grafana Health: HEALTHY" >> "$grafana_report"
        echo "Response: $health_response" >> "$grafana_report"
        log_success "Grafana is healthy"
    else
        echo "❌ Grafana Health: UNHEALTHY" >> "$grafana_report"
        log_error "Grafana is not accessible"
        return 1
    fi
    
    # Validate dashboard configuration
    log_info "Validating dashboard configuration..."
    local dashboard_file="$PROJECT_ROOT/monitoring/health-check-dashboard.json"
    
    if [[ -f "$dashboard_file" ]]; then
        echo "✅ Dashboard Config: EXISTS" >> "$grafana_report"
        
        # Validate JSON structure
        if jq empty "$dashboard_file" 2>/dev/null; then
            echo "✅ Dashboard JSON: VALID" >> "$grafana_report"
            
            # Extract dashboard info
            local title=$(jq -r '.dashboard.title' "$dashboard_file")
            local panel_count=$(jq '.dashboard.panels | length' "$dashboard_file")
            
            echo "Dashboard Title: $title" >> "$grafana_report"
            echo "Panel Count: $panel_count" >> "$grafana_report"
            
            log_success "Dashboard configuration valid ($panel_count panels)"
        else
            echo "❌ Dashboard JSON: INVALID" >> "$grafana_report"
            log_error "Dashboard JSON is invalid"
        fi
    else
        echo "❌ Dashboard Config: MISSING" >> "$grafana_report"
        log_error "Dashboard configuration file not found"
    fi
    
    log_success "Grafana validation completed: $grafana_report"
}

validate_alertmanager() {
    log_info "Validating AlertManager integration..."
    
    local alertmanager_report="$REPORTS_DIR/alertmanager_${TIMESTAMP}.txt"
    
    cat > "$alertmanager_report" << EOF
AlertManager Integration Validation Report
==========================================
Timestamp: $(date)

EOF
    
    # Test AlertManager health
    log_info "Testing AlertManager health..."
    if check_url_accessible "$ALERTMANAGER_URL/api/v1/status"; then
        local status_response=$(curl -s "$ALERTMANAGER_URL/api/v1/status")
        echo "✅ AlertManager Health: HEALTHY" >> "$alertmanager_report"
        echo "Response: $status_response" >> "$alertmanager_report"
        log_success "AlertManager is healthy"
    else
        echo "❌ AlertManager Health: UNHEALTHY" >> "$alertmanager_report"
        log_warning "AlertManager is not accessible (may not be configured)"
    fi
    
    # Test alerts endpoint
    log_info "Testing AlertManager alerts..."
    if check_url_accessible "$ALERTMANAGER_URL/api/v1/alerts"; then
        local alerts_response=$(curl -s "$ALERTMANAGER_URL/api/v1/alerts")
        local alert_count=$(echo "$alerts_response" | jq '. | length' 2>/dev/null || echo "unknown")
        
        echo "✅ AlertManager Alerts: ACCESSIBLE" >> "$alertmanager_report"
        echo "Active Alerts: $alert_count" >> "$alertmanager_report"
        
        log_success "AlertManager alerts accessible ($alert_count active)"
    else
        echo "❌ AlertManager Alerts: INACCESSIBLE" >> "$alertmanager_report"
        log_warning "AlertManager alerts not accessible"
    fi
    
    log_success "AlertManager validation completed: $alertmanager_report"
}

generate_monitoring_summary() {
    log_info "Generating monitoring validation summary..."
    
    local summary_file="$REPORTS_DIR/MONITORING_VALIDATION_SUMMARY_${TIMESTAMP}.md"
    
    cat > "$summary_file" << EOF
# Monitoring Integration Validation Summary

**Generated:** $(date)  
**Test Suite:** AKS Pod Migration - Phase 6 Monitoring Integration  
**Validation Scope:** Complete monitoring stack validation  

## Test Configuration

| Component | URL | Validated |
|-----------|-----|-----------|
| Prometheus | $PROMETHEUS_URL | $VALIDATE_PROMETHEUS |
| Grafana | $GRAFANA_URL | $VALIDATE_GRAFANA |
| AlertManager | $ALERTMANAGER_URL | $VALIDATE_ALERTMANAGER |
| Inbox Monitor | $INBOX_MONITOR_URL | $VALIDATE_HEALTH_ENDPOINTS |
| Email Agent | $EMAIL_AGENT_URL | $VALIDATE_HEALTH_ENDPOINTS |

## Validation Results

EOF
    
    # Analyze validation results
    local total_reports=0
    local successful_reports=0
    
    for report_file in "$REPORTS_DIR"/*_"${TIMESTAMP}".txt; do
        if [[ -f "$report_file" ]]; then
            ((total_reports++))
            local report_name=$(basename "$report_file" | sed "s/_${TIMESTAMP}.txt//")
            
            if grep -q "✅" "$report_file"; then
                ((successful_reports++))
                echo "### $report_name" >> "$summary_file"
                echo "" >> "$summary_file"
                echo "✅ **Status:** PASSED" >> "$summary_file"
                echo "📁 **Details:** [$(basename "$report_file")]($report_file)" >> "$summary_file"
                echo "" >> "$summary_file"
            else
                echo "### $report_name" >> "$summary_file"
                echo "" >> "$summary_file"
                echo "❌ **Status:** FAILED" >> "$summary_file"
                echo "📁 **Details:** [$(basename "$report_file")]($report_file)" >> "$summary_file"
                echo "" >> "$summary_file"
            fi
        fi
    done
    
    # Add summary statistics
    cat >> "$summary_file" << EOF

## Summary Statistics

- **Total Validations:** $total_reports
- **Successful:** $successful_reports
- **Success Rate:** $(( successful_reports * 100 / total_reports ))%

## Recommendations

1. **Monitor Service Health:** Ensure all services maintain healthy status
2. **Metrics Collection:** Verify metrics are being collected consistently
3. **Dashboard Updates:** Keep monitoring dashboards updated with service changes
4. **Alert Tuning:** Review and tune alerting thresholds based on baseline performance
5. **Data Retention:** Ensure monitoring data retention meets operational requirements

## Next Steps

1. Address any failed validations
2. Set up automated monitoring validation in CI/CD pipeline
3. Establish monitoring baseline metrics
4. Configure production alerting rules
5. Test monitoring system backup and recovery procedures

---

**Report Generated:** $(date)  
**Total Validation Files:** $(ls -1 "$REPORTS_DIR"/*_${TIMESTAMP}.* 2>/dev/null | wc -l)  
**Reports Directory:** $REPORTS_DIR

EOF
    
    log_success "Monitoring validation summary generated: $summary_file"
    
    if [ "$VERBOSE" = true ]; then
        echo
        cat "$summary_file"
    fi
}

cleanup_and_exit() {
    local exit_code=${1:-0}
    
    log_info "Monitoring validation completed"
    exit $exit_code
}

# Main execution
main() {
    # Set up signal handlers
    trap 'cleanup_and_exit 130' INT TERM
    
    echo -e "${BLUE}🔍 Monitoring Integration Validation Suite${NC}"
    echo "=============================================="
    echo "Prometheus: $PROMETHEUS_URL"
    echo "Grafana: $GRAFANA_URL"
    echo "AlertManager: $ALERTMANAGER_URL"
    echo "Reports Directory: $REPORTS_DIR"
    echo
    
    # Create reports directory
    mkdir -p "$REPORTS_DIR"
    
    # Execute validation pipeline
    local validation_failed=false
    
    if [ "$VALIDATE_HEALTH_ENDPOINTS" = true ]; then
        validate_health_endpoints || validation_failed=true
    fi
    
    if [ "$VALIDATE_METRICS" = true ]; then
        validate_metrics_endpoints || validation_failed=true
    fi
    
    if [ "$VALIDATE_PROMETHEUS" = true ]; then
        validate_prometheus || validation_failed=true
    fi
    
    if [ "$VALIDATE_GRAFANA" = true ]; then
        validate_grafana || validation_failed=true
    fi
    
    if [ "$VALIDATE_ALERTMANAGER" = true ]; then
        validate_alertmanager || validation_failed=true
    fi
    
    generate_monitoring_summary
    
    echo
    echo "=============================================="
    if [ "$validation_failed" = true ]; then
        echo -e "${YELLOW}⚠️ Monitoring validation completed with warnings${NC}"
        echo "Some validations failed - check reports for details"
        cleanup_and_exit 1
    else
        echo -e "${GREEN}✅ Monitoring validation completed successfully${NC}"
        echo "All monitoring systems validated successfully"
        cleanup_and_exit 0
    fi
}

# Check dependencies
if ! command -v curl &> /dev/null; then
    log_error "curl is required for monitoring validation"
    exit 1
fi

if ! command -v jq &> /dev/null; then
    log_warning "jq not found - some validations may be limited"
fi

# Run main function
main "$@"