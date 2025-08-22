# Kubernetes Deployment Guide

This directory contains production-ready Kubernetes manifests for deploying the email agents (inbox-monitor and email-agent) to Azure Kubernetes Service (AKS).

## Prerequisites

### Required Tools
- [kubectl](https://kubernetes.io/docs/tasks/tools/) (v1.24+)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/) (v2.40+)
- [kustomize](https://kustomize.io/) (v4.5+) - optional, kubectl has built-in support

### Required Azure Resources
- AKS cluster with Azure Key Vault CSI driver enabled
- Azure Container Registry (ACR)
- Azure Key Vault with required secrets
- Managed Identity for Key Vault access

### Required Cluster Add-ons
```bash
# Enable Azure Key Vault CSI driver
az aks addon enable --name azure-keyvault-secrets-provider --resource-group aou-lowtouch-rg --cluster-name aou-lowtouch-aks

# Enable pod identity (if using pod identity instead of managed identity)
az aks addon enable --name pod-identity --resource-group aou-lowtouch-rg --cluster-name aou-lowtouch-aks
```

## Quick Start

### 1. Deploy Using Script
```bash
# Set environment variables (optional - script has defaults)
export AKS_CLUSTER_NAME="aou-lowtouch-aks"
export AKS_RESOURCE_GROUP="aou-lowtouch-rg"
export ACR_REGISTRY="aoulowtouch.azurecr.io"

# Run deployment script
./scripts/deploy-to-aks.sh
```

### 2. Manual Deployment
```bash
# Connect to cluster
az aks get-credentials --resource-group aou-lowtouch-rg --name aou-lowtouch-aks

# Deploy all manifests
kubectl apply -k k8s/

# Check deployment status
kubectl get pods -n email-agents
kubectl get svc -n email-agents
```

## Directory Structure

```
k8s/
├── README.md                           # This file
├── namespace.yaml                      # Namespace definitions (prod + staging)
├── networkpolicy.yaml                  # Network security policies
├── kustomization.yaml                  # Kustomize configuration
├── validate-manifests.sh               # Validation script
├── inbox-monitor/
│   ├── configmap.yaml                  # Non-sensitive configuration
│   ├── secret.yaml                     # Template for manual secrets
│   ├── secretproviderclass.yaml        # Azure Key Vault integration
│   ├── deployment.yaml                 # Pod specification with health checks
│   ├── service.yaml                    # Service and ServiceAccount
│   ├── hpa.yaml                        # Horizontal Pod Autoscaler
│   ├── pdb.yaml                        # Pod Disruption Budget
│   ├── config.env                      # Environment-specific overrides
│   └── secrets.env                     # Secret templates (DO NOT commit real values)
└── email-agent/
    ├── configmap.yaml                  # Non-sensitive configuration
    ├── secret.yaml                     # Template for manual secrets
    ├── secretproviderclass.yaml        # Azure Key Vault integration
    ├── deployment.yaml                 # Pod specification with health checks
    ├── service.yaml                    # Service and ServiceAccount
    ├── hpa.yaml                        # Horizontal Pod Autoscaler
    ├── pdb.yaml                        # Pod Disruption Budget
    ├── config.env                      # Environment-specific overrides
    └── secrets.env                     # Secret templates (DO NOT commit real values)
```

## Configuration Management

### Environment Variables
Configuration is managed through multiple layers:

1. **ConfigMaps** - Non-sensitive defaults (configmap.yaml)
2. **Environment Overrides** - Environment-specific values (config.env)
3. **Secrets** - Sensitive values from Azure Key Vault (secretproviderclass.yaml)
4. **Manual Secrets** - Fallback for development (secret.yaml templates)

### Secret Management
Secrets are managed through Azure Key Vault using the CSI driver:

```yaml
# Required secrets in Key Vault:
- azure-key-vault-url
- azure-tenant-id
- azure-client-id
- azure-client-secret
- graph-api-monitored-email
- databricks-server-hostname
- databricks-http-path
- databricks-catalog
- databricks-schema
- azure-storage-connection-string  # email-agent only
- azure-storage-account-name       # email-agent only
- azure-storage-sas-token         # email-agent only
```

## Security Features

### Network Security
- NetworkPolicies restrict pod-to-pod communication
- Ingress limited to health check ports
- Egress allows DNS, HTTPS, and inter-service communication

### Pod Security
- Non-root containers (runAsUser: 1000)
- Read-only root filesystem for secrets
- Security contexts with fsGroup restrictions
- Image pull secrets for private registry

### Secret Management
- Azure Key Vault CSI driver integration
- No secrets stored in manifests
- Managed identity authentication
- Volume-mounted secrets with proper permissions

## Scaling and Availability

### Horizontal Pod Autoscaler (HPA)
- **Min replicas:** 2
- **Max replicas:** 10
- **CPU threshold:** 70%
- **Memory threshold:** 80%
- **Scale-down stabilization:** 300s
- **Scale-up stabilization:** 60s

### Pod Disruption Budget (PDB)
- **Min available:** 1 pod per service
- Ensures availability during cluster maintenance

### Resource Limits
```yaml
requests:
  memory: "768Mi"  # Updated based on Python workload requirements
  cpu: "500m"      # Increased to prevent throttling
limits:
  memory: "1.5Gi"  # Sufficient headroom for processing
  cpu: "2000m"     # Allow bursting for batch operations
```

## Health Monitoring

### Health Check Endpoints
- **Liveness:** `/health` - Container restart if fails
- **Readiness:** `/ready` - Traffic routing control
- **Startup:** `/health` - Slow container initialization support

### Probe Configuration
```yaml
livenessProbe:
  initialDelaySeconds: 30  # Optimized for Python startup
  periodSeconds: 30
  timeoutSeconds: 10
  failureThreshold: 3

readinessProbe:
  initialDelaySeconds: 15  # Reduced for faster traffic routing
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3

startupProbe:             # Added for slow-starting containers
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 12    # Allow up to 2 minutes for startup
```

### Monitoring Integration
- Prometheus scraping enabled via annotations
- ServiceMonitor for advanced metrics collection
- Grafana dashboard support

## Troubleshooting

### Common Issues

#### 1. Pod Startup Failures
```bash
# Check pod events
kubectl describe pod -n email-agents -l app=inbox-monitor

# Check logs
kubectl logs -n email-agents -l app=inbox-monitor --tail=100

# Check secret mounting
kubectl exec -n email-agents deployment/inbox-monitor -- ls -la /mnt/secrets-store
```

#### 2. Key Vault Access Issues
```bash
# Check SecretProviderClass status
kubectl describe secretproviderclass -n email-agents

# Check pod identity binding
kubectl get azureidentitybinding -n email-agents

# Verify managed identity permissions
az keyvault show --name aou-lowtouch-kv --query properties.accessPolicies
```

#### 3. Network Connectivity
```bash
# Test pod-to-pod communication
kubectl exec -n email-agents deployment/inbox-monitor -- curl http://email-agent:80/health

# Check NetworkPolicy
kubectl describe networkpolicy -n email-agents

# Test external connectivity
kubectl exec -n email-agents deployment/inbox-monitor -- nslookup aoulowtouch.blob.core.windows.net
```

#### 4. Scaling Issues
```bash
# Check HPA status
kubectl get hpa -n email-agents

# Check metrics server
kubectl top pods -n email-agents

# Check resource requests vs limits
kubectl describe deployment -n email-agents
```

### Log Locations
- **Application logs:** Configured via LOG_LEVEL environment variable
- **Container logs:** `kubectl logs -n email-agents <pod-name>`
- **Kubernetes events:** `kubectl get events -n email-agents --sort-by='.lastTimestamp'`

## Maintenance

### Updating Images
```bash
# Update image tags in kustomization.yaml
kubectl kustomize . | kubectl apply -f -

# Or use deployment script with new tag
export IMAGE_TAG="v1.2.3"
./scripts/deploy-to-aks.sh
```

### Secret Rotation
```bash
# Update secrets in Azure Key Vault
az keyvault secret set --vault-name aou-lowtouch-kv --name azure-client-secret --value "new-secret"

# Restart pods to pick up new secrets
kubectl rollout restart deployment/inbox-monitor -n email-agents
kubectl rollout restart deployment/email-agent -n email-agents
```

### Scaling Operations
```bash
# Manual scaling
kubectl scale deployment inbox-monitor --replicas=5 -n email-agents

# Update HPA limits
kubectl patch hpa inbox-monitor -n email-agents --patch '{"spec":{"maxReplicas":15}}'
```

## Security Checklist

- [ ] Azure Key Vault CSI driver installed and configured
- [ ] Managed identity has Key Vault access permissions
- [ ] NetworkPolicies are applied and tested
- [ ] Pod Security Standards enforced at namespace level
- [ ] Container images scanned for vulnerabilities
- [ ] Secret rotation procedures established
- [ ] RBAC permissions follow least privilege principle
- [ ] Monitoring and alerting configured
- [ ] Backup and disaster recovery procedures documented

## Performance Tuning

### Resource Optimization
1. Monitor actual resource usage with `kubectl top pods`
2. Adjust requests/limits based on observed patterns
3. Use VPA (Vertical Pod Autoscaler) for recommendations

### Network Optimization
1. Consider using Azure CNI for better network performance
2. Enable proximity placement groups for low latency
3. Use Azure Load Balancer for external traffic

### Storage Optimization
1. Use Azure Disk for persistent storage if needed
2. Consider Azure Files for shared storage scenarios
3. Implement proper backup strategies

## Support

For deployment issues:
1. Check this documentation
2. Review pod logs and events
3. Validate secret and configuration management
4. Test network connectivity
5. Monitor resource utilization

For application-specific issues, refer to the individual service documentation in their respective directories.