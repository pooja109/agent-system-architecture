# Core Deployment Guide - Inbox Monitor Scenario Tracking

## Overview

This guide provides step-by-step deployment procedures for the core scenario tracking system (Phases 1-3). It covers environment setup, configuration management, deployment execution, and validation procedures for production, staging, and development environments.

## Prerequisites

### System Requirements

- **Python**: 3.9 or higher
- **Databricks Workspace**: With Unity Catalog enabled
- **Azure Active Directory**: OAuth application configured
- **Network Access**: HTTPS connectivity to Databricks workspace
- **Storage**: Minimum 1GB available disk space
- **Memory**: Minimum 4GB RAM recommended

### Required Permissions

- **Databricks**: 
  - CREATE TABLE permissions in target catalog/schema
  - SELECT/INSERT permissions on scenario tracking tables
  - EXECUTE permissions on target warehouse
- **Azure AD**: 
  - OAuth application with Databricks scope
  - Client credentials for service principal

### Dependencies

```bash
# Core Python packages
pip install pydantic structlog databricks-sql-connector

# Optional packages for enhanced functionality
pip install asyncio-throttle tenacity
```

## Environment Configuration

### Environment Variables

Create environment-specific configuration files:

#### Production Environment
```bash
# /etc/environment or ~/.bashrc
export DATABRICKS_HOST="https://your-workspace.databricks.com"
export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"
export DATABRICKS_OAUTH_CLIENT_ID="your-oauth-client-id"
export DATABRICKS_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
export DATABRICKS_CATALOG="inbox_monitor_prod"
export DATABRICKS_SCHEMA="scenario_tracking"
export SCENARIO_TRACKING_TABLE_SUFFIX=""
export SCENARIO_TRACKING_LOG_DIR="/var/log/scenario_tracking"
```

#### Staging Environment
```bash
export DATABRICKS_HOST="https://your-workspace.databricks.com"
export DATABRICKS_WAREHOUSE_ID="your-staging-warehouse-id"
export DATABRICKS_OAUTH_CLIENT_ID="your-oauth-client-id"
export DATABRICKS_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
export DATABRICKS_CATALOG="inbox_monitor_staging"
export DATABRICKS_SCHEMA="scenario_tracking_staging"
export SCENARIO_TRACKING_TABLE_SUFFIX="_staging"
export SCENARIO_TRACKING_LOG_DIR="/var/log/scenario_tracking_staging"
```

#### Development Environment
```bash
export DATABRICKS_HOST="https://your-workspace.databricks.com"
export DATABRICKS_WAREHOUSE_ID="your-dev-warehouse-id"
export DATABRICKS_OAUTH_CLIENT_ID="your-oauth-client-id"
export DATABRICKS_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
export DATABRICKS_CATALOG="inbox_monitor_dev"
export DATABRICKS_SCHEMA="scenario_tracking_dev"
export SCENARIO_TRACKING_TABLE_SUFFIX="_dev"
export SCENARIO_TRACKING_LOG_DIR="/var/log/scenario_tracking_dev"
```

### Configuration Files

#### Production Configuration
```yaml
# config/core_deployment/core_production_config.yaml
database:
  catalog: "${DATABRICKS_CATALOG}"
  schema: "${DATABRICKS_SCHEMA}"
  warehouse_id: "${DATABRICKS_WAREHOUSE_ID}"
  host: "${DATABRICKS_HOST}"
  oauth_client_id: "${DATABRICKS_OAUTH_CLIENT_ID}"
  oauth_client_secret: "${DATABRICKS_OAUTH_CLIENT_SECRET}"

core_deployment:
  log_directory: "/var/log/scenario_tracking"
  config_directory: "./config"
  backup_directory: "/var/backups/scenario_tracking"
  enable_performance_monitoring: true

scenario_tracking:
  enabled: true
  table_suffix: ""
  batch_insert_size: 50
  async_insert: true
  retry_attempts: 3
  connection_timeout_seconds: 30

logging:
  level: "INFO"
  format: "structured"
  file_rotation: true
  max_file_size: "100MB"
  backup_count: 10
```

#### Development Configuration
```yaml
# config/core_deployment/core_development_config.yaml
database:
  catalog: "${DATABRICKS_CATALOG:-inbox_monitor_dev}"
  schema: "${DATABRICKS_SCHEMA:-scenario_tracking_dev}"
  warehouse_id: "${DATABRICKS_WAREHOUSE_ID}"
  host: "${DATABRICKS_HOST}"
  oauth_client_id: "${DATABRICKS_OAUTH_CLIENT_ID}"
  oauth_client_secret: "${DATABRICKS_OAUTH_CLIENT_SECRET}"

scenario_tracking:
  enabled: true
  table_suffix: "_dev"
  batch_insert_size: 10
  async_insert: false  # Synchronous for debugging
  retry_attempts: 1
  connection_timeout_seconds: 10

logging:
  level: "DEBUG"
  format: "structured"
  console_output: true
```

## Deployment Procedures

### Pre-Deployment Validation

Before deploying, run the production readiness validator:

```bash
cd agents/inbox_monitor

# Validate production readiness
python scripts/testing/validate_core_production_readiness.py \
  --table-suffix="_prod_validation" \
  --output pre_deployment_validation.json \
  --verbose

# Check validation results
if [ $? -eq 0 ]; then
  echo "✅ Pre-deployment validation passed"
else
  echo "❌ Pre-deployment validation failed"
  exit 1
fi
```

### Core System Deployment

#### Step 1: Environment Preparation

```bash
# Create necessary directories
sudo mkdir -p /var/log/scenario_tracking
sudo mkdir -p /var/backups/scenario_tracking
sudo mkdir -p /etc/scenario_tracking

# Set appropriate permissions
sudo chown -R $(whoami):$(whoami) /var/log/scenario_tracking
sudo chmod 755 /var/log/scenario_tracking

# Verify environment variables
echo "Verifying environment configuration..."
python -c "
import os
required_vars = [
    'DATABRICKS_HOST',
    'DATABRICKS_WAREHOUSE_ID', 
    'DATABRICKS_OAUTH_CLIENT_ID',
    'DATABRICKS_OAUTH_CLIENT_SECRET'
]

missing = []
for var in required_vars:
    if not os.getenv(var):
        missing.append(var)

if missing:
    print(f'❌ Missing environment variables: {missing}')
    exit(1)
else:
    print('✅ All required environment variables set')
"
```

#### Step 2: Database Schema Deployment

```bash
# Deploy core database schema
python scripts/deployment/deploy_core_scenario_tracking.py \
  --config config/core_deployment/core_production_config.yaml \
  --table-suffix="${SCENARIO_TRACKING_TABLE_SUFFIX}" \
  --verbose

# Verify deployment success
if [ $? -eq 0 ]; then
  echo "✅ Database schema deployment succeeded"
else
  echo "❌ Database schema deployment failed"
  exit 1
fi
```

#### Step 3: Service Configuration

```bash
# Copy configuration files
cp config/core_production_config.py /etc/scenario_tracking/
cp config/core_deployment/core_production_config.yaml /etc/scenario_tracking/

# Create systemd service file (optional)
sudo tee /etc/systemd/system/scenario-tracking.service > /dev/null << EOF
[Unit]
Description=Scenario Tracking Core Service
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$(pwd)
Environment=PYTHONPATH=$(pwd)
EnvironmentFile=/etc/scenario_tracking/environment
ExecStart=/usr/bin/python3 -m agents.inbox_monitor.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable scenario-tracking
```

#### Step 4: Deployment Validation

```bash
# Validate deployment
python scripts/deployment/validate_core_deployment.py \
  --table-suffix="${SCENARIO_TRACKING_TABLE_SUFFIX}" \
  --config config/core_deployment/core_production_config.yaml

# Run integration tests
python scripts/testing/run_core_integration_tests.py \
  --table-suffix="${SCENARIO_TRACKING_TABLE_SUFFIX}_test" \
  --verbose

# Generate deployment report
python -c "
import json
from datetime import datetime

deployment_report = {
    'deployment_timestamp': datetime.now().isoformat(),
    'environment': 'production',
    'table_suffix': '${SCENARIO_TRACKING_TABLE_SUFFIX}',
    'version': 'core_phases_1_3',
    'status': 'deployed',
    'validation_passed': True
}

with open('deployment_report.json', 'w') as f:
    json.dump(deployment_report, f, indent=2)

print('✅ Deployment report generated: deployment_report.json')
"
```

### Blue-Green Deployment

For zero-downtime deployments:

#### Step 1: Prepare Green Environment

```bash
# Set green environment variables
export SCENARIO_TRACKING_TABLE_SUFFIX="_green"
export DATABRICKS_SCHEMA="scenario_tracking_green"

# Deploy to green environment
python scripts/deployment/deploy_core_scenario_tracking.py \
  --config config/core_deployment/core_production_config.yaml \
  --table-suffix="_green"
```

#### Step 2: Validate Green Environment

```bash
# Validate green deployment
python scripts/deployment/validate_core_deployment.py \
  --table-suffix="_green"

# Run smoke tests
python scripts/testing/run_core_integration_tests.py \
  --table-suffix="_green_test" \
  --suite smoke
```

#### Step 3: Switch Traffic

```bash
# Update configuration to point to green
sed -i 's/scenario_tracking/scenario_tracking_green/g' /etc/scenario_tracking/core_production_config.yaml

# Restart service to pick up new configuration
sudo systemctl restart scenario-tracking

# Verify service health
python scripts/maintenance/health_monitor_core.py
```

#### Step 4: Cleanup Blue Environment

```bash
# After successful green deployment, cleanup blue
export SCENARIO_TRACKING_TABLE_SUFFIX="_blue"

# Archive blue data if needed
python scripts/backup/archive_environment.py --suffix="_blue"

# Remove blue tables
python scripts/deployment/cleanup_environment.py --suffix="_blue"
```

### Rollback Procedures

#### Automatic Rollback

```bash
# Use automated rollback script
python scripts/deployment/rollback_core_deployment.py \
  --config config/core_deployment/core_production_config.yaml \
  --to-version previous \
  --reason "deployment_failure"
```

#### Manual Rollback

```bash
# Stop current service
sudo systemctl stop scenario-tracking

# Restore previous configuration
git checkout previous-stable-tag -- config/

# Restore database schema if needed
python scripts/deployment/restore_schema.py \
  --backup-version previous \
  --table-suffix="${SCENARIO_TRACKING_TABLE_SUFFIX}"

# Start service with previous configuration  
sudo systemctl start scenario-tracking

# Verify rollback success
python scripts/deployment/validate_core_deployment.py
```

## Environment-Specific Deployment

### Production Deployment

```bash
#!/bin/bash
# deploy_production.sh

set -e  # Exit on any error

echo "🚀 Starting production deployment..."

# Load production environment
source /etc/scenario_tracking/production.env

# Pre-deployment validation
echo "📋 Running pre-deployment validation..."
python scripts/testing/validate_core_production_readiness.py \
  --table-suffix="_prod_validation" \
  --output validation_results.json

# Deploy core system
echo "⚙️ Deploying core system..."
python scripts/deployment/deploy_core_scenario_tracking.py \
  --config config/core_deployment/core_production_config.yaml

# Post-deployment validation
echo "✅ Running post-deployment validation..."
python scripts/deployment/validate_core_deployment.py

# Run integration tests
echo "🧪 Running integration tests..."
python scripts/testing/run_core_integration_tests.py \
  --table-suffix="_prod_test"

echo "🎉 Production deployment completed successfully!"
```

### Staging Deployment

```bash
#!/bin/bash
# deploy_staging.sh

set -e

echo "🚀 Starting staging deployment..."

# Load staging environment
source /etc/scenario_tracking/staging.env

# Deploy with staging configuration
python scripts/deployment/deploy_core_scenario_tracking.py \
  --config config/core_deployment/core_staging_config.yaml \
  --table-suffix="_staging"

# Run comprehensive tests
python scripts/testing/run_core_integration_tests.py \
  --table-suffix="_staging_test" \
  --verbose

echo "🎉 Staging deployment completed successfully!"
```

### Development Deployment

```bash
#!/bin/bash
# deploy_development.sh

echo "🚀 Starting development deployment..."

# Use development configuration
export SCENARIO_TRACKING_TABLE_SUFFIX="_dev"

# Quick deployment for development
python scripts/deployment/deploy_core_scenario_tracking.py \
  --config config/core_deployment/core_development_config.yaml \
  --table-suffix="_dev" \
  --dry-run

# Minimal validation
python scripts/testing/run_core_integration_tests.py \
  --table-suffix="_dev_test" \
  --suite basic

echo "🎉 Development deployment completed!"
```

## Post-Deployment Tasks

### Health Monitoring Setup

```bash
# Set up automated health monitoring
cat > /etc/cron.d/scenario-tracking-health << EOF
# Monitor scenario tracking health every 5 minutes
*/5 * * * * $(whoami) /usr/bin/python3 $(pwd)/scripts/maintenance/health_monitor_core.py
EOF

# Set up log rotation
cat > /etc/logrotate.d/scenario-tracking << EOF
/var/log/scenario_tracking/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 $(whoami) $(whoami)
}
EOF
```

### Performance Baseline

```bash
# Establish performance baseline
python scripts/testing/run_core_integration_tests.py \
  --suite performance \
  --table-suffix="_baseline" \
  --output baseline_metrics.json

# Set up performance monitoring
cat > scripts/monitoring/check_performance.sh << 'EOF'
#!/bin/bash
python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def check_performance():
    async with InboxMonitorDatabricksClient() as client:
        metrics = await client.get_performance_metrics()
        
        # Check key metrics
        throughput = metrics.get('throughput', 0)
        success_rate = metrics.get('success_rate', 0)
        
        if throughput < 5:  # Below 5 records/second
            print(f'WARNING: Low throughput: {throughput}')
            
        if success_rate < 0.9:  # Below 90%
            print(f'WARNING: Low success rate: {success_rate:.2%}')

asyncio.run(check_performance())
"
EOF

chmod +x scripts/monitoring/check_performance.sh
```

### Documentation Updates

```bash
# Update deployment documentation with environment-specific details
cat > docs/deployment/ENVIRONMENT_SPECIFICS.md << EOF
# Environment-Specific Configuration

## Production
- Catalog: inbox_monitor_prod
- Schema: scenario_tracking
- Table Suffix: (none)
- Warehouse: prod-warehouse-id

## Staging  
- Catalog: inbox_monitor_staging
- Schema: scenario_tracking_staging
- Table Suffix: _staging
- Warehouse: staging-warehouse-id

## Development
- Catalog: inbox_monitor_dev
- Schema: scenario_tracking_dev
- Table Suffix: _dev
- Warehouse: dev-warehouse-id

Last Updated: $(date)
EOF
```

## Troubleshooting Deployment Issues

### Common Deployment Failures

#### Permission Issues
```bash
# Check OAuth permissions
python -c "
import asyncio
from services.databricks_oauth_client import DatabricksOAuthClient

async def test_permissions():
    try:
        client = DatabricksOAuthClient()
        token = await client.get_access_token()
        print('✅ OAuth authentication successful')
    except Exception as e:
        print(f'❌ OAuth authentication failed: {e}')

asyncio.run(test_permissions())
"
```

#### Network Connectivity
```bash
# Test network connectivity
curl -I "$DATABRICKS_HOST" || echo "❌ Cannot reach Databricks host"

# Test warehouse connectivity
python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def test_warehouse():
    try:
        pool = await get_connection_pool()
        async with pool.get_connection() as conn:
            result = await conn.execute_sql('SELECT 1')
            print('✅ Warehouse connectivity successful')
    except Exception as e:
        print(f'❌ Warehouse connectivity failed: {e}')

asyncio.run(test_warehouse())
"
```

#### Schema Deployment Issues
```bash
# Check if tables exist
python -c "
import asyncio
from services.scenario_tracking_client import ScenarioTrackingClient

async def check_tables():
    try:
        async with ScenarioTrackingClient() as client:
            await client.initialize_table()
            print('✅ Schema initialization successful')
    except Exception as e:
        print(f'❌ Schema initialization failed: {e}')

asyncio.run(check_tables())
"
```

### Deployment Logs

All deployment operations generate detailed logs:

```bash
# View deployment logs
tail -f /var/log/scenario_tracking/deployment.log

# Check for specific error patterns
grep -i error /var/log/scenario_tracking/deployment.log
grep -i warning /var/log/scenario_tracking/deployment.log
```

## Security Considerations

### Secrets Management

```bash
# Secure environment variables
chmod 600 /etc/scenario_tracking/production.env
chown root:root /etc/scenario_tracking/production.env

# Use HashiCorp Vault or Azure Key Vault for secrets
# Example with Azure Key Vault:
# az keyvault secret set --vault-name "scenario-tracking-vault" --name "databricks-oauth-secret" --value "$DATABRICKS_OAUTH_CLIENT_SECRET"
```

### Network Security

```bash
# Configure firewall rules
# Allow outbound HTTPS to Databricks
sudo ufw allow out 443

# Restrict inbound access to monitoring ports only
sudo ufw allow from monitoring-subnet to any port 8080
```

### Audit Logging

```bash
# Enable audit logging
cat >> /etc/scenario_tracking/core_production_config.yaml << EOF
audit:
  enabled: true
  log_file: "/var/log/scenario_tracking/audit.log"
  log_level: "INFO"
  include_pii: false
EOF
```

This deployment guide provides comprehensive procedures for deploying the core scenario tracking system across all environments with proper validation, monitoring, and security measures.