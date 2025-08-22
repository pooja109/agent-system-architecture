#!/bin/bash
# Comprehensive deployment validation script

set -e

# Configuration
NAMESPACE=${NAMESPACE:-"email-agents"}
TIMEOUT=${TIMEOUT:-300}
VERBOSE=${VERBOSE:-false}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🔍 Deployment Validation Suite${NC}"
echo "===================================="
echo "Namespace: ${NAMESPACE}"
echo "Timeout: ${TIMEOUT}s"
echo "===================================="

# Validation functions
validate_pods() {
    echo -e "\n${YELLOW}📦 Validating Pod Status${NC}"
    
    # Check pod readiness
    kubectl wait --for=condition=ready pod \
        -l app=inbox-monitor \
        -n ${NAMESPACE} \
        --timeout=${TIMEOUT}s || {
        echo -e "${RED}❌ Inbox monitor pods not ready${NC}"
        kubectl get pods -n ${NAMESPACE} -l app=inbox-monitor
        kubectl describe pods -n ${NAMESPACE} -l app=inbox-monitor
        return 1
    }
    
    kubectl wait --for=condition=ready pod \
        -l app=email-agent \
        -n ${NAMESPACE} \
        --timeout=${TIMEOUT}s || {
        echo -e "${RED}❌ Email agent pods not ready${NC}"
        kubectl get pods -n ${NAMESPACE} -l app=email-agent
        kubectl describe pods -n ${NAMESPACE} -l app=email-agent
        return 1
    }
    
    echo -e "${GREEN}✅ All pods are ready${NC}"
    
    if [ "${VERBOSE}" == "true" ]; then
        echo -e "\n${BLUE}Pod Details:${NC}"
        kubectl get pods -n ${NAMESPACE} -o wide
    fi
}

validate_services() {
    echo -e "\n${YELLOW}🌐 Validating Services${NC}"
    
    # Check services exist
    kubectl get svc inbox-monitor -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Inbox monitor service not found${NC}"
        return 1
    }
    
    kubectl get svc email-agent -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Email agent service not found${NC}"
        return 1
    }
    
    echo -e "${GREEN}✅ All services are available${NC}"
    
    if [ "${VERBOSE}" == "true" ]; then
        echo -e "\n${BLUE}Service Details:${NC}"
        kubectl get svc -n ${NAMESPACE}
    fi
}

validate_health_endpoints() {
    echo -e "\n${YELLOW}🏥 Validating Health Endpoints${NC}"
    
    # Port forward to test health endpoints
    kubectl port-forward -n ${NAMESPACE} svc/inbox-monitor 8080:80 &
    PF1_PID=$!
    
    kubectl port-forward -n ${NAMESPACE} svc/email-agent 8081:80 &
    PF2_PID=$!
    
    # Wait for port forwards to establish
    sleep 5
    
    # Test health endpoints
    echo "Testing inbox monitor health..."
    if curl -f -s http://localhost:8080/health > /dev/null; then
        echo -e "${GREEN}✅ Inbox monitor health check passed${NC}"
    else
        echo -e "${RED}❌ Inbox monitor health check failed${NC}"
        HEALTH_FAILED=true
    fi
    
    echo "Testing email agent health..."
    if curl -f -s http://localhost:8081/health > /dev/null; then
        echo -e "${GREEN}✅ Email agent health check passed${NC}"
    else
        echo -e "${RED}❌ Email agent health check failed${NC}"
        HEALTH_FAILED=true
    fi
    
    # Test detailed health endpoints
    if [ "${VERBOSE}" == "true" ]; then
        echo -e "\n${BLUE}Detailed Health Responses:${NC}"
        echo "Inbox Monitor:"
        curl -s http://localhost:8080/health | jq . 2>/dev/null || curl -s http://localhost:8080/health
        echo -e "\nEmail Agent:"
        curl -s http://localhost:8081/health | jq . 2>/dev/null || curl -s http://localhost:8081/health
    fi
    
    # Cleanup port forwards
    kill $PF1_PID $PF2_PID 2>/dev/null || true
    
    if [ "${HEALTH_FAILED}" == "true" ]; then
        return 1
    fi
}

validate_scaling() {
    echo -e "\n${YELLOW}📈 Validating Scaling Configuration${NC}"
    
    # Check HPA exists
    kubectl get hpa inbox-monitor -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Inbox monitor HPA not found${NC}"
        return 1
    }
    
    kubectl get hpa email-agent -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Email agent HPA not found${NC}"
        return 1
    }
    
    echo -e "${GREEN}✅ Scaling configuration validated${NC}"
    
    if [ "${VERBOSE}" == "true" ]; then
        echo -e "\n${BLUE}HPA Status:${NC}"
        kubectl get hpa -n ${NAMESPACE}
    fi
}

validate_resource_usage() {
    echo -e "\n${YELLOW}💻 Validating Resource Usage${NC}"
    
    # Get resource usage
    echo "Checking pod resource usage..."
    
    if command -v kubectl top &> /dev/null; then
        kubectl top pods -n ${NAMESPACE} --no-headers | while read line; do
            pod_name=$(echo $line | awk '{print $1}')
            cpu_usage=$(echo $line | awk '{print $2}')
            memory_usage=$(echo $line | awk '{print $3}')
            
            echo "Pod: $pod_name - CPU: $cpu_usage, Memory: $memory_usage"
        done
    else
        echo "kubectl top not available, skipping resource usage check"
    fi
    
    echo -e "${GREEN}✅ Resource usage checked${NC}"
}

validate_logs() {
    echo -e "\n${YELLOW}📋 Validating Logs${NC}"
    
    # Check for error patterns in logs
    echo "Checking for error patterns in logs..."
    
    # Get recent logs and check for errors
    inbox_errors=$(kubectl logs -n ${NAMESPACE} -l app=inbox-monitor --tail=100 | grep -i "error\|exception\|failed" | wc -l)
    email_errors=$(kubectl logs -n ${NAMESPACE} -l app=email-agent --tail=100 | grep -i "error\|exception\|failed" | wc -l)
    
    if [ "$inbox_errors" -gt 10 ]; then
        echo -e "${YELLOW}⚠️  High error count in inbox monitor logs: ${inbox_errors}${NC}"
    fi
    
    if [ "$email_errors" -gt 10 ]; then
        echo -e "${YELLOW}⚠️  High error count in email agent logs: ${email_errors}${NC}"
    fi
    
    # Check for successful startup messages
    if kubectl logs -n ${NAMESPACE} -l app=inbox-monitor --tail=50 | grep -q "Starting\|Ready\|Listening"; then
        echo -e "${GREEN}✅ Inbox monitor startup messages found${NC}"
    else
        echo -e "${YELLOW}⚠️  No startup messages found for inbox monitor${NC}"
    fi
    
    if kubectl logs -n ${NAMESPACE} -l app=email-agent --tail=50 | grep -q "Starting\|Ready\|Listening"; then
        echo -e "${GREEN}✅ Email agent startup messages found${NC}"
    else
        echo -e "${YELLOW}⚠️  No startup messages found for email agent${NC}"
    fi
}

validate_configuration() {
    echo -e "\n${YELLOW}⚙️  Validating Configuration${NC}"
    
    # Check ConfigMaps exist
    kubectl get configmap inbox-monitor-config -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Inbox monitor ConfigMap not found${NC}"
        return 1
    }
    
    kubectl get configmap email-agent-config -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Email agent ConfigMap not found${NC}"
        return 1
    }
    
    # Check Secrets exist
    kubectl get secret inbox-monitor-secrets -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Inbox monitor Secret not found${NC}"
        return 1
    }
    
    kubectl get secret email-agent-secrets -n ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Email agent Secret not found${NC}"
        return 1
    }
    
    echo -e "${GREEN}✅ Configuration validated${NC}"
    
    if [ "${VERBOSE}" == "true" ]; then
        echo -e "\n${BLUE}ConfigMap Contents:${NC}"
        echo "Inbox Monitor Config:"
        kubectl get configmap inbox-monitor-config -n ${NAMESPACE} -o yaml | grep -A 20 "data:"
        echo -e "\nEmail Agent Config:"
        kubectl get configmap email-agent-config -n ${NAMESPACE} -o yaml | grep -A 20 "data:"
    fi
}

# Run all validations
main() {
    local validation_failed=false
    
    # Check namespace exists
    kubectl get namespace ${NAMESPACE} &>/dev/null || {
        echo -e "${RED}❌ Namespace ${NAMESPACE} not found${NC}"
        exit 1
    }
    
    # Run validation functions
    validate_pods || validation_failed=true
    validate_services || validation_failed=true
    validate_configuration || validation_failed=true
    validate_health_endpoints || validation_failed=true
    validate_scaling || validation_failed=true
    validate_resource_usage || validation_failed=true
    validate_logs || validation_failed=true
    
    echo -e "\n===================================="
    if [ "$validation_failed" == "true" ]; then
        echo -e "${RED}❌ Deployment validation failed${NC}"
        echo -e "Please check the errors above and resolve them."
        exit 1
    else
        echo -e "${GREEN}✅ Deployment validation successful${NC}"
        echo -e "All services are running correctly!"
        
        # Final status summary
        echo -e "\n${BLUE}Final Status Summary:${NC}"
        kubectl get all -n ${NAMESPACE}
    fi
}

main "$@"