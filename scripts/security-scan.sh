#!/bin/bash
# Security Scanning Script for Email Agents
# =========================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPORTS_DIR="${PROJECT_ROOT}/security-reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SECURITY_DB="${PROJECT_ROOT}/.security_cache"

# Default options
NAMESPACE=${NAMESPACE:-"email-agents"}
VERBOSE=${VERBOSE:-false}
SCAN_CONTAINERS=${SCAN_CONTAINERS:-true}
SCAN_KUBERNETES=${SCAN_KUBERNETES:-true}
SCAN_NETWORK=${SCAN_NETWORK:-true}
SCAN_SECRETS=${SCAN_SECRETS:-true}
SCAN_CODE=${SCAN_CODE:-true}
INSTALL_TOOLS=${INSTALL_TOOLS:-false}

# Security tool detection and installation
TOOLS_NEEDED=("trivy" "kubesec" "hadolint" "bandit" "semgrep")
TOOLS_AVAILABLE=()
CRITICAL_FINDINGS=0
HIGH_FINDINGS=0
MEDIUM_FINDINGS=0
LOW_FINDINGS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Usage information
usage() {
    cat << EOF
Security Scanning Script

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -v, --verbose           Enable verbose output
    -n, --namespace NAME    Kubernetes namespace (default: email-agents)
    --containers            Scan container images (default: enabled)
    --no-containers         Skip container image scanning
    --kubernetes            Scan Kubernetes manifests (default: enabled)
    --no-kubernetes         Skip Kubernetes manifest scanning
    --network               Scan network security (default: enabled)
    --no-network            Skip network security scanning
    --baseline              Run baseline security scan
    --comprehensive         Run comprehensive security scan
    --install-tools         Install missing security tools
    --secrets               Scan for secrets and credentials (default: enabled)
    --no-secrets            Skip secrets scanning
    --code                  Scan source code for vulnerabilities (default: enabled)
    --no-code               Skip code vulnerability scanning

Examples:
    $0                      # Run all security scans
    $0 --baseline           # Run baseline security checks
    $0 --no-containers      # Skip container scanning
    $0 --comprehensive      # Run comprehensive security assessment
    $0 --install-tools      # Install security tools and run scans
    $0 -n production        # Scan production namespace

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
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --containers)
            SCAN_CONTAINERS=true
            shift
            ;;
        --no-containers)
            SCAN_CONTAINERS=false
            shift
            ;;
        --kubernetes)
            SCAN_KUBERNETES=true
            shift
            ;;
        --no-kubernetes)
            SCAN_KUBERNETES=false
            shift
            ;;
        --network)
            SCAN_NETWORK=true
            shift
            ;;
        --no-network)
            SCAN_NETWORK=false
            shift
            ;;
        --baseline)
            SCAN_MODE="baseline"
            shift
            ;;
        --comprehensive)
            SCAN_MODE="comprehensive"
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
    log_info "Checking security scanning prerequisites..."
    
    # Create reports directory
    mkdir -p "$REPORTS_DIR"
    
    # Check if Docker is available for container scanning
    if [ "$SCAN_CONTAINERS" = true ]; then
        if ! command -v docker &> /dev/null; then
            log_warning "Docker not available, skipping container image scanning"
            SCAN_CONTAINERS=false
        fi
    fi
    
    # Check if kubectl is available for Kubernetes scanning
    if [ "$SCAN_KUBERNETES" = true ]; then
        if ! command -v kubectl &> /dev/null; then
            log_warning "kubectl not available, skipping Kubernetes scanning"
            SCAN_KUBERNETES=false
        fi
    fi
    
    # Check for security scanning tools
    SECURITY_TOOLS=()
    
    if command -v hadolint &> /dev/null; then
        SECURITY_TOOLS+=("hadolint")
    fi
    
    if command -v trivy &> /dev/null; then
        SECURITY_TOOLS+=("trivy")
    fi
    
    if command -v kube-score &> /dev/null; then
        SECURITY_TOOLS+=("kube-score")
    fi
    
    if command -v nmap &> /dev/null; then
        SECURITY_TOOLS+=("nmap")
    fi
    
    if [ ${#SECURITY_TOOLS[@]} -eq 0 ]; then
        log_warning "No advanced security tools found. Using basic security checks."
        log_info "Consider installing: hadolint, trivy, kube-score, nmap for comprehensive scanning"
    else
        log_success "Security tools available: ${SECURITY_TOOLS[*]}"
    fi
}

scan_dockerfile_security() {
    log_info "Scanning Dockerfile security..."
    
    local dockerfile_report="$REPORTS_DIR/dockerfile_security_${TIMESTAMP}.txt"
    
    cat > "$dockerfile_report" << EOF
Dockerfile Security Scan Results
===============================
Timestamp: $(date)

EOF
    
    # Find Dockerfiles
    local dockerfiles=()
    dockerfiles+=($(find "$PROJECT_ROOT/agents" -name "Dockerfile" 2>/dev/null || true))
    
    if [ ${#dockerfiles[@]} -eq 0 ]; then
        echo "No Dockerfiles found to scan" >> "$dockerfile_report"
        log_warning "No Dockerfiles found"
        return
    fi
    
    for dockerfile in "${dockerfiles[@]}"; do
        echo "=== Scanning: $dockerfile ===" >> "$dockerfile_report"
        
        # Basic Dockerfile security checks
        echo "Basic Security Checks:" >> "$dockerfile_report"
        
        # Check for USER instruction
        if grep -q "^USER " "$dockerfile"; then
            echo "✅ Non-root user specified" >> "$dockerfile_report"
        else
            echo "⚠️  No USER instruction found - container may run as root" >> "$dockerfile_report"
        fi
        
        # Check for HEALTHCHECK
        if grep -q "^HEALTHCHECK " "$dockerfile"; then
            echo "✅ Health check defined" >> "$dockerfile_report"
        else
            echo "⚠️  No HEALTHCHECK instruction found" >> "$dockerfile_report"
        fi
        
        # Check for secrets in Dockerfile
        if grep -i -E "(password|secret|key|token)" "$dockerfile"; then
            echo "⚠️  Potential secrets found in Dockerfile" >> "$dockerfile_report"
        else
            echo "✅ No obvious secrets in Dockerfile" >> "$dockerfile_report"
        fi
        
        # Run hadolint if available
        if command -v hadolint &> /dev/null; then
            echo "" >> "$dockerfile_report"
            echo "Hadolint Analysis:" >> "$dockerfile_report"
            hadolint "$dockerfile" >> "$dockerfile_report" 2>&1 || true
        fi
        
        echo "" >> "$dockerfile_report"
    done
    
    log_success "Dockerfile security scan completed: $dockerfile_report"
}

scan_container_images() {
    if [ "$SCAN_CONTAINERS" != true ]; then
        log_info "Skipping container image scanning"
        return
    fi
    
    log_info "Scanning container images for vulnerabilities..."
    
    local container_report="$REPORTS_DIR/container_security_${TIMESTAMP}.txt"
    
    cat > "$container_report" << EOF
Container Image Security Scan Results
====================================
Timestamp: $(date)

EOF
    
    # Define images to scan
    local images=("inbox-monitor:latest" "email-agent:latest")
    
    for image in "${images[@]}"; do
        echo "=== Scanning Image: $image ===" >> "$container_report"
        
        # Check if image exists
        if ! docker image inspect "$image" > /dev/null 2>&1; then
            echo "❌ Image not found: $image" >> "$container_report"
            echo "" >> "$container_report"
            continue
        fi
        
        # Basic image information
        echo "Image Information:" >> "$container_report"
        docker image inspect "$image" --format "Created: {{.Created}}" >> "$container_report"
        docker image inspect "$image" --format "Architecture: {{.Architecture}}" >> "$container_report"
        docker image inspect "$image" --format "OS: {{.Os}}" >> "$container_report"
        
        # Check image size
        local image_size
        image_size=$(docker image inspect "$image" --format "{{.Size}}" | awk '{print int($1/1024/1024) " MB"}')
        echo "Size: $image_size" >> "$container_report"
        
        # Run Trivy scan if available
        if command -v trivy &> /dev/null; then
            echo "" >> "$container_report"
            echo "Trivy Vulnerability Scan:" >> "$container_report"
            trivy image --severity HIGH,CRITICAL --no-progress "$image" >> "$container_report" 2>&1 || true
        fi
        
        # Basic security checks
        echo "" >> "$container_report"
        echo "Security Configuration:" >> "$container_report"
        
        # Check if running as root
        local user_config
        user_config=$(docker image inspect "$image" --format "{{.Config.User}}")
        if [ -z "$user_config" ]; then
            echo "⚠️  No USER configuration - may run as root" >> "$container_report"
        else
            echo "✅ User configured: $user_config" >> "$container_report"
        fi
        
        # Check exposed ports
        local exposed_ports
        exposed_ports=$(docker image inspect "$image" --format "{{range \$port, \$config := .Config.ExposedPorts}}{{.}}{{end}}")
        if [ -n "$exposed_ports" ]; then
            echo "Exposed Ports: $exposed_ports" >> "$container_report"
        fi
        
        echo "" >> "$container_report"
    done
    
    log_success "Container image security scan completed: $container_report"
}

scan_kubernetes_security() {
    if [ "$SCAN_KUBERNETES" != true ]; then
        log_info "Skipping Kubernetes security scanning"
        return
    fi
    
    log_info "Scanning Kubernetes manifests for security issues..."
    
    local k8s_report="$REPORTS_DIR/kubernetes_security_${TIMESTAMP}.txt"
    
    cat > "$k8s_report" << EOF
Kubernetes Security Scan Results
===============================
Timestamp: $(date)
Namespace: $NAMESPACE

EOF
    
    # Check if namespace exists
    if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
        echo "❌ Namespace $NAMESPACE not found" >> "$k8s_report"
        log_error "Namespace $NAMESPACE not found"
        return
    fi
    
    # Scan deployments
    echo "=== Deployment Security Analysis ===" >> "$k8s_report"
    
    local deployments
    deployments=$(kubectl get deployments -n "$NAMESPACE" -o name 2>/dev/null || true)
    
    if [ -z "$deployments" ]; then
        echo "No deployments found in namespace $NAMESPACE" >> "$k8s_report"
    else
        for deployment in $deployments; do
            local deployment_name
            deployment_name=$(echo "$deployment" | cut -d'/' -f2)
            
            echo "--- Deployment: $deployment_name ---" >> "$k8s_report"
            
            # Check security context
            local security_context
            security_context=$(kubectl get "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.securityContext}' 2>/dev/null || echo "null")
            
            if [ "$security_context" = "null" ] || [ -z "$security_context" ]; then
                echo "⚠️  No security context defined" >> "$k8s_report"
            else
                echo "✅ Security context configured" >> "$k8s_report"
            fi
            
            # Check for privileged containers
            local privileged
            privileged=$(kubectl get "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[*].securityContext.privileged}' 2>/dev/null || echo "")
            
            if [ "$privileged" = "true" ]; then
                echo "❌ Privileged container detected" >> "$k8s_report"
            else
                echo "✅ No privileged containers" >> "$k8s_report"
            fi
            
            # Check resource limits
            local cpu_limits memory_limits
            cpu_limits=$(kubectl get "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[*].resources.limits.cpu}' 2>/dev/null || echo "")
            memory_limits=$(kubectl get "$deployment" -n "$NAMESPACE" -o jsonpath='{.spec.template.spec.containers[*].resources.limits.memory}' 2>/dev/null || echo "")
            
            if [ -n "$cpu_limits" ]; then
                echo "✅ CPU limits configured: $cpu_limits" >> "$k8s_report"
            else
                echo "⚠️  No CPU limits configured" >> "$k8s_report"
            fi
            
            if [ -n "$memory_limits" ]; then
                echo "✅ Memory limits configured: $memory_limits" >> "$k8s_report"
            else
                echo "⚠️  No memory limits configured" >> "$k8s_report"
            fi
            
            # Run kube-score if available
            if command -v kube-score &> /dev/null; then
                echo "" >> "$k8s_report"
                echo "Kube-score Analysis:" >> "$k8s_report"
                kubectl get "$deployment" -n "$NAMESPACE" -o yaml | kube-score score - >> "$k8s_report" 2>&1 || true
            fi
            
            echo "" >> "$k8s_report"
        done
    fi
    
    # Check network policies
    echo "=== Network Security Analysis ===" >> "$k8s_report"
    
    local network_policies
    network_policies=$(kubectl get networkpolicies -n "$NAMESPACE" -o name 2>/dev/null || true)
    
    if [ -z "$network_policies" ]; then
        echo "⚠️  No network policies found - traffic not restricted" >> "$k8s_report"
    else
        echo "✅ Network policies configured:" >> "$k8s_report"
        for policy in $network_policies; do
            local policy_name
            policy_name=$(echo "$policy" | cut -d'/' -f2)
            echo "  - $policy_name" >> "$k8s_report"
        done
    fi
    
    # Check service accounts
    echo "" >> "$k8s_report"
    echo "=== Service Account Security ===" >> "$k8s_report"
    
    local service_accounts
    service_accounts=$(kubectl get serviceaccounts -n "$NAMESPACE" -o name 2>/dev/null || true)
    
    for sa in $service_accounts; do
        local sa_name
        sa_name=$(echo "$sa" | cut -d'/' -f2)
        
        if [ "$sa_name" != "default" ]; then
            echo "Service Account: $sa_name" >> "$k8s_report"
            
            # Check for custom service accounts
            echo "✅ Custom service account in use" >> "$k8s_report"
        fi
    done
    
    # Check for secrets
    echo "" >> "$k8s_report"
    echo "=== Secrets Management ===" >> "$k8s_report"
    
    local secrets
    secrets=$(kubectl get secrets -n "$NAMESPACE" -o name 2>/dev/null | grep -v "default-token" || true)
    
    if [ -z "$secrets" ]; then
        echo "⚠️  No application secrets found" >> "$k8s_report"
    else
        echo "✅ Application secrets configured:" >> "$k8s_report"
        for secret in $secrets; do
            local secret_name
            secret_name=$(echo "$secret" | cut -d'/' -f2)
            echo "  - $secret_name" >> "$k8s_report"
        done
    fi
    
    log_success "Kubernetes security scan completed: $k8s_report"
}

scan_network_security() {
    if [ "$SCAN_NETWORK" != true ]; then
        log_info "Skipping network security scanning"
        return
    fi
    
    log_info "Scanning network security..."
    
    local network_report="$REPORTS_DIR/network_security_${TIMESTAMP}.txt"
    
    cat > "$network_report" << EOF
Network Security Scan Results
============================
Timestamp: $(date)

EOF
    
    # Test service endpoints
    echo "=== Service Endpoint Security ===" >> "$network_report"
    
    local services=("localhost:8080" "localhost:8081")
    
    for service in "${services[@]}"; do
        local host port
        host=$(echo "$service" | cut -d':' -f1)
        port=$(echo "$service" | cut -d':' -f2)
        
        echo "--- Service: $service ---" >> "$network_report"
        
        # Check if service is accessible
        if curl -f -s "http://$service/health" > /dev/null 2>&1; then
            echo "✅ Service accessible on $service" >> "$network_report"
            
            # Check response headers for security
            echo "Security Headers:" >> "$network_report"
            local headers
            headers=$(curl -s -I "http://$service/health" 2>/dev/null || echo "")
            
            if echo "$headers" | grep -qi "x-frame-options"; then
                echo "✅ X-Frame-Options header present" >> "$network_report"
            else
                echo "⚠️  X-Frame-Options header missing" >> "$network_report"
            fi
            
            if echo "$headers" | grep -qi "x-content-type-options"; then
                echo "✅ X-Content-Type-Options header present" >> "$network_report"
            else
                echo "⚠️  X-Content-Type-Options header missing" >> "$network_report"
            fi
            
            if echo "$headers" | grep -qi "strict-transport-security"; then
                echo "✅ HSTS header present" >> "$network_report"
            else
                echo "⚠️  HSTS header missing" >> "$network_report"
            fi
            
        else
            echo "❌ Service not accessible on $service" >> "$network_report"
        fi
        
        # Run nmap scan if available
        if command -v nmap &> /dev/null; then
            echo "" >> "$network_report"
            echo "Port Scan Results:" >> "$network_report"
            nmap -p "$port" "$host" >> "$network_report" 2>&1 || true
        fi
        
        echo "" >> "$network_report"
    done
    
    # Check for open ports
    echo "=== Port Security Analysis ===" >> "$network_report"
    
    if command -v netstat &> /dev/null; then
        echo "Listening Ports:" >> "$network_report"
        netstat -tlnp 2>/dev/null | grep -E ":808[01] " >> "$network_report" || echo "No services listening on target ports" >> "$network_report"
    elif command -v ss &> /dev/null; then
        echo "Listening Ports:" >> "$network_report"
        ss -tlnp 2>/dev/null | grep -E ":808[01] " >> "$network_report" || echo "No services listening on target ports" >> "$network_report"
    fi
    
    log_success "Network security scan completed: $network_report"
}

scan_configuration_security() {
    log_info "Scanning configuration security..."
    
    local config_report="$REPORTS_DIR/configuration_security_${TIMESTAMP}.txt"
    
    cat > "$config_report" << EOF
Configuration Security Scan Results
==================================
Timestamp: $(date)

EOF
    
    # Check environment files
    echo "=== Environment Configuration Security ===" >> "$config_report"
    
    local env_files=()
    env_files+=($(find "$PROJECT_ROOT/agents" -name ".env*" -o -name "*.env" 2>/dev/null || true))
    
    for env_file in "${env_files[@]}"; do
        if [ -f "$env_file" ]; then
            echo "--- File: $env_file ---" >> "$config_report"
            
            # Check file permissions
            local permissions
            permissions=$(stat -c "%a" "$env_file" 2>/dev/null || stat -f "%A" "$env_file" 2>/dev/null || echo "unknown")
            echo "File permissions: $permissions" >> "$config_report"
            
            if [ "$permissions" != "600" ] && [ "$permissions" != "640" ]; then
                echo "⚠️  File permissions may be too permissive" >> "$config_report"
            else
                echo "✅ File permissions appropriate" >> "$config_report"
            fi
            
            # Check for hardcoded secrets (without exposing them)
            if grep -qi "password\|secret\|key\|token" "$env_file"; then
                echo "⚠️  Potential secrets detected in file" >> "$config_report"
            else
                echo "✅ No obvious secrets in file" >> "$config_report"
            fi
            
            echo "" >> "$config_report"
        fi
    done
    
    # Check Kubernetes ConfigMaps and Secrets
    if [ "$SCAN_KUBERNETES" = true ] && kubectl get namespace "$NAMESPACE" &> /dev/null; then
        echo "=== Kubernetes Configuration Security ===" >> "$config_report"
        
        # Check ConfigMaps
        local configmaps
        configmaps=$(kubectl get configmaps -n "$NAMESPACE" -o name 2>/dev/null || true)
        
        for cm in $configmaps; do
            local cm_name
            cm_name=$(echo "$cm" | cut -d'/' -f2)
            
            if [ "$cm_name" != "kube-root-ca.crt" ]; then
                echo "ConfigMap: $cm_name" >> "$config_report"
                
                # Check for potential secrets in ConfigMaps
                local cm_data
                cm_data=$(kubectl get "$cm" -n "$NAMESPACE" -o jsonpath='{.data}' 2>/dev/null || echo "{}")
                
                if echo "$cm_data" | grep -qi "password\|secret\|key\|token"; then
                    echo "⚠️  Potential secrets in ConfigMap" >> "$config_report"
                else
                    echo "✅ No obvious secrets in ConfigMap" >> "$config_report"
                fi
            fi
        done
    fi
    
    log_success "Configuration security scan completed: $config_report"
}

generate_security_summary() {
    log_info "Generating security summary..."
    
    local summary_file="$REPORTS_DIR/security_summary_${TIMESTAMP}.txt"
    
    cat > "$summary_file" << EOF
Security Scan Summary
====================
Timestamp: $(date)
Scan Configuration:
  - Containers: $SCAN_CONTAINERS
  - Kubernetes: $SCAN_KUBERNETES
  - Network: $SCAN_NETWORK
  - Namespace: $NAMESPACE

Reports Generated:
EOF
    
    # List all generated reports
    for report in "$REPORTS_DIR"/*_"${TIMESTAMP}".txt; do
        if [ -f "$report" ]; then
            echo "  - $(basename "$report")" >> "$summary_file"
        fi
    done
    
    cat >> "$summary_file" << EOF

Security Recommendations:
  1. Review all ⚠️  warnings in the detailed reports
  2. Fix any ❌ critical issues found
  3. Implement missing security headers for web services
  4. Ensure proper file permissions on configuration files
  5. Use Kubernetes network policies to restrict traffic
  6. Regularly update container images to patch vulnerabilities
  7. Follow principle of least privilege for service accounts
  8. Monitor for suspicious network activity

Next Steps:
  1. Address critical and high-severity findings
  2. Implement automated security scanning in CI/CD
  3. Set up monitoring for security events
  4. Regular security reviews and updates

EOF
    
    log_success "Security summary generated: $summary_file"
    
    if [ "$VERBOSE" = true ]; then
        echo
        cat "$summary_file"
    fi
}

# Main execution
main() {
    echo -e "${BLUE}🔒 Security Scanning Suite${NC}"
    echo "=========================="
    echo "Namespace: $NAMESPACE"
    echo "Container Scanning: $SCAN_CONTAINERS"
    echo "Kubernetes Scanning: $SCAN_KUBERNETES"
    echo "Network Scanning: $SCAN_NETWORK"
    echo "Reports Directory: $REPORTS_DIR"
    echo
    
    # Execute security scanning pipeline
    check_prerequisites
    
    # Run scans based on configuration
    scan_dockerfile_security
    
    if [ "$SCAN_CONTAINERS" = true ]; then
        scan_container_images
    fi
    
    if [ "$SCAN_KUBERNETES" = true ]; then
        scan_kubernetes_security
    fi
    
    if [ "$SCAN_NETWORK" = true ]; then
        scan_network_security
    fi
    
    scan_configuration_security
    generate_security_summary
    
    echo
    echo "=========================="
    echo -e "${GREEN}✅ Security scanning completed${NC}"
    echo "Reports available in: $REPORTS_DIR"
    echo "Review the security summary and address any critical findings."
}

# Enhanced security scanning functions for comprehensive analysis

# Security tool installation
install_security_tools() {
    log_info "Installing comprehensive security scanning tools..."
    
    # Create tools directory
    mkdir -p "${PROJECT_ROOT}/.security_tools"
    
    # Install Trivy for container scanning
    if ! command -v trivy &> /dev/null; then
        echo "Installing Trivy for container vulnerability scanning..."
        curl -sfL https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh | sh -s -- -b "${PROJECT_ROOT}/.security_tools" v0.45.0 || {
            echo "Could not install Trivy automatically"
        }
        export PATH="${PROJECT_ROOT}/.security_tools:$PATH"
    fi
    
    # Install Hadolint for Dockerfile scanning
    if ! command -v hadolint &> /dev/null; then
        echo "Installing Hadolint for Dockerfile scanning..."
        curl -sL https://github.com/hadolint/hadolint/releases/latest/download/hadolint-Linux-x86_64 -o "${PROJECT_ROOT}/.security_tools/hadolint" || {
            echo "Could not download Hadolint"
        }
        chmod +x "${PROJECT_ROOT}/.security_tools/hadolint" 2>/dev/null || true
    fi
    
    # Install Bandit for Python code scanning  
    if ! command -v bandit &> /dev/null; then
        echo "Installing Bandit for Python security analysis..."
        pip3 install --user bandit[toml] 2>/dev/null || {
            echo "Could not install Bandit via pip"
        }
    fi
    
    echo "Security tools installation attempted"
}

# Enhanced container vulnerability scanning
scan_container_vulnerabilities_enhanced() {
    echo -e "${YELLOW}🐳 Enhanced Container Security Scanning${NC}"
    local container_report="${REPORTS_DIR}/container_security_enhanced_${TIMESTAMP}.txt"
    
    echo "Enhanced Container Security Analysis" > "$container_report"
    echo "Generated: $(date)" >> "$container_report"
    echo "======================================" >> "$container_report"
    echo "" >> "$container_report"
    
    # Check for container images
    local images_found=false
    for image in "inbox-monitor:latest" "inbox-monitor:test-latest" "email-agent:latest" "email-agent:test-latest"; do
        if docker images --format "table {{.Repository}}:{{.Tag}}" 2>/dev/null | grep -q "$image"; then
            images_found=true
            echo "=== Enhanced Analysis: $image ===" >> "$container_report"
            
            # Try multiple vulnerability scanners
            if command -v trivy &> /dev/null; then
                echo "Trivy Vulnerability Scan Results:" >> "$container_report"
                trivy image --format table --severity HIGH,CRITICAL "$image" >> "$container_report" 2>&1 || {
                    echo "Trivy scan encountered issues" >> "$container_report"
                }
            else
                echo "Trivy not available - install with --install-tools flag" >> "$container_report"
            fi
            
            # Basic Docker image analysis
            echo "" >> "$container_report"
            echo "Basic Image Analysis:" >> "$container_report"
            docker inspect "$image" 2>/dev/null | jq -r '.[] | {
                "Created": .Created,
                "Architecture": .Architecture, 
                "Size": .Size,
                "Layers": (.RootFS.Layers | length)
            }' >> "$container_report" 2>/dev/null || {
                echo "Could not retrieve detailed image information" >> "$container_report"
            }
            
            echo "" >> "$container_report"
        fi
    done
    
    if [[ "$images_found" == "false" ]]; then
        echo "No container images found for security analysis" >> "$container_report"
        echo "Build images first with: docker build -t <image-name> ." >> "$container_report"
    fi
    
    # Enhanced Dockerfile analysis
    echo "" >> "$container_report"
    echo "=== Dockerfile Security Analysis ===" >> "$container_report"
    find "$PROJECT_ROOT" -name "Dockerfile*" -type f 2>/dev/null | while read -r dockerfile; do
        echo "Analyzing: $dockerfile" >> "$container_report"
        
        if command -v hadolint &> /dev/null; then
            hadolint "$dockerfile" >> "$container_report" 2>&1 || true
        else
            # Basic Dockerfile security checks
            echo "Basic Dockerfile Security Checks:" >> "$container_report"
            
            if grep -q "^USER root" "$dockerfile"; then
                echo "⚠️ WARNING: Running as root user detected" >> "$container_report"
            fi
            
            if ! grep -q "^USER " "$dockerfile"; then
                echo "⚠️ WARNING: No USER directive found - container may run as root" >> "$container_report"
            fi
            
            if grep -q "curl.*|.*sh" "$dockerfile"; then
                echo "⚠️ WARNING: Potentially unsafe curl | sh pattern detected" >> "$container_report"
            fi
            
            if grep -q "ADD.*http" "$dockerfile"; then
                echo "⚠️ WARNING: ADD with URLs can be security risk - consider using COPY" >> "$container_report"
            fi
            
            echo "Manual Dockerfile analysis completed" >> "$container_report"
        fi
        
        echo "" >> "$container_report"
    done
    
    echo -e "${GREEN}✅ Enhanced container security scan completed${NC}: $container_report"
}

# Enhanced secrets scanning
scan_secrets_enhanced() {
    echo -e "${YELLOW}🔐 Enhanced Secrets Scanning${NC}"
    local secrets_report="${REPORTS_DIR}/secrets_enhanced_${TIMESTAMP}.txt"
    
    echo "Enhanced Secrets and Credentials Analysis" > "$secrets_report"
    echo "Generated: $(date)" >> "$secrets_report"
    echo "=========================================" >> "$secrets_report"
    echo "" >> "$secrets_report"
    
    # Define comprehensive secret patterns
    local secret_patterns=(
        "password\s*[=:]\s*['\"][^'\"]*['\"]"
        "secret\s*[=:]\s*['\"][^'\"]*['\"]" 
        "api[_-]?key\s*[=:]\s*['\"][^'\"]*['\"]"
        "token\s*[=:]\s*['\"][^'\"]*['\"]"
        "AZURE_CLIENT_SECRET\s*[=:]\s*[^\\s]+"
        "DATABASE_PASSWORD\s*[=:]\s*[^\\s]+"
        "-----BEGIN [A-Z ]*PRIVATE KEY-----"
        "sk_test_[0-9a-zA-Z]+"
        "pk_test_[0-9a-zA-Z]+"
        "[0-9a-f]{32,64}"
    )
    
    echo "=== Scanning for Hardcoded Secrets ===" >> "$secrets_report"
    local secrets_found=false
    
    # Scan multiple file types for secrets
    find "$PROJECT_ROOT" -type f \( \
        -name "*.py" -o \
        -name "*.yaml" -o \
        -name "*.yml" -o \
        -name "*.json" -o \
        -name "*.env*" -o \
        -name "*.config" -o \
        -name "*.conf" \
    \) ! -path "*/.*" ! -path "*/node_modules/*" ! -path "*/__pycache__/*" 2>/dev/null | \
    head -100 | while read -r file; do
        
        local file_has_secrets=false
        for pattern in "${secret_patterns[@]}"; do
            if grep -i -H -n -E "$pattern" "$file" 2>/dev/null | head -5; then
                if [[ "$file_has_secrets" == "false" ]]; then
                    echo "🚨 POTENTIAL SECRETS IN: $file" >> "$secrets_report"
                    file_has_secrets=true
                    secrets_found=true
                fi
            fi
        done
        
        if [[ "$file_has_secrets" == "true" ]]; then
            echo "" >> "$secrets_report"
        fi
    done
    
    # Check environment files specifically
    echo "" >> "$secrets_report"
    echo "=== Environment Files Analysis ===" >> "$secrets_report"
    find "$PROJECT_ROOT" -name "*.env*" -type f 2>/dev/null | while read -r env_file; do
        if [[ -r "$env_file" ]]; then
            echo "Environment file: $env_file" >> "$secrets_report"
            
            # Check for non-placeholder values that look like secrets
            grep -E "^[A-Z_]+=.{20,}" "$env_file" 2>/dev/null | head -10 | while read -r line; do
                if [[ ! "$line" =~ (example|placeholder|changeme|your-|test-) ]]; then
                    echo "⚠️ Potential real credential: ${line%%=*}" >> "$secrets_report"
                fi
            done
            echo "" >> "$secrets_report"
        fi
    done
    
    if [[ "$secrets_found" == "false" ]]; then
        echo "✅ No obvious hardcoded secrets detected in source files" >> "$secrets_report"
    fi
    
    echo -e "${GREEN}✅ Enhanced secrets scanning completed${NC}: $secrets_report"
}

# Enhanced Python code security analysis
scan_python_security_enhanced() {
    echo -e "${YELLOW}🐍 Enhanced Python Security Analysis${NC}"
    local python_report="${REPORTS_DIR}/python_security_${TIMESTAMP}.txt"
    
    echo "Enhanced Python Security Analysis" > "$python_report"
    echo "Generated: $(date)" >> "$python_report"
    echo "=================================" >> "$python_report"
    echo "" >> "$python_report"
    
    # Find Python files
    local python_files=()
    while IFS= read -r -d '' file; do
        python_files+=("$file")
    done < <(find "$PROJECT_ROOT" -name "*.py" -type f ! -path "*/.*" ! -path "*/__pycache__/*" -print0 2>/dev/null | head -z -50)
    
    if [[ ${#python_files[@]} -eq 0 ]]; then
        echo "No Python files found for security analysis" >> "$python_report"
        return
    fi
    
    echo "Found ${#python_files[@]} Python files for analysis" >> "$python_report"
    echo "" >> "$python_report"
    
    # Bandit security analysis
    if command -v bandit &> /dev/null; then
        echo "=== Bandit Security Analysis ===" >> "$python_report"
        bandit -r "$PROJECT_ROOT" -f txt --exclude "*/.*,*/__pycache__/*" >> "$python_report" 2>&1 || {
            echo "Bandit analysis completed with some issues" >> "$python_report"
        }
    else
        echo "=== Manual Python Security Checks ===" >> "$python_report"
        
        # Manual security pattern checks
        for py_file in "${python_files[@]}"; do
            echo "Checking: $py_file" >> "$python_report"
            
            # Check for dangerous functions
            if grep -n "eval\|exec\|subprocess.*shell=True" "$py_file" 2>/dev/null; then
                echo "⚠️ WARNING: Potentially dangerous functions found in $py_file" >> "$python_report"
            fi
            
            # Check for SQL injection patterns
            if grep -n "execute.*%\|query.*format\|f\".*SELECT" "$py_file" 2>/dev/null; then
                echo "⚠️ WARNING: Potential SQL injection patterns in $py_file" >> "$python_report"  
            fi
            
            # Check for hardcoded credentials
            if grep -n "password.*=.*['\"].*['\"]" "$py_file" 2>/dev/null; then
                echo "⚠️ WARNING: Hardcoded credentials pattern in $py_file" >> "$python_report"
            fi
        done
        
        echo "" >> "$python_report"
        echo "Manual security analysis completed" >> "$python_report"
        echo "Install Bandit (pip install bandit) for comprehensive Python security analysis" >> "$python_report"
    fi
    
    echo -e "${GREEN}✅ Enhanced Python security analysis completed${NC}: $python_report"
}

# Enhanced main function
enhanced_main() {
    echo -e "${BLUE}🔐 Enhanced Email Agents Security Scanner${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
    
    # Create reports directory
    mkdir -p "$REPORTS_DIR"
    
    # Check if enhanced scanning is requested
    if [[ "$1" == "--comprehensive" ]] || [[ "$1" == "--enhanced" ]]; then
        echo "Running comprehensive security analysis..."
        
        # Install tools if requested
        if [[ "$INSTALL_TOOLS" == "true" ]] || [[ "$2" == "--install-tools" ]]; then
            install_security_tools
        fi
        
        # Run enhanced scans
        scan_container_vulnerabilities_enhanced
        scan_secrets_enhanced  
        scan_python_security_enhanced
        
        # Generate enhanced summary
        echo -e "${BLUE}📊 Enhanced Security Analysis Summary${NC}"
        echo -e "${BLUE}=====================================${NC}"
        echo "Reports generated in: $REPORTS_DIR"
        ls -la "$REPORTS_DIR"/*"$TIMESTAMP"* 2>/dev/null || echo "No reports found"
        
        echo ""
        echo -e "${GREEN}✅ Enhanced security scanning completed${NC}"
        echo "Review all generated reports before production deployment"
        
    else
        # Run original main function for compatibility
        main "$@"
    fi
}

# Check if this is being run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse arguments for enhanced features
    case "${1:-}" in
        --comprehensive|--enhanced)
            enhanced_main "$@"
            ;;
        --install-tools)
            INSTALL_TOOLS=true
            enhanced_main --comprehensive "$@"
            ;;
        *)
            # Run original main function
            main "$@"
            ;;
    esac
fi