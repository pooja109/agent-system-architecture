# Core Rollback Procedures - Inbox Monitor Scenario Tracking

## Overview

This document provides comprehensive rollback procedures for the core scenario tracking system (Phases 1-3). It covers automated and manual rollback procedures, data recovery, and emergency response protocols.

## Rollback Strategy

### Rollback Triggers

Initiate rollback procedures when:

1. **Service Health Failures**
   - Health checks fail for >5 minutes
   - Success rate drops below 80%
   - Database connectivity failures

2. **Performance Degradation**
   - Response times >3 seconds consistently
   - Throughput drops below 3 records/second
   - Circuit breaker activation

3. **Data Integrity Issues**
   - Data validation failures increase >10%
   - Corrupted records detected
   - Schema inconsistencies

4. **Security Incidents**
   - Unauthorized access detected
   - Data leakage incidents
   - Authentication failures

### Rollback Types

1. **Configuration Rollback**: Revert configuration changes only
2. **Service Rollback**: Restart with previous service version
3. **Schema Rollback**: Revert database schema changes
4. **Full Rollback**: Complete system restoration to previous state

## Automated Rollback Procedures

### Quick Rollback Script

```bash
#!/bin/bash
# scripts/deployment/quick_rollback.sh

set -e

ROLLBACK_REASON="${1:-manual_trigger}"
ROLLBACK_VERSION="${2:-previous}"

echo "🔄 Initiating automated rollback..."
echo "Reason: $ROLLBACK_REASON"
echo "Target Version: $ROLLBACK_VERSION"

# Execute automated rollback
python scripts/deployment/rollback_core_deployment.py \
  --config config/core_deployment/core_production_config.yaml \
  --to-version "$ROLLBACK_VERSION" \
  --reason "$ROLLBACK_REASON" \
  --auto-confirm

# Verify rollback success
if [ $? -eq 0 ]; then
  echo "✅ Automated rollback completed successfully"
  
  # Run health check
  python scripts/maintenance/health_monitor_core.py
  
  # Send notification (optional)
  # slack_notify "Rollback completed successfully" "success"
else
  echo "❌ Automated rollback failed - manual intervention required"
  exit 1
fi
```

### Rollback with Health Monitoring

```bash
#!/bin/bash
# scripts/deployment/monitored_rollback.sh

HEALTH_CHECK_INTERVAL=30  # seconds
MAX_HEALTH_CHECKS=10

echo "🔄 Starting monitored rollback procedure..."

# Function to check system health
check_health() {
  python -c "
import asyncio
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def health_check():
    try:
        async with InboxMonitorDatabricksClient() as client:
            health = await client.get_health_status()
            status = health.get('status', 'unknown')
            return status == 'healthy'
    except Exception:
        return False

result = asyncio.run(health_check())
exit(0 if result else 1)
"
}

# Execute rollback
python scripts/deployment/rollback_core_deployment.py \
  --config config/core_deployment/core_production_config.yaml \
  --to-version previous \
  --reason "automated_health_trigger"

# Monitor health post-rollback
echo "🔍 Monitoring system health post-rollback..."

for i in $(seq 1 $MAX_HEALTH_CHECKS); do
  echo "Health check $i/$MAX_HEALTH_CHECKS..."
  
  if check_health; then
    echo "✅ System healthy after rollback"
    break
  else
    echo "⏳ System not healthy yet, waiting..."
    sleep $HEALTH_CHECK_INTERVAL
    
    if [ $i -eq $MAX_HEALTH_CHECKS ]; then
      echo "❌ System still unhealthy after rollback - escalating"
      exit 1
    fi
  fi
done

echo "🎉 Monitored rollback completed successfully"
```

## Manual Rollback Procedures

### Step-by-Step Manual Rollback

#### Step 1: Assess Current State

```bash
# Document current system state before rollback
echo "📊 Documenting current system state..."

# Capture current configuration
cp -r config/ backup/config_$(date +%Y%m%d_%H%M%S)/

# Capture current database schema
python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def capture_schema():
    pool = await get_connection_pool()
    async with pool.get_connection() as conn:
        result = await conn.execute_sql_fetchall('''
            DESCRIBE DETAIL inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
        ''')
        
        with open('backup/current_schema.json', 'w') as f:
            import json
            json.dump([dict(row) for row in result], f, indent=2, default=str)
        
        print('Schema captured to backup/current_schema.json')

asyncio.run(capture_schema())
"

# Capture performance metrics
python scripts/maintenance/health_monitor_core.py > backup/pre_rollback_health.json

echo "📁 Current state documented in backup/ directory"
```

#### Step 2: Stop Current Service

```bash
echo "🛑 Stopping current service..."

# Stop systemd service if running
if systemctl is-active --quiet scenario-tracking; then
  sudo systemctl stop scenario-tracking
  echo "✅ Systemd service stopped"
fi

# Kill any remaining processes
pkill -f "scenario_tracking" || true

# Verify no processes running
if pgrep -f "scenario_tracking"; then
  echo "⚠️ Warning: Some processes still running"
  pgrep -f "scenario_tracking" | xargs ps -p
else
  echo "✅ All scenario tracking processes stopped"
fi
```

#### Step 3: Restore Previous Configuration

```bash
echo "📝 Restoring previous configuration..."

# Restore from git (if version controlled)
PREVIOUS_COMMIT=$(git log --oneline -n 2 | tail -1 | cut -d' ' -f1)
echo "Rolling back to commit: $PREVIOUS_COMMIT"

# Backup current config before restore
cp -r config/ backup/config_before_rollback_$(date +%Y%m%d_%H%M%S)/

# Restore previous configuration
git checkout $PREVIOUS_COMMIT -- config/

# Or restore from backup
# cp -r backup/config_known_good/* config/

echo "✅ Configuration restored"
```

#### Step 4: Restore Database Schema (if needed)

```bash
echo "🗄️ Checking database schema rollback requirements..."

# Check if schema changes need to be reverted
python -c "
import asyncio
import json
from services.databricks_connection_pool import get_connection_pool

async def check_schema_changes():
    # Compare current schema with backup
    try:
        with open('backup/known_good_schema.json', 'r') as f:
            target_schema = json.load(f)
        
        pool = await get_connection_pool()
        async with pool.get_connection() as conn:
            current_result = await conn.execute_sql_fetchall('''
                DESCRIBE DETAIL inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
            ''')
            current_schema = [dict(row) for row in current_result]
        
        # Simple comparison - in production, implement more sophisticated comparison
        if len(current_schema) != len(target_schema):
            print('SCHEMA_ROLLBACK_REQUIRED')
        else:
            print('NO_SCHEMA_ROLLBACK_NEEDED')
            
    except Exception as e:
        print(f'SCHEMA_CHECK_FAILED: {e}')

asyncio.run(check_schema_changes())
"

SCHEMA_STATUS=$?

if [ "$SCHEMA_STATUS" = "SCHEMA_ROLLBACK_REQUIRED" ]; then
  echo "⚠️ Schema rollback required - executing..."
  
  # Execute schema rollback
  python scripts/deployment/rollback_schema.py \
    --backup-file backup/known_good_schema.json \
    --table-suffix "${SCENARIO_TRACKING_TABLE_SUFFIX}"
    
  echo "✅ Schema rollback completed"
else
  echo "ℹ️ No schema rollback required"
fi
```

#### Step 5: Restart Service

```bash
echo "🚀 Restarting service with restored configuration..."

# Start systemd service
sudo systemctl start scenario-tracking

# Wait for service to start
sleep 10

# Check service status
if systemctl is-active --quiet scenario-tracking; then
  echo "✅ Service started successfully"
else
  echo "❌ Service failed to start"
  
  # Check logs for errors
  echo "📋 Recent service logs:"
  journalctl -u scenario-tracking --since "1 minute ago" --no-pager
  
  exit 1
fi
```

#### Step 6: Validate Rollback

```bash
echo "✅ Validating rollback success..."

# Run health checks
python scripts/maintenance/health_monitor_core.py

# Run basic integration tests
python scripts/testing/run_core_integration_tests.py \
  --table-suffix "_rollback_test" \
  --suite basic

# Compare performance with baseline
python -c "
import asyncio
import json
from services.inbox_monitor_databricks_client import InboxMonitorDatabricksClient

async def validate_performance():
    async with InboxMonitorDatabricksClient() as client:
        metrics = await client.get_performance_metrics()
        
        # Load baseline metrics
        try:
            with open('backup/baseline_metrics.json', 'r') as f:
                baseline = json.load(f)
            
            # Compare key metrics
            current_throughput = metrics.get('throughput', 0)
            baseline_throughput = baseline.get('throughput', 0)
            
            if current_throughput >= baseline_throughput * 0.8:  # 80% of baseline
                print('✅ Performance acceptable after rollback')
            else:
                print(f'⚠️ Performance degraded: {current_throughput} vs {baseline_throughput}')
                
        except FileNotFoundError:
            print('ℹ️ No baseline metrics available for comparison')

asyncio.run(validate_performance())
"

echo "🎉 Manual rollback completed successfully"
```

## Data Recovery Procedures

### Point-in-Time Recovery

```bash
#!/bin/bash
# scripts/recovery/point_in_time_recovery.sh

RECOVERY_TIMESTAMP="${1:-$(date -d '1 hour ago' --iso-8601=seconds)}"
BACKUP_SUFFIX="_recovery_$(date +%Y%m%d_%H%M%S)"

echo "🕐 Starting point-in-time recovery to: $RECOVERY_TIMESTAMP"

# Use Delta Lake time travel capabilities
python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def point_in_time_recovery():
    recovery_timestamp = '$RECOVERY_TIMESTAMP'
    backup_suffix = '$BACKUP_SUFFIX'
    
    pool = await get_connection_pool()
    async with pool.get_connection() as conn:
        # Create backup of current state
        await conn.execute_sql(f'''
            CREATE TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing{backup_suffix}
            AS SELECT * FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
        ''')
        
        # Restore to specific timestamp using Delta Lake time travel
        await conn.execute_sql(f'''
            RESTORE TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
            TO TIMESTAMP AS OF '{recovery_timestamp}'
        ''')
        
        print(f'✅ Point-in-time recovery completed to {recovery_timestamp}')
        print(f'📁 Current data backed up to: inbox_monitor_scenario_processing{backup_suffix}')

asyncio.run(point_in_time_recovery())
"
```

### Data Restoration from Backup

```bash
#!/bin/bash
# scripts/recovery/restore_from_backup.sh

BACKUP_TABLE="${1}"
RESTORE_MODE="${2:-replace}"  # replace or merge

if [ -z "$BACKUP_TABLE" ]; then
  echo "Usage: $0 <backup_table_name> [replace|merge]"
  exit 1
fi

echo "💾 Restoring data from backup table: $BACKUP_TABLE"
echo "Restore mode: $RESTORE_MODE"

python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def restore_from_backup():
    backup_table = '$BACKUP_TABLE'
    restore_mode = '$RESTORE_MODE'
    
    pool = await get_connection_pool()
    async with pool.get_connection() as conn:
        if restore_mode == 'replace':
            # Complete replacement
            await conn.execute_sql('DELETE FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing')
            await conn.execute_sql(f'''
                INSERT INTO inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
                SELECT * FROM {backup_table}
            ''')
            print('✅ Data replaced from backup')
            
        elif restore_mode == 'merge':
            # Merge only missing records
            await conn.execute_sql(f'''
                MERGE INTO inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing AS target
                USING {backup_table} AS source
                ON target.process_id = source.process_id
                WHEN NOT MATCHED THEN INSERT *
            ''')
            print('✅ Data merged from backup')
        
        # Verify restoration
        result = await conn.execute_sql_fetchone('''
            SELECT COUNT(*) as record_count 
            FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
        ''')
        
        print(f'📊 Total records after restoration: {result[\"record_count\"]}')

asyncio.run(restore_from_backup())
"
```

## Emergency Response Procedures

### Immediate Response Checklist

```bash
#!/bin/bash
# scripts/emergency/immediate_response.sh

echo "🚨 EMERGENCY RESPONSE PROCEDURE ACTIVATED"
echo "Timestamp: $(date)"

# 1. Stop all processing immediately
echo "1️⃣ Stopping all processing..."
sudo systemctl stop scenario-tracking
pkill -f "scenario_tracking"

# 2. Isolate the service
echo "2️⃣ Isolating service (blocking external access)..."
# Implement service isolation (firewall rules, load balancer removal, etc.)
# This is environment-specific

# 3. Capture system state
echo "3️⃣ Capturing system state for forensics..."
mkdir -p emergency_backup/$(date +%Y%m%d_%H%M%S)

# Capture logs
cp -r /var/log/scenario_tracking/ emergency_backup/$(date +%Y%m%d_%H%M%S)/logs/

# Capture configuration
cp -r config/ emergency_backup/$(date +%Y%m%d_%H%M%S)/config/

# Capture current database state
python -c "
import asyncio
from services.databricks_connection_pool import get_connection_pool

async def emergency_backup():
    try:
        pool = await get_connection_pool()
        async with pool.get_connection() as conn:
            # Create emergency backup table
            await conn.execute_sql('''
                CREATE TABLE inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing_emergency_backup_$(date +%Y%m%d_%H%M%S)
                AS SELECT * FROM inbox_monitor.scenario_tracking.inbox_monitor_scenario_processing
            ''')
            print('✅ Emergency database backup created')
    except Exception as e:
        print(f'❌ Emergency backup failed: {e}')

asyncio.run(emergency_backup())
"

# 4. Initiate rollback to last known good state
echo "4️⃣ Initiating emergency rollback..."
./scripts/deployment/quick_rollback.sh "emergency_response" "last_known_good"

# 5. Verify system security
echo "5️⃣ Running security verification..."
python scripts/security/emergency_security_check.py

echo "🚨 EMERGENCY RESPONSE COMPLETED"
echo "Next steps: Review logs, investigate root cause, implement fixes"
```

### Escalation Procedures

```bash
#!/bin/bash
# scripts/emergency/escalation.sh

INCIDENT_SEVERITY="${1:-high}"
INCIDENT_DESCRIPTION="${2:-Emergency rollback executed}"

echo "📢 Escalating incident..."
echo "Severity: $INCIDENT_SEVERITY"
echo "Description: $INCIDENT_DESCRIPTION"

# Generate incident report
cat > incident_report_$(date +%Y%m%d_%H%M%S).md << EOF
# Incident Report

**Timestamp:** $(date)
**Severity:** $INCIDENT_SEVERITY
**Description:** $INCIDENT_DESCRIPTION

## Actions Taken
- Emergency response procedure executed
- Service isolated and rolled back
- System state captured for analysis

## Current Status
- Service: $(systemctl is-active scenario-tracking)
- Health: $(python scripts/maintenance/health_monitor_core.py 2>/dev/null | head -1 || echo "Unknown")

## Next Steps
- [ ] Root cause analysis
- [ ] Fix implementation
- [ ] Testing and validation
- [ ] Gradual re-deployment

## Timeline
- $(date): Emergency response initiated
- $(date): Rollback completed
- $(date): Incident escalated

EOF

# Notify stakeholders (implement based on your notification system)
# slack_notify "Emergency rollback executed" "critical"
# email_notify "ops-team@company.com" "Critical: Scenario Tracking Emergency Rollback"

echo "📧 Incident report generated and stakeholders notified"
```

## Rollback Validation

### Post-Rollback Testing

```bash
#!/bin/bash
# scripts/validation/post_rollback_testing.sh

echo "🧪 Starting post-rollback validation testing..."

# Test suite prioritized by criticality
test_suites=(
  "basic:smoke tests for core functionality"
  "integration:end-to-end workflow validation" 
  "performance:performance regression testing"
  "security:security compliance validation"
)

for suite_info in "${test_suites[@]}"; do
  suite_name=$(echo $suite_info | cut -d: -f1)
  suite_desc=$(echo $suite_info | cut -d: -f2)
  
  echo "🔍 Running $suite_name tests: $suite_desc"
  
  python scripts/testing/run_core_integration_tests.py \
    --suite "$suite_name" \
    --table-suffix "_rollback_validation" \
    --output "rollback_validation_${suite_name}.json"
  
  if [ $? -eq 0 ]; then
    echo "✅ $suite_name tests passed"
  else
    echo "❌ $suite_name tests failed - rollback may not be complete"
    
    # Critical tests failing means rollback unsuccessful
    if [ "$suite_name" = "basic" ]; then
      echo "🚨 Critical tests failed - rollback unsuccessful"
      exit 1
    fi
  fi
done

echo "🎉 Post-rollback validation completed successfully"
```

### Performance Comparison

```bash
#!/bin/bash
# scripts/validation/performance_comparison.sh

echo "📊 Comparing post-rollback performance with baseline..."

# Run performance benchmarks
python scripts/testing/run_core_integration_tests.py \
  --suite performance \
  --table-suffix "_rollback_benchmark" \
  --output rollback_performance.json

# Compare with baseline
python -c "
import json

try:
    with open('rollback_performance.json', 'r') as f:
        current = json.load(f)
    
    with open('backup/baseline_performance.json', 'r') as f:
        baseline = json.load(f)
    
    # Extract performance metrics (adjust based on actual test output format)
    current_metrics = current.get('performance_metrics', {})
    baseline_metrics = baseline.get('performance_metrics', {})
    
    print('Performance Comparison:')
    print('=' * 50)
    
    for metric in ['throughput', 'success_rate', 'response_time']:
        current_val = current_metrics.get(metric, 0)
        baseline_val = baseline_metrics.get(metric, 0)
        
        if baseline_val > 0:
            change_pct = ((current_val - baseline_val) / baseline_val) * 100
            status = '✅' if change_pct >= -10 else '⚠️' if change_pct >= -20 else '❌'
            print(f'{metric}: {current_val} vs {baseline_val} ({change_pct:+.1f}%) {status}')
        else:
            print(f'{metric}: {current_val} (no baseline)')
    
except FileNotFoundError as e:
    print(f'Performance comparison failed: {e}')
"
```

## Rollback Documentation

### Rollback Report Template

```bash
#!/bin/bash
# Generate rollback report

cat > rollback_report_$(date +%Y%m%d_%H%M%S).md << EOF
# Rollback Report

## Summary
- **Date/Time:** $(date)
- **Trigger:** $ROLLBACK_REASON
- **Target Version:** $ROLLBACK_VERSION
- **Execution Method:** $ROLLBACK_METHOD
- **Duration:** $ROLLBACK_DURATION

## Pre-Rollback State
- Service Status: $PRE_ROLLBACK_STATUS
- Performance Metrics: $PRE_ROLLBACK_METRICS
- Error Rate: $PRE_ROLLBACK_ERROR_RATE

## Rollback Actions
- [ ] Service stopped
- [ ] Configuration restored
- [ ] Database schema reverted (if applicable)
- [ ] Service restarted
- [ ] Health validation completed

## Post-Rollback State
- Service Status: $(systemctl is-active scenario-tracking)
- Health Check: $(python scripts/maintenance/health_monitor_core.py | grep "Status:" | cut -d: -f2)
- Performance: Baseline comparison attached

## Validation Results
- Basic Tests: $BASIC_TEST_RESULT
- Integration Tests: $INTEGRATION_TEST_RESULT
- Performance Tests: $PERFORMANCE_TEST_RESULT

## Root Cause Analysis
[To be completed after investigation]

## Lessons Learned
[To be completed after post-mortem]

## Next Steps
- [ ] Root cause investigation
- [ ] Fix development and testing
- [ ] Gradual re-deployment plan
- [ ] Process improvements
EOF

echo "📝 Rollback report generated: rollback_report_$(date +%Y%m%d_%H%M%S).md"
```

This comprehensive rollback procedures guide ensures that the core scenario tracking system can be safely and quickly restored to a previous working state when issues arise, with proper validation and documentation of all rollback activities.