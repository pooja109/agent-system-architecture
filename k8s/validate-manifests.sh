#!/bin/bash
# Kubernetes Manifest Validation Script
# Validates all manifests for syntax, best practices, and security

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

echo -e "${BLUE}🔍 Kubernetes Manifest Validation${NC}"
echo "===================================="

# Function to log test results
log_test() {
    local test_name="$1"
    local result="$2"
    local details="$3"
    
    ((TOTAL_CHECKS++))
    
    if [ "$result" = "PASS" ]; then
        echo -e "${GREEN}✅ $test_name${NC}"
        ((PASSED_CHECKS++))
    else
        echo -e "${RED}❌ $test_name${NC}"
        if [ -n "$details" ]; then
            echo -e "   ${YELLOW}Details: $details${NC}"
        fi
        ((FAILED_CHECKS++))
    fi
}

# Function to check tool availability
check_tool() {
    local tool="$1"
    local description="$2"
    
    if command -v "$tool" &> /dev/null; then
        log_test "$description available" "PASS"
        return 0
    else
        log_test "$description available" "FAIL" "Install $tool to enable validation"
        return 1
    fi
}

echo -e "\n${YELLOW}Checking prerequisites...${NC}"

# Check required tools
check_tool "kubectl" "kubectl"
check_tool "python3" "Python 3"
KUSTOMIZE_AVAILABLE=false
if check_tool "kustomize" "kustomize"; then
    KUSTOMIZE_AVAILABLE=true
fi

echo -e "\n${YELLOW}Validating YAML syntax...${NC}"

# YAML syntax validation
python3 -c "
import yaml
import os
import sys

failed = False
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.yaml') or file.endswith('.yml'):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, 'r') as f:
                    list(yaml.safe_load_all(f))
                print(f'✅ {file_path}: Valid YAML')
            except Exception as e:
                print(f'❌ {file_path}: {str(e)}')
                failed = True

sys.exit(1 if failed else 0)
" && log_test "YAML syntax validation" "PASS" || log_test "YAML syntax validation" "FAIL"

echo -e "\n${YELLOW}Validating Kubernetes manifests...${NC}"

# Kubernetes manifest validation
if kubectl version --client &>/dev/null; then
    # Test dry-run validation
    if kubectl apply --dry-run=client --validate=false -f . &>/dev/null; then
        log_test "Kubernetes manifest structure" "PASS"
    else
        log_test "Kubernetes manifest structure" "FAIL" "Run 'kubectl apply --dry-run=client -f .' for details"
    fi
    
    # Test kustomize build if available
    if [ "$KUSTOMIZE_AVAILABLE" = true ]; then
        if kustomize build . &>/dev/null; then
            log_test "Kustomize build validation" "PASS"
        else
            log_test "Kustomize build validation" "FAIL" "Run 'kustomize build .' for details"
        fi
    else
        if kubectl kustomize . &>/dev/null; then
            log_test "Kubectl kustomize validation" "PASS"
        else
            log_test "Kubectl kustomize validation" "FAIL" "Run 'kubectl kustomize .' for details"
        fi
    fi
else
    log_test "Kubernetes client validation" "FAIL" "kubectl not properly configured"
fi

echo -e "\n${YELLOW}Validating security configurations...${NC}"

# Security validation
check_security() {
    local file="$1"
    local check_name="$2"
    local pattern="$3"
    local expected="$4"
    
    if grep -q "$pattern" "$file" 2>/dev/null; then
        if [ "$expected" = "true" ]; then
            log_test "$check_name in $file" "PASS"
        else
            log_test "$check_name in $file" "FAIL" "Found security issue"
        fi
    else
        if [ "$expected" = "true" ]; then
            log_test "$check_name in $file" "FAIL" "Security feature missing"
        else
            log_test "$check_name in $file" "PASS"
        fi
    fi
}

# Check for non-root users
check_security "*/deployment.yaml" "Non-root user configuration" "runAsNonRoot: true" "true"
check_security "*/deployment.yaml" "Specific user ID" "runAsUser: 1000" "true"

# Check for security contexts
check_security "*/deployment.yaml" "Security context defined" "securityContext:" "true"

# Check for resource limits
check_security "*/deployment.yaml" "Resource limits defined" "limits:" "true"
check_security "*/deployment.yaml" "Resource requests defined" "requests:" "true"

# Check for health probes
check_security "*/deployment.yaml" "Liveness probe defined" "livenessProbe:" "true"
check_security "*/deployment.yaml" "Readiness probe defined" "readinessProbe:" "true"

# Check for secrets not hardcoded
if grep -r "password\|secret\|key" --include="*.yaml" . | grep -v "secretRef\|secretName\|SecretProviderClass" | grep -v "# " &>/dev/null; then
    log_test "No hardcoded secrets" "FAIL" "Found potential hardcoded secrets"
else
    log_test "No hardcoded secrets" "PASS"
fi

echo -e "\n${YELLOW}Validating best practices...${NC}"

# Best practices validation
check_best_practice() {
    local pattern="$1"
    local description="$2"
    local expected="$3"
    
    if find . -name "*.yaml" -exec grep -l "$pattern" {} \; | wc -l | grep -q "^[1-9]"; then
        if [ "$expected" = "true" ]; then
            log_test "$description" "PASS"
        else
            log_test "$description" "FAIL"
        fi
    else
        if [ "$expected" = "true" ]; then
            log_test "$description" "FAIL"
        else
            log_test "$description" "PASS"
        fi
    fi
}

# Check for labels
check_best_practice "app:" "Application labels defined" "true"
check_best_practice "version:" "Version labels defined" "true"

# Check for annotations
check_best_practice "prometheus.io/scrape" "Prometheus monitoring enabled" "true"

# Check for pod disruption budgets
check_best_practice "PodDisruptionBudget" "Pod Disruption Budgets defined" "true"

# Check for horizontal pod autoscalers
check_best_practice "HorizontalPodAutoscaler" "Horizontal Pod Autoscalers defined" "true"

# Check for network policies
check_best_practice "NetworkPolicy" "Network Policies defined" "true"

echo -e "\n${YELLOW}Validating configuration completeness...${NC}"

# Configuration validation
required_files=(
    "namespace.yaml"
    "networkpolicy.yaml"
    "kustomization.yaml"
    "inbox-monitor/configmap.yaml"
    "inbox-monitor/secret.yaml"
    "inbox-monitor/deployment.yaml"
    "inbox-monitor/service.yaml"
    "inbox-monitor/hpa.yaml"
    "inbox-monitor/pdb.yaml"
    "email-agent/configmap.yaml"
    "email-agent/secret.yaml"
    "email-agent/deployment.yaml"
    "email-agent/service.yaml"
    "email-agent/hpa.yaml"
    "email-agent/pdb.yaml"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        log_test "Required file: $file" "PASS"
    else
        log_test "Required file: $file" "FAIL" "File missing"
    fi
done

# Check for environment files
env_files=(
    "inbox-monitor/config.env"
    "inbox-monitor/secrets.env"
    "email-agent/config.env"
    "email-agent/secrets.env"
)

for file in "${env_files[@]}"; do
    if [ -f "$file" ]; then
        log_test "Environment file: $file" "PASS"
    else
        log_test "Environment file: $file" "FAIL" "File missing for kustomize"
    fi
done

echo -e "\n${YELLOW}Validating resource specifications...${NC}"

# Resource validation
validate_resources() {
    local file="$1"
    if [ -f "$file" ]; then
        # Check memory requests are reasonable (not too low)
        if grep -q "memory.*[5-9][0-9][0-9]Mi\|memory.*[1-9]Gi" "$file"; then
            log_test "Memory requests in $file" "PASS"
        else
            log_test "Memory requests in $file" "FAIL" "Memory requests may be too low for Python applications"
        fi
        
        # Check CPU requests are present
        if grep -q "cpu.*[0-9]" "$file"; then
            log_test "CPU requests in $file" "PASS"
        else
            log_test "CPU requests in $file" "FAIL" "CPU requests missing"
        fi
    fi
}

validate_resources "inbox-monitor/deployment.yaml"
validate_resources "email-agent/deployment.yaml"

echo -e "\n${YELLOW}Running additional validations...${NC}"

# Check for common Kubernetes anti-patterns
if grep -r "latest" --include="*.yaml" . | grep -v "newTag\|# " &>/dev/null; then
    log_test "No 'latest' image tags" "FAIL" "Using 'latest' tag is not recommended for production"
else
    log_test "No 'latest' image tags" "PASS"
fi

# Check for privileged containers
if grep -r "privileged: true" --include="*.yaml" . &>/dev/null; then
    log_test "No privileged containers" "FAIL" "Privileged containers found"
else
    log_test "No privileged containers" "PASS"
fi

# Check for host network usage
if grep -r "hostNetwork: true" --include="*.yaml" . &>/dev/null; then
    log_test "No host network usage" "FAIL" "Host network usage found"
else
    log_test "No host network usage" "PASS"
fi

# Final summary
echo -e "\n${BLUE}Validation Summary${NC}"
echo "=================="
echo -e "Total checks: ${TOTAL_CHECKS}"
echo -e "${GREEN}Passed: ${PASSED_CHECKS}${NC}"
echo -e "${RED}Failed: ${FAILED_CHECKS}${NC}"

if [ $FAILED_CHECKS -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All validations passed! Manifests are ready for deployment.${NC}"
    exit 0
else
    echo -e "\n${RED}⚠️  Some validations failed. Please address the issues above.${NC}"
    exit 1
fi