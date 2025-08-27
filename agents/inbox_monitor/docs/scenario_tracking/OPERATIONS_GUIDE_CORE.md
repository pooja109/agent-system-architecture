# Core Operations Guide - Inbox Monitor Scenario Tracking

## Overview

This guide provides operational procedures for managing the core scenario tracking system (Phases 1-3) in production environments. It covers deployment, monitoring, maintenance, and troubleshooting procedures for operations teams.

## System Architecture

### Core Components
- **Database Layer**: Databricks Delta tables with Unity Catalog
- **Service Layer**: InboxMonitorDatabricksClient and ScenarioTrackingClient
- **Data Models**: Pydantic models with validation
- **Connection Pool**: Managed database connections with retry logic
- **Circuit Breaker**: Automatic failure handling and recovery

### Data Flow
1. Email processing triggers scenario classification
2. Scenario results are stored via InboxMonitorDatabricksClient
3. Data is persisted to Databricks Delta tables
4. Analytics and monitoring query stored data
5. Health checks monitor system status

## Deployment Procedures

### Pre-Deployment Checklist

1. **Environment Variables**
   ```bash
   export DATABRICKS_HOST="your-databricks-host"
   export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"
   export DATABRICKS_OAUTH_CLIENT_ID="your-oauth-client-id"
   export DATABRICKS_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
   export DATABRICKS_CATALOG="inbox_monitor"
   export DATABRICKS_SCHEMA="scenario_tracking"
   ```

2. **Dependency Verification**
   ```bash
   pip install pydantic structlog databricks-sql-connector
   python -c "import pydantic, structlog; print('Dependencies OK')"
   ```

3. **Database Connectivity**
   ```bash
   python -c "
   import asyncio
   from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
   
   async def test():
       async with InboxMonitorDatabricksClient() as client:
           result = await client.test_connection()
           print(f'Connection test: {result}')
   
   asyncio.run(test())
   "
   ```

### Deployment Steps

1. **Run Production Readiness Validation**
   ```bash
   cd agents/inbox_monitor
   python scripts/testing/validate_core_production_readiness.py \
     --table-suffix="_prod" \
     --output validation_results.json
   ```

2. **Deploy Core System**
   ```bash
   python scripts/deployment/deploy_core_scenario_tracking.py \
     --config config/core_production_config.yaml \
     --table-suffix="_prod"
   ```

3. **Validate Deployment**
   ```bash
   python scripts/deployment/validate_core_deployment.py \
     --table-suffix="_prod"
   ```

4. **Run Integration Tests**
   ```bash
   python scripts/testing/run_core_integration_tests.py \
     --table-suffix="_prod_test" \
     --verbose
   ```

### Environment-Specific Configurations

#### Production Environment
```yaml
# config/core_production_config.yaml
database:
  catalog: "inbox_monitor_prod"
  schema: "scenario_tracking"
  warehouse_id: "${DATABRICKS_WAREHOUSE_ID}"

core_deployment:
  log_directory: "/var/log/scenario_tracking"
  enable_performance_monitoring: true

scenario_tracking:
  batch_insert_size: 50
  async_insert: true
  retry_attempts: 3
```

#### Staging Environment
```yaml
# config/core_staging_config.yaml
database:
  catalog: "inbox_monitor_staging"
  schema: "scenario_tracking_staging"
  warehouse_id: "${DATABRICKS_WAREHOUSE_ID}"

core_deployment:
  log_directory: "/var/log/scenario_tracking_staging"
  enable_performance_monitoring: true

scenario_tracking:
  batch_insert_size: 25
  async_insert: true
  retry_attempts: 3
```

#### Development Environment
```yaml
# config/core_development_config.yaml
database:
  catalog: "inbox_monitor_dev"
  schema: "scenario_tracking_dev"
  warehouse_id: "${DATABRICKS_WAREHOUSE_ID}"

scenario_tracking:
  batch_insert_size: 10
  async_insert: false  # Synchronous for debugging
  retry_attempts: 1
```

## Monitoring and Health Checks

### Health Check Endpoints

The system provides comprehensive health monitoring:

```python
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async with InboxMonitorDatabricksClient() as client:
    health = await client.get_health_status()
    print(f"Service status: {health['status']}")
```

### Health Check Response Format
```json
{
  "service_name": "scenario_tracking_client",
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "checks": {
    "database_connectivity": {
      "status": "healthy",
      "response_time_ms": 45.2,
      "table_name": "inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing"
    },
    "batch_queue": {
      "status": "healthy",
      "queue_size": 5,
      "max_size": 100
    }
  },
  "metrics": {
    "total_operations": 1000,
    "success_rate": 0.97,
    "average_response_time_ms": 120.5
  },
  "circuit_breaker": {
    "failures": 0,
    "is_open": false
  }
}
```

### Monitoring Scripts

#### Automated Health Monitoring
```bash
#!/bin/bash
# scripts/maintenance/health_monitor_core.py

python3 << EOF
import asyncio
import json
from datetime import datetime
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def monitor_health():
    async with InboxMonitorDatabricksClient() as client:
        health = await client.get_health_status()
        
        status = health.get('status', 'unknown')
        timestamp = datetime.now().isoformat()
        
        print(f"[{timestamp}] Health Status: {status}")
        
        if status != 'healthy':
            print(f"[{timestamp}] WARNING: Service unhealthy")
            print(json.dumps(health, indent=2))
            exit(1)
        else:
            print(f"[{timestamp}] Service operating normally")
            
        # Check performance metrics
        metrics = health.get('metrics', {})
        success_rate = metrics.get('success_rate', 0)
        
        if success_rate < 0.9:
            print(f"[{timestamp}] WARNING: Success rate below threshold: {success_rate:.2%}")
            exit(1)

asyncio.run(monitor_health())
EOF
```

#### Performance Monitoring
```bash
# Monitor performance metrics every 5 minutes
*/5 * * * * /path/to/agents/inbox_monitor/scripts/maintenance/health_monitor_core.py
```

### Key Performance Indicators (KPIs)

1. **Storage Throughput**: Target 8+ records/second
2. **Success Rate**: Target 90%+ under normal conditions
3. **Response Time**: Target <500ms average
4. **Circuit Breaker Status**: Should remain closed
5. **Queue Size**: Should remain under batch size limit

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Success Rate | < 95% | < 90% |
| Response Time | > 1000ms | > 2000ms |
| Circuit Breaker | Failures > 3 | Circuit Open |
| Queue Size | > 75% capacity | > 90% capacity |
| Database Connectivity | Response > 500ms | Connection Failed |

## Maintenance Procedures

### Daily Maintenance

1. **Health Check Verification**
   ```bash
   python scripts/maintenance/health_monitor_core.py
   ```

2. **Performance Metrics Review**
   ```bash
   python -c "
   import asyncio
   from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
   
   async def get_metrics():
       async with InboxMonitorDatabricksClient() as client:
           metrics = await client.get_performance_metrics()
           print('Performance Metrics:')
           for key, value in metrics.items():
               print(f'  {key}: {value}')
   
   asyncio.run(get_metrics())
   "
   ```

3. **Error Log Review**
   ```bash
   tail -n 100 /var/log/scenario_tracking/scenario_tracking.log | grep ERROR
   ```

### Weekly Maintenance

1. **Data Cleanup**
   ```bash
   python scripts/maintenance/data_cleanup_core.py \
     --retention-days 30 \
     --table-suffix="_prod"
   ```

2. **Performance Benchmarks**
   ```bash
   python scripts/testing/run_core_integration_tests.py \
     --suite performance \
     --table-suffix="_benchmark"
   ```

3. **Database Optimization**
   ```sql
   -- Run in Databricks SQL
   OPTIMIZE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing;
   ANALYZE TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing 
   COMPUTE STATISTICS;
   ```

### Monthly Maintenance

1. **Full Integration Testing**
   ```bash
   python scripts/testing/run_core_integration_tests.py \
     --table-suffix="_monthly_test" \
     --verbose \
     --output monthly_test_results.json
   ```

2. **Capacity Planning Review**
   ```sql
   -- Check table size growth
   DESCRIBE DETAIL inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing;
   
   -- Check record count trends
   SELECT 
     DATE(processed_at) as date,
     COUNT(*) as daily_records,
     AVG(processing_duration_ms) as avg_processing_time
   FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
   WHERE processed_at >= CURRENT_DATE() - INTERVAL 30 DAYS
   GROUP BY DATE(processed_at)
   ORDER BY date DESC;
   ```

3. **Security Audit**
   ```bash
   python scripts/testing/validate_core_production_readiness.py \
     --table-suffix="_prod" \
     --output security_audit.json
   ```

## Backup and Recovery

### Backup Procedures

1. **Automated Delta Table Backup**
   ```sql
   -- Create backup table
   CREATE TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing_backup_YYYYMMDD
   AS SELECT * FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing;
   ```

2. **Configuration Backup**
   ```bash
   tar -czf config_backup_$(date +%Y%m%d).tar.gz config/
   cp config_backup_*.tar.gz /backup/location/
   ```

3. **Export Recent Data**
   ```python
   # scripts/backup/export_recent_data.py
   import asyncio
   from services.scenario_tracking_client import ScenarioTrackingClient
   
   async def export_data():
       async with ScenarioTrackingClient() as client:
           analytics = await client.get_scenario_analytics(days_back=7)
           # Save analytics to backup location
   
   asyncio.run(export_data())
   ```

### Recovery Procedures

1. **Service Recovery**
   ```bash
   # Stop service
   systemctl stop inbox-monitor
   
   # Restore configuration
   tar -xzf config_backup_YYYYMMDD.tar.gz
   
   # Restart service
   systemctl start inbox-monitor
   
   # Verify health
   python scripts/maintenance/health_monitor_core.py
   ```

2. **Data Recovery**
   ```sql
   -- Restore from backup table
   INSERT INTO inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
   SELECT * FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing_backup_YYYYMMDD
   WHERE processed_at > 'recovery_point_timestamp';
   ```

3. **Point-in-Time Recovery**
   ```sql
   -- Use Delta Lake time travel
   SELECT * FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
   VERSION AS OF 'recovery_version_number';
   ```

## Rollback Procedures

### Automated Rollback
```bash
python scripts/deployment/rollback_core_deployment.py \
  --config config/core_production_config.yaml \
  --to-version previous
```

### Manual Rollback Steps

1. **Stop Current Service**
   ```bash
   systemctl stop inbox-monitor
   ```

2. **Restore Previous Configuration**
   ```bash
   git checkout previous-stable-tag -- config/
   ```

3. **Rollback Database Schema** (if needed)
   ```sql
   -- Revert schema changes
   ALTER TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
   DROP COLUMN IF EXISTS new_column;
   ```

4. **Restart Service**
   ```bash
   systemctl start inbox-monitor
   ```

5. **Verify Rollback**
   ```bash
   python scripts/deployment/validate_core_deployment.py
   ```

## Troubleshooting

### Common Issues

#### High Error Rate
```bash
# Check circuit breaker status
python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def check_cb():
    async with InboxMonitorDatabricksClient() as client:
        health = await client.get_health_status()
        cb = health.get('circuit_breaker', {})
        print(f'Circuit Breaker - Failures: {cb.get(\"failures\", 0)}, Open: {cb.get(\"is_open\", False)}')

asyncio.run(check_cb())
"

# Reset circuit breaker if needed
python -c "
import asyncio
from services.scenario_tracking_client import ScenarioTrackingClient

async def reset_cb():
    async with ScenarioTrackingClient() as client:
        client._reset_circuit_breaker()
        print('Circuit breaker reset')

asyncio.run(reset_cb())
"
```

#### Database Connection Issues
```bash
# Test connectivity
python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def test_conn():
    try:
        pool = await get_connection_pool()
        async with pool.get_connection() as conn:
            result = await conn.execute_sql('SELECT 1 as test')
            print('Database connection successful')
    except Exception as e:
        print(f'Database connection failed: {e}')

asyncio.run(test_conn())
"
```

#### Performance Degradation
```bash
# Check batch queue status
python -c "
import asyncio
from services.scenario_tracking_client import ScenarioTrackingClient

async def check_queue():
    client = ScenarioTrackingClient()
    queue_size = len(client._batch_insert_queue)
    print(f'Batch queue size: {queue_size}')
    
    if queue_size > 50:
        print('WARNING: Large batch queue detected')
        await client.flush_pending_inserts()
        print('Batch queue flushed')

asyncio.run(check_queue())
"
```

### Log Analysis

#### Important Log Patterns

1. **Normal Operations**
   ```
   INFO - Scenario processing record stored successfully
   DEBUG - Background batch processed successfully
   INFO - Health check completed successfully
   ```

2. **Warning Conditions**
   ```
   WARNING - Storage failed but didn't raise exception
   WARNING - Circuit breaker activated
   WARNING - Batch queue size approaching limit
   ```

3. **Error Conditions**
   ```
   ERROR - Database connection failed
   ERROR - Batch processing failed
   ERROR - Circuit breaker open - requests rejected
   ```

#### Log Aggregation Queries
```bash
# Error summary
grep ERROR /var/log/scenario_tracking/*.log | \
  awk '{print $3}' | sort | uniq -c | sort -rn

# Performance metrics
grep "processing_duration_ms" /var/log/scenario_tracking/*.log | \
  tail -100 | grep -o "processing_duration_ms=[0-9]*" | \
  awk -F= '{sum+=$2; count++} END {print "Average:", sum/count, "ms"}'
```

## Performance Tuning

### Configuration Tuning

1. **Batch Size Optimization**
   ```python
   # Test different batch sizes
   batch_sizes = [25, 50, 100, 200]
   for size in batch_sizes:
       # Benchmark with different batch sizes
       # Optimal: 50-100 for most workloads
   ```

2. **Connection Pool Tuning**
   ```python
   # Adjust based on workload
   CORE_PRODUCTION_CONFIG["DATABRICKS_CONFIG"]["connection_pool"] = {
       "max_connections": 8,  # Increase for high throughput
       "connection_timeout": 30,
       "retry_attempts": 3
   }
   ```

3. **Circuit Breaker Tuning**
   ```python
   # Adjust thresholds based on reliability requirements
   client._circuit_breaker_threshold = 5  # Failure threshold
   client._circuit_breaker_timeout = 300  # Recovery timeout
   ```

This operations guide provides comprehensive procedures for managing the core scenario tracking system in production environments.