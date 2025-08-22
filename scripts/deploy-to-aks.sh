#!/bin/bash
# Deploy agents to AKS cluster

set -e

# Configuration
CLUSTER_NAME=${AKS_CLUSTER_NAME:-"aou-lowtouch-aks"}
RESOURCE_GROUP=${AKS_RESOURCE_GROUP:-"aou-lowtouch-rg"}
NAMESPACE=${NAMESPACE:-"email-agents"}
REGISTRY=${ACR_REGISTRY:-"aoulowtouch.azurecr.io"}
IMAGE_TAG=${IMAGE_TAG:-"latest"}
ENVIRONMENT=${ENVIRONMENT:-"production"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🚀 AKS Deployment Script${NC}"
echo "===================================="
echo "Cluster: ${CLUSTER_NAME}"
echo "Namespace: ${NAMESPACE}"
echo "Registry: ${REGISTRY}"
echo "Tag: ${IMAGE_TAG}"
echo "Environment: ${ENVIRONMENT}"
echo "===================================="

# Function to check prerequisites
check_prerequisites() {
    echo -e "\n${YELLOW}Checking prerequisites...${NC}"
    
    # Check Azure CLI
    if ! command -v az &> /dev/null; then
        echo -e "${RED}❌ Azure CLI not found${NC}"
        exit 1
    fi
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}❌ kubectl not found${NC}"
        exit 1
    fi
    
    # Check kustomize
    if ! command -v kustomize &> /dev/null; then
        echo -e "${YELLOW}⚠️  kustomize not found, using kubectl -k${NC}"
    fi
    
    echo -e "${GREEN}✅ Prerequisites satisfied${NC}"
}

# Function to connect to AKS
connect_to_aks() {
    echo -e "\n${YELLOW}Connecting to AKS cluster...${NC}"
    
    # Get credentials
    az aks get-credentials \
        --resource-group ${RESOURCE_GROUP} \
        --name ${CLUSTER_NAME} \
        --overwrite-existing
    
    # Verify connection
    kubectl cluster-info &> /dev/null || {
        echo -e "${RED}❌ Failed to connect to cluster${NC}"
        exit 1
    }
    
    echo -e "${GREEN}✅ Connected to AKS cluster${NC}"
}

# Function to create ACR secret
create_acr_secret() {
    echo -e "\n${YELLOW}Creating ACR pull secret...${NC}"
    
    # Get ACR credentials
    ACR_USERNAME=$(az acr credential show --name ${REGISTRY%%.*} --query username -o tsv)
    ACR_PASSWORD=$(az acr credential show --name ${REGISTRY%%.*} --query passwords[0].value -o tsv)
    
    # Create secret
    kubectl create secret docker-registry acr-secret \
        --namespace=${NAMESPACE} \
        --docker-server=${REGISTRY} \
        --docker-username=${ACR_USERNAME} \
        --docker-password=${ACR_PASSWORD} \
        --dry-run=client -o yaml | kubectl apply -f -
    
    echo -e "${GREEN}✅ ACR secret created${NC}"
}

# Function to deploy applications
deploy_applications() {
    echo -e "\n${YELLOW}Deploying applications...${NC}"
    
    # Update image tags in kustomization
    cd k8s
    
    # Apply namespace first
    kubectl apply -f namespace.yaml
    
    # Create ACR secret
    create_acr_secret
    
    # Apply configurations
    if command -v kustomize &> /dev/null; then
        kustomize build . | kubectl apply -f -
    else
        kubectl apply -k .
    fi
    
    echo -e "${GREEN}✅ Applications deployed${NC}"
}

# Function to wait for deployments
wait_for_deployments() {
    echo -e "\n${YELLOW}Waiting for deployments to be ready...${NC}"
    
    # Wait for inbox-monitor
    kubectl rollout status deployment/inbox-monitor \
        --namespace=${NAMESPACE} \
        --timeout=300s || {
        echo -e "${RED}❌ inbox-monitor deployment failed${NC}"
        kubectl describe deployment inbox-monitor -n ${NAMESPACE}
        exit 1
    }
    
    # Wait for email-agent
    kubectl rollout status deployment/email-agent \
        --namespace=${NAMESPACE} \
        --timeout=300s || {
        echo -e "${RED}❌ email-agent deployment failed${NC}"
        kubectl describe deployment email-agent -n ${NAMESPACE}
        exit 1
    }
    
    echo -e "${GREEN}✅ All deployments ready${NC}"
}

# Function to verify deployment
verify_deployment() {
    echo -e "\n${YELLOW}Verifying deployment...${NC}"
    
    # Get pod status
    echo -e "\n${BLUE}Pod Status:${NC}"
    kubectl get pods -n ${NAMESPACE} -l 'app in (inbox-monitor,email-agent)'
    
    # Get service status
    echo -e "\n${BLUE}Service Status:${NC}"
    kubectl get svc -n ${NAMESPACE}
    
    # Get HPA status
    echo -e "\n${BLUE}HPA Status:${NC}"
    kubectl get hpa -n ${NAMESPACE}
    
    # Test health endpoints
    echo -e "\n${YELLOW}Testing health endpoints...${NC}"
    
    # Port forward to test
    kubectl port-forward -n ${NAMESPACE} svc/inbox-monitor 8080:80 &
    PF1_PID=$!
    kubectl port-forward -n ${NAMESPACE} svc/email-agent 8081:80 &
    PF2_PID=$!
    
    sleep 5
    
    # Test endpoints
    curl -s http://localhost:8080/health > /dev/null && \
        echo -e "${GREEN}✅ inbox-monitor health check passed${NC}" || \
        echo -e "${RED}❌ inbox-monitor health check failed${NC}"
    
    curl -s http://localhost:8081/health > /dev/null && \
        echo -e "${GREEN}✅ email-agent health check passed${NC}" || \
        echo -e "${RED}❌ email-agent health check failed${NC}"
    
    # Kill port forwards
    kill $PF1_PID $PF2_PID 2>/dev/null
    
    echo -e "${GREEN}✅ Deployment verified${NC}"
}

# Main execution
main() {
    echo -e "${BLUE}Starting AKS deployment...${NC}\n"
    
    check_prerequisites
    connect_to_aks
    deploy_applications
    wait_for_deployments
    verify_deployment
    
    echo -e "\n${GREEN}🎉 Deployment completed successfully!${NC}"
    echo "===================================="
    echo -e "View pods: ${BLUE}kubectl get pods -n ${NAMESPACE}${NC}"
    echo -e "View logs: ${BLUE}kubectl logs -n ${NAMESPACE} -l app=inbox-monitor${NC}"
    echo -e "Port forward: ${BLUE}kubectl port-forward -n ${NAMESPACE} svc/inbox-monitor 8080:80${NC}"
}

# Run main function
main