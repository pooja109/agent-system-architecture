# Core Troubleshooting Guide - Inbox Monitor Scenario Tracking

## Overview

This guide provides comprehensive troubleshooting procedures for the core scenario tracking system (Phases 1-3). It covers common issues, diagnostic procedures, and resolution steps for operations and development teams.

## Quick Diagnostic Commands

### System Health Check
```bash
# Overall system health
python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def quick_health():
    try:
        async with InboxMonitorDatabricksClient() as client:
            health = await client.get_health_status()
            print(f'Status: {health[\"status\"]}')
            
            # Check specific components
            checks = health.get('checks', {})
            for component, status in checks.items():
                print(f'{component}: {status.get(\"status\", \"unknown\")}')
                
            # Circuit breaker status
            cb = health.get('circuit_breaker', {})
            print(f'Circuit Breaker Open: {cb.get(\"is_open\", False)}')
            
    except Exception as e:
        print(f'CRITICAL: Health check failed - {e}')

asyncio.run(quick_health())
"
```

### Database Connectivity Test
```bash
# Test database connection
python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def test_db():
    try:
        pool = await get_connection_pool()
        async with pool.get_connection() as conn:
            result = await conn.execute_sql('SELECT CURRENT_TIMESTAMP() as test_time')
            row = result.fetchone()
            print(f'Database OK - Time: {row[\"test_time\"]}')
    except Exception as e:
        print(f'Database FAILED - {e}')

asyncio.run(test_db())
"
```

### Performance Metrics Check
```bash
# Get current performance metrics
python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def check_performance():
    try:
        async with InboxMonitorDatabricksClient() as client:
            metrics = await client.get_performance_metrics()
            print('Performance Metrics:')
            for key, value in metrics.items():
                print(f'  {key}: {value}')
    except Exception as e:
        print(f'Metrics unavailable: {e}')

asyncio.run(check_performance())
"
```

## Common Issues and Solutions

### Issue 1: Storage Operations Failing

#### Symptoms
- `store_scenario_processing_record()` returns `False`
- Log messages: "Storage failed but didn't raise exception"
- Health check shows database connectivity issues

#### Diagnosis
```bash
# Check database connectivity
python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def diagnose_storage():
    async with InboxMonitorDatabricksClient() as client:
        # Test connection
        conn_test = await client.test_connection()
        print(f'Connection Test: {conn_test}')
        
        # Check health
        health = await client.get_health_status()
        db_check = health.get('checks', {}).get('database_connectivity', {})
        print(f'DB Health: {db_check.get(\"status\", \"unknown\")}')
        
        if 'response_time_ms' in db_check:
            print(f'Response Time: {db_check[\"response_time_ms\"]}ms')

asyncio.run(diagnose_storage())
"
```

#### Resolution Steps

1. **Check Environment Variables**
   ```bash
   echo "DATABRICKS_HOST: $DATABRICKS_HOST"
   echo "DATABRICKS_WAREHOUSE_ID: $DATABRICKS_WAREHOUSE_ID"
   echo "DATABRICKS_OAUTH_CLIENT_ID: $DATABRICKS_OAUTH_CLIENT_ID"
   echo "DATABRICKS_OAUTH_CLIENT_SECRET: [SET: $([ -n \"$DATABRICKS_OAUTH_CLIENT_SECRET\" ] && echo 'YES' || echo 'NO')]"
   ```

2. **Verify OAuth Token**
   ```bash
   python -c "
   import asyncio
   from services.databricks_oauth_client import DatabricksOAuthClient
   
   async def test_oauth():
       try:
           client = DatabricksOAuthClient()
           token = await client.get_access_token()
           print('OAuth token obtained successfully')
       except Exception as e:
           print(f'OAuth failed: {e}')
   
   asyncio.run(test_oauth())
   "
   ```

3. **Check Table Existence**
   ```bash
   python -c "
   import asyncio
   from services.scenario_tracking_client import ScenarioTrackingClient
   
   async def check_table():
       try:
           async with ScenarioTrackingClient() as client:
               success = await client.initialize_table()
               print(f'Table initialization: {success}')
       except Exception as e:
           print(f'Table check failed: {e}')
   
   asyncio.run(check_table())
   "
   ```

4. **Reset Circuit Breaker** (if applicable)
   ```bash
   python -c "
   import asyncio
   from services.scenario_tracking_client import ScenarioTrackingClient
   
   async def reset_cb():
       client = ScenarioTrackingClient()
       client._reset_circuit_breaker()
       print('Circuit breaker reset')
   
   asyncio.run(reset_cb())
   "
   ```

### Issue 2: Circuit Breaker Activated

#### Symptoms
- `ServiceUnavailableError: Service circuit breaker is open`
- Health check shows circuit breaker failures
- All storage operations rejected

#### Diagnosis
```bash
# Check circuit breaker status
python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def diagnose_cb():
    async with InboxMonitorDatabricksClient() as client:
        health = await client.get_health_status()
        cb = health.get('circuit_breaker', {})
        
        print(f'Circuit Breaker Status:')
        print(f'  Failures: {cb.get(\"failures\", 0)}')
        print(f'  Is Open: {cb.get(\"is_open\", False)}')
        print(f'  Threshold: 5 (default)')

asyncio.run(diagnose_cb())
"
```

#### Resolution Steps

1. **Identify Root Cause**
   ```bash
   # Check recent error logs
   tail -n 50 /var/log/scenario_tracking/*.log | grep -A 5 -B 5 "circuit breaker"
   ```

2. **Resolve Underlying Issues**
   - Fix database connectivity issues
   - Resolve authentication problems
   - Address network connectivity

3. **Manual Reset** (after fixing root cause)
   ```bash
   python -c "
   import asyncio
   from services.scenario_tracking_client import ScenarioTrackingClient
   
   async def force_reset():
       client = ScenarioTrackingClient()
       client._circuit_breaker_failures = 0
       client._circuit_breaker_last_failure = None
       print('Circuit breaker manually reset')
   
   asyncio.run(force_reset())
   "
   ```

4. **Test Recovery**
   ```bash
   python -c "
   import asyncio
   from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
   from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
   from datetime import datetime, timezone
   
   async def test_recovery():
       test_record = ScenarioProcessingRecord(
           process_id='recovery_test',
           email_id='test_recovery',
           sender_email='test@recovery.com',
           received_datetime=datetime.now(timezone.utc),
           process_success=True,
           scenario_type=ScenarioType.SCENARIO_5,
           test_mode=True
       )
       
       async with InboxMonitorDatabricksClient() as client:
           result = await client.store_scenario_processing_record(test_record)
           print(f'Recovery test result: {result}')
   
   asyncio.run(test_recovery())
   "
   ```

### Issue 3: Poor Performance / High Latency

#### Symptoms
- Storage operations taking >2 seconds
- High response times in health checks
- Performance metrics showing degradation

#### Diagnosis
```bash
# Performance analysis
python -c "
import asyncio
import time
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from datetime import datetime, timezone

async def performance_test():
    test_record = ScenarioProcessingRecord(
        process_id='perf_test',
        email_id='perf_test_email',
        sender_email='perf@test.com',
        received_datetime=datetime.now(timezone.utc),
        process_success=True,
        scenario_type=ScenarioType.SCENARIO_5,
        test_mode=True
    )
    
    async with InboxMonitorDatabricksClient() as client:
        # Test health check performance
        start = time.time()
        health = await client.get_health_status()
        health_time = (time.time() - start) * 1000
        print(f'Health check time: {health_time:.2f}ms')
        
        # Test storage performance
        start = time.time()
        result = await client.store_scenario_processing_record(test_record)
        storage_time = (time.time() - start) * 1000
        print(f'Storage time: {storage_time:.2f}ms')
        print(f'Storage result: {result}')

asyncio.run(performance_test())
"
```

#### Resolution Steps

1. **Check Database Load**
   ```sql
   -- Run in Databricks SQL
   SELECT 
     query_start_time,
     execution_duration,
     query_text
   FROM system.query.history 
   WHERE warehouse_id = 'your-warehouse-id'
   AND query_start_time >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR
   ORDER BY execution_duration DESC
   LIMIT 10;
   ```

2. **Optimize Batch Processing**
   ```bash
   # Check batch queue status
   python -c "
   import asyncio
   from services.scenario_tracking_client import ScenarioTrackingClient
   
   async def check_batching():
       client = ScenarioTrackingClient()
       queue_size = len(client._batch_insert_queue)
       batch_size = client.config.batch_insert_size
       
       print(f'Batch queue size: {queue_size}')
       print(f'Batch size limit: {batch_size}')
       
       if queue_size > batch_size * 0.8:
           print('WARNING: Batch queue approaching capacity')
           await client.flush_pending_inserts()
           print('Batch queue flushed')
   
   asyncio.run(check_batching())
   "
   ```

3. **Database Optimization**
   ```sql
   -- Optimize tables
   OPTIMIZE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing;
   
   -- Update statistics
   ANALYZE TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
   COMPUTE STATISTICS;
   ```

4. **Configuration Tuning**
   ```python
   # Adjust configuration for higher performance
   # In config/core_production_config.py
   CORE_PRODUCTION_CONFIG["SCENARIO_TRACKING_CONFIG"].update({
       "batch_insert_size": 100,  # Increase batch size
       "connection_timeout_seconds": 60,  # Increase timeout
   })
   
   CORE_PRODUCTION_CONFIG["DATABRICKS_CONFIG"]["connection_pool"].update({
       "max_connections": 12,  # Increase connection pool
   })
   ```

### Issue 4: Data Validation Errors

#### Symptoms
- `DataValidationError` exceptions
- Records not being stored
- Validation error messages in logs

#### Diagnosis
```bash
# Test data validation
python -c "
from database.scenario_tracking_models import ScenarioProcessingRecord, ScenarioType
from datetime import datetime, timezone
from pydantic import ValidationError

# Test various validation scenarios
test_cases = [
    {
        'name': 'missing_required_field',
        'data': {
            # Missing process_id
            'email_id': 'test',
            'sender_email': 'test@example.com',
            'received_datetime': datetime.now(timezone.utc),
            'process_success': True
        }
    },
    {
        'name': 'invalid_email',
        'data': {
            'process_id': 'test',
            'email_id': 'test',
            'sender_email': 'not-an-email',
            'received_datetime': datetime.now(timezone.utc),
            'process_success': True
        }
    },
    {
        'name': 'invalid_datetime',
        'data': {
            'process_id': 'test',
            'email_id': 'test',
            'sender_email': 'test@example.com',
            'received_datetime': 'not-a-datetime',
            'process_success': True
        }
    }
]

for test_case in test_cases:
    try:
        record = ScenarioProcessingRecord(**test_case['data'])
        print(f'{test_case[\"name\"]}: PASS')
    except ValidationError as e:
        print(f'{test_case[\"name\"]}: FAIL - {e}')
"
```

#### Resolution Steps

1. **Check Field Requirements**
   ```python
   # Review required fields
   from database.scenario_tracking_models import ScenarioProcessingRecord
   
   # Get field information
   fields = ScenarioProcessingRecord.__fields__
   required_fields = [name for name, field in fields.items() if field.required]
   print("Required fields:", required_fields)
   ```

2. **Validate Email Formats**
   ```python
   import re
   
   def validate_email(email):
       pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
       return re.match(pattern, email) is not None
   
   # Test email validation
   test_emails = ['valid@example.com', 'invalid-email', 'test@']
   for email in test_emails:
       print(f'{email}: {"VALID" if validate_email(email) else "INVALID"}')
   ```

3. **Fix Data Length Issues**
   ```python
   # Check field length limits
   test_data = {
       'subject': 'A' * 600,  # Too long
       'email_body': 'B' * 300,  # Too long
   }
   
   # Truncate if needed
   max_lengths = {'subject': 500, 'email_body': 255}
   for field, value in test_data.items():
       if len(value) > max_lengths.get(field, 1000):
           print(f'{field} too long: {len(value)} > {max_lengths[field]}')
   ```

### Issue 5: Import Path Issues

#### Symptoms
- `ImportError` or `ModuleNotFoundError`
- Tests failing to run
- Service startup failures

#### Diagnosis
```bash
# Check Python path and imports
python -c "
import sys
print('Python path:')
for path in sys.path:
    print(f'  {path}')

print('\nTesting imports:')
try:
    from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
    print('✓ InboxMonitorDatabricksClient imported successfully')
except ImportError as e:
    print(f'✗ InboxMonitorDatabricksClient import failed: {e}')

try:
    from database.scenario_tracking_models import ScenarioProcessingRecord
    print('✓ ScenarioProcessingRecord imported successfully')
except ImportError as e:
    print(f'✗ ScenarioProcessingRecord import failed: {e}')

try:
    from services.scenario_tracking_client import ScenarioTrackingClient
    print('✓ ScenarioTrackingClient imported successfully')
except ImportError as e:
    print(f'✗ ScenarioTrackingClient import failed: {e}')
"
```

#### Resolution Steps

1. **Set PYTHONPATH**
   ```bash
   export PYTHONPATH=/path/to/agents/inbox_monitor:$PYTHONPATH
   ```

2. **Use Relative Imports in Tests**
   ```python
   # In test files, use relative imports
   try:
       from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
   except ImportError:
       from ..services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient
   ```

3. **Install in Development Mode**
   ```bash
   cd agents/inbox_monitor
   pip install -e .
   ```

### Issue 6: Memory Leaks / Resource Issues

#### Symptoms
- Gradually increasing memory usage
- Connection pool exhaustion
- Background tasks not terminating

#### Diagnosis
```bash
# Check resource usage
python -c "
import asyncio
import psutil
import gc
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def check_resources():
    process = psutil.Process()
    
    print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB')
    print(f'Open files: {len(process.open_files())}')
    print(f'Threads: {process.num_threads()}')
    
    # Check garbage collection
    gc.collect()
    print(f'Garbage objects: {len(gc.get_objects())}')

asyncio.run(check_resources())
"
```

#### Resolution Steps

1. **Ensure Proper Context Manager Usage**
   ```python
   # CORRECT - Always use context manager
   async with InboxMonitorDatabricksClient() as client:
       await client.store_scenario_processing_record(record)
   
   # INCORRECT - Manual cleanup required
   client = InboxMonitorDatabricksClient()
   await client.__aenter__()
   try:
       await client.store_scenario_processing_record(record)
   finally:
       await client.__aexit__(None, None, None)
   ```

2. **Check Background Task Cleanup**
   ```bash
   python -c "
   import asyncio
   from services.scenario_tracking_client import ScenarioTrackingClient
   
   async def check_tasks():
       client = ScenarioTrackingClient()
       
       # Check if background task exists
       if hasattr(client, '_background_batch_task') and client._background_batch_task:
           print(f'Background task status: {client._background_batch_task.done()}')
           if not client._background_batch_task.done():
               print('WARNING: Background task still running')
       
       await client.close()
       print('Client closed properly')
   
   asyncio.run(check_tasks())
   "
   ```

3. **Monitor Connection Pool**
   ```bash
   python -c "
   import asyncio
   from services.databricks_connection_pool import get_connection_pool
   
   async def check_pool():
       pool = await get_connection_pool()
       # Add pool monitoring if available
       print('Connection pool status checked')
   
   asyncio.run(check_pool())
   "
   ```

## Diagnostic Queries

### Database Health Queries
```sql
-- Check recent activity
SELECT 
  DATE(processed_at) as date,
  COUNT(*) as total_records,
  COUNT(CASE WHEN process_success THEN 1 END) as successful,
  AVG(processing_duration_ms) as avg_processing_time
FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
GROUP BY DATE(processed_at);

-- Check error patterns
SELECT 
  process_error,
  COUNT(*) as error_count
FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
WHERE process_success = false
  AND processed_at >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
GROUP BY process_error
ORDER BY error_count DESC;

-- Check table size and partitions
DESCRIBE DETAIL inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing;
```

### Performance Analysis Queries
```sql
-- Slowest processing times
SELECT 
  process_id,
  email_id,
  processing_duration_ms,
  scenario_type,
  processed_at
FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
WHERE processing_duration_ms > 1000
  AND processed_at >= CURRENT_TIMESTAMP() - INTERVAL 1 HOUR
ORDER BY processing_duration_ms DESC;

-- Success rate by hour
SELECT 
  DATE_TRUNC('hour', processed_at) as hour,
  COUNT(*) as total,
  COUNT(CASE WHEN process_success THEN 1 END) as successful,
  COUNT(CASE WHEN process_success THEN 1 END) * 100.0 / COUNT(*) as success_rate
FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
WHERE processed_at >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
GROUP BY DATE_TRUNC('hour', processed_at)
ORDER BY hour DESC;
```

## Emergency Procedures

### Complete Service Restart
```bash
#!/bin/bash
echo "Emergency service restart procedure"

# 1. Stop the service
systemctl stop inbox-monitor

# 2. Clear any stuck processes
pkill -f "inbox_monitor"

# 3. Clear temporary files if any
rm -f /tmp/scenario_tracking_*

# 4. Start the service
systemctl start inbox-monitor

# 5. Wait for startup
sleep 10

# 6. Verify health
python /path/to/scripts/maintenance/health_monitor_core.py

echo "Emergency restart complete"
```

### Failover to Backup System
```bash
#!/bin/bash
echo "Initiating failover to backup system"

# 1. Stop primary service
systemctl stop inbox-monitor

# 2. Switch DNS or load balancer to backup
# (Implementation depends on infrastructure)

# 3. Start backup service
ssh backup-server "systemctl start inbox-monitor-backup"

# 4. Verify backup is healthy
ssh backup-server "python scripts/maintenance/health_monitor_core.py"

echo "Failover complete"
```

This troubleshooting guide provides comprehensive procedures for diagnosing and resolving issues with the core scenario tracking system.