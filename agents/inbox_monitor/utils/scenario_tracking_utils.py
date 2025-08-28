"""
Utility functions for scenario tracking operations.
Provides helper functions, data transformations, and common operations.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Union
import json
import hashlib
from collections import defaultdict
import structlog

try:
    from database.scenario_tracking_models import (
        ScenarioProcessingRecord, 
        ScenarioType, 
        AIIntent,
        ScenarioTrackingConfiguration
    )
    from services.scenario_tracking_exceptions import (
        DataValidationError,
        QueryExecutionError
    )
except ImportError:
    from ..database.scenario_tracking_models import (
        ScenarioProcessingRecord, 
        ScenarioType, 
        AIIntent,
        ScenarioTrackingConfiguration
    )
    from ..services.scenario_tracking_exceptions import (
        DataValidationError,
        QueryExecutionError
    )

logger = structlog.get_logger(__name__)


def generate_processing_correlation_id(email_id: str, sender_email: str, timestamp: datetime = None) -> str:
    """Generate a correlation ID for scenario processing.
    
    Args:
        email_id: Microsoft Graph email ID
        sender_email: Sender email address
        timestamp: Processing timestamp (defaults to now)
        
    Returns:
        Unique correlation ID
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    
    # Create deterministic hash based on email details
    hash_input = f"{email_id}:{sender_email.lower()}:{timestamp.strftime('%Y%m%d')}"
    hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    return f"scenario_{timestamp.strftime('%Y%m%d')}_{hash_value}"


def sanitize_email_content(content: str, max_length: int = 500) -> str:
    """Sanitize email content for database storage.
    
    Args:
        content: Raw email content
        max_length: Maximum length to retain
        
    Returns:
        Sanitized content
    """
    if not content:
        return ""
    
    # Remove excessive whitespace
    sanitized = " ".join(content.split())
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length - 3] + "..."
    
    # Remove or escape problematic characters for SQL
    sanitized = sanitized.replace("'", "''")  # Escape single quotes
    sanitized = sanitized.replace("\x00", "")  # Remove null bytes
    
    return sanitized


def normalize_customer_email(email: str) -> str:
    """Normalize customer email for consistent grouping.
    
    Args:
        email: Raw email address
        
    Returns:
        Normalized email address
    """
    if not email or "@" not in email:
        return "unknown@unknown.com"
    
    # Convert to lowercase and strip whitespace
    normalized = email.lower().strip()
    
    # Remove any display name portion if present
    if "<" in normalized and ">" in normalized:
        start = normalized.find("<")
        end = normalized.find(">")
        if start < end:
            normalized = normalized[start + 1:end]
    
    return normalized


def extract_scenario_insights(records: List[ScenarioProcessingRecord]) -> Dict[str, Any]:
    """Extract insights from a collection of scenario processing records.
    
    Args:
        records: List of scenario processing records
        
    Returns:
        Dictionary with extracted insights
    """
    if not records:
        return {
            "total_records": 0,
            "insights": {}
        }
    
    insights = {
        "total_records": len(records),
        "scenario_breakdown": defaultdict(int),
        "success_rates": {},
        "processing_time_stats": {},
        "customer_patterns": defaultdict(list),
        "expert_workload": defaultdict(int),
        "common_failures": defaultdict(int),
        "temporal_patterns": defaultdict(int)
    }
    
    processing_times = []
    scenario_success = defaultdict(list)
    
    for record in records:
        # Scenario breakdown
        insights["scenario_breakdown"][record.scenario_type.value] += 1
        
        # Processing time tracking
        if record.processing_duration_ms:
            processing_times.append(record.processing_duration_ms)
        
        # Success rate by scenario
        scenario_success[record.scenario_type.value].append(record.process_success)
        
        # Customer patterns
        customer_key = normalize_customer_email(record.sender_email)
        insights["customer_patterns"][customer_key].append({
            "scenario": record.scenario_type.value,
            "timestamp": record.processed_at,
            "success": record.process_success
        })
        
        # Expert workload
        if record.expert_assigned:
            insights["expert_workload"][record.expert_assigned] += 1
        
        # Failure patterns
        if not record.process_success and record.process_error:
            insights["common_failures"][record.process_error] += 1
        
        # Temporal patterns (by hour of day)
        hour = record.processed_at.hour
        insights["temporal_patterns"][hour] += 1
    
    # Calculate success rates
    for scenario, successes in scenario_success.items():
        total = len(successes)
        successful = sum(successes)
        insights["success_rates"][scenario] = (successful / total * 100) if total > 0 else 0
    
    # Processing time statistics
    if processing_times:
        processing_times.sort()
        insights["processing_time_stats"] = {
            "mean_ms": sum(processing_times) / len(processing_times),
            "median_ms": processing_times[len(processing_times) // 2],
            "p95_ms": processing_times[int(len(processing_times) * 0.95)],
            "min_ms": min(processing_times),
            "max_ms": max(processing_times)
        }
    
    # Convert defaultdicts to regular dicts for serialization
    insights = {k: dict(v) if isinstance(v, defaultdict) else v for k, v in insights.items()}
    
    return insights


def validate_scenario_data_quality(record: ScenarioProcessingRecord) -> List[Dict[str, str]]:
    """Validate data quality for scenario processing record.
    
    Args:
        record: Scenario processing record to validate
        
    Returns:
        List of data quality issues found
    """
    issues = []
    
    # Email validation
    if not record.sender_email or "@" not in record.sender_email:
        issues.append({
            "field": "sender_email",
            "issue": "invalid_email_format",
            "description": "Sender email is missing or invalid format"
        })
    
    # Processing time validation
    if record.processing_duration_ms is not None and record.processing_duration_ms < 0:
        issues.append({
            "field": "processing_duration_ms",
            "issue": "negative_processing_time",
            "description": "Processing time cannot be negative"
        })
    
    # Scenario consistency validation
    if record.scenario_type == ScenarioType.SCENARIO_5 and not record.expert_assigned:
        issues.append({
            "field": "expert_assigned",
            "issue": "missing_expert_for_scenario_5",
            "description": "Scenario 5 should have an expert assigned"
        })
    
    # AI confidence validation
    if record.ai_confidence is not None and (record.ai_confidence < 0 or record.ai_confidence > 1):
        issues.append({
            "field": "ai_confidence",
            "issue": "invalid_confidence_range",
            "description": "AI confidence must be between 0 and 1"
        })
    
    # Date validation
    if record.received_datetime > record.processed_at:
        issues.append({
            "field": "processed_at",
            "issue": "processing_before_receipt",
            "description": "Processing timestamp cannot be before email receipt"
        })
    
    # Success vs error consistency
    if not record.process_success and not record.process_error:
        issues.append({
            "field": "process_error",
            "issue": "missing_error_message",
            "description": "Failed processing should have an error message"
        })
    
    return issues


def calculate_performance_score(record: ScenarioProcessingRecord) -> float:
    """Calculate performance score for a scenario processing record.
    
    Args:
        record: Scenario processing record
        
    Returns:
        Performance score (0-100)
    """
    return record.calculate_performance_score()


def group_records_by_customer(records: List[ScenarioProcessingRecord]) -> Dict[str, List[ScenarioProcessingRecord]]:
    """Group scenario processing records by customer.
    
    Args:
        records: List of scenario processing records
        
    Returns:
        Dictionary mapping customer email to their records
    """
    grouped = defaultdict(list)
    
    for record in records:
        customer_key = normalize_customer_email(record.sender_email)
        grouped[customer_key].append(record)
    
    return dict(grouped)


def calculate_scenario_trends(
    records: List[ScenarioProcessingRecord], 
    time_window_hours: int = 24
) -> Dict[str, Any]:
    """Calculate scenario processing trends over time.
    
    Args:
        records: List of scenario processing records
        time_window_hours: Time window for trend analysis
        
    Returns:
        Dictionary with trend analysis
    """
    if not records:
        return {"trends": {}, "summary": {"total_records": 0}}
    
    # Sort records by timestamp
    sorted_records = sorted(records, key=lambda r: r.processed_at)
    
    # Create time buckets
    start_time = sorted_records[0].processed_at
    end_time = sorted_records[-1].processed_at
    total_hours = int((end_time - start_time).total_seconds() / 3600) + 1
    
    bucket_size = max(1, total_hours // time_window_hours)
    
    trends = {
        "hourly_volume": defaultdict(int),
        "scenario_trends": defaultdict(lambda: defaultdict(int)),
        "success_trends": defaultdict(lambda: {"success": 0, "failure": 0}),
        "processing_time_trends": defaultdict(list)
    }
    
    for record in sorted_records:
        hour_bucket = record.processed_at.hour // bucket_size * bucket_size
        
        # Volume trends
        trends["hourly_volume"][hour_bucket] += 1
        
        # Scenario type trends
        trends["scenario_trends"][record.scenario_type.value][hour_bucket] += 1
        
        # Success/failure trends
        if record.process_success:
            trends["success_trends"][hour_bucket]["success"] += 1
        else:
            trends["success_trends"][hour_bucket]["failure"] += 1
        
        # Processing time trends
        if record.processing_duration_ms:
            trends["processing_time_trends"][hour_bucket].append(record.processing_duration_ms)
    
    # Convert to regular dicts and calculate averages
    result_trends = {}
    
    result_trends["hourly_volume"] = dict(trends["hourly_volume"])
    result_trends["scenario_trends"] = {k: dict(v) for k, v in trends["scenario_trends"].items()}
    result_trends["success_trends"] = dict(trends["success_trends"])
    
    # Calculate average processing times
    result_trends["avg_processing_time_trends"] = {}
    for hour, times in trends["processing_time_trends"].items():
        if times:
            result_trends["avg_processing_time_trends"][hour] = sum(times) / len(times)
    
    summary = {
        "total_records": len(records),
        "time_span_hours": total_hours,
        "unique_scenarios": len(set(r.scenario_type.value for r in records)),
        "overall_success_rate": sum(1 for r in records if r.process_success) / len(records) * 100,
        "peak_volume_hour": max(result_trends["hourly_volume"], key=result_trends["hourly_volume"].get) if result_trends["hourly_volume"] else None
    }
    
    return {
        "trends": result_trends,
        "summary": summary
    }


async def create_scenario_record_from_email_data(
    email_data: Any,
    processing_result: Any = None,
    scenario_result: Any = None,
    ai_result: Any = None,
    **kwargs
) -> ScenarioProcessingRecord:
    """Create ScenarioProcessingRecord from various email processing data with real customer analytics.
    
    Args:
        email_data: Email data object
        processing_result: Processing result object
        scenario_result: Scenario processing result
        ai_result: AI classification result
        **kwargs: Additional fields
        
    Returns:
        ScenarioProcessingRecord instance with calculated customer analytics
    """
    return await ScenarioProcessingRecord.from_processing_results(
        email_data=email_data,
        processing_result=processing_result,
        scenario_result=scenario_result,
        intent_result=ai_result,
        **kwargs
    )


def format_duration_ms(duration_ms: float) -> str:
    """Format duration in milliseconds to human-readable string.
    
    Args:
        duration_ms: Duration in milliseconds
        
    Returns:
        Human-readable duration string
    """
    if duration_ms < 1000:
        return f"{duration_ms:.0f}ms"
    elif duration_ms < 60000:
        return f"{duration_ms / 1000:.1f}s"
    elif duration_ms < 3600000:
        return f"{duration_ms / 60000:.1f}m"
    else:
        return f"{duration_ms / 3600000:.1f}h"


def calculate_batch_optimal_size(
    records: List[ScenarioProcessingRecord],
    target_batch_time_ms: int = 5000
) -> int:
    """Calculate optimal batch size based on record complexity.
    
    Args:
        records: Sample records to analyze
        target_batch_time_ms: Target batch processing time
        
    Returns:
        Recommended batch size
    """
    if not records:
        return 50  # Default batch size
    
    # Calculate average record complexity score
    total_complexity = 0
    for record in records:
        complexity = 1  # Base complexity
        
        # Add complexity based on data richness
        if record.recipient_emails:
            complexity += len(record.recipient_emails) * 0.1
        
        if record.agent_actions_log:
            complexity += len(record.agent_actions_log) * 0.2
        
        if record.status_updates:
            complexity += len(record.status_updates) * 0.3
        
        if record.ai_detected_phrases:
            complexity += len(record.ai_detected_phrases) * 0.1
        
        total_complexity += complexity
    
    avg_complexity = total_complexity / len(records)
    
    # Estimate processing time per record based on complexity
    estimated_time_per_record = avg_complexity * 50  # 50ms base per complexity unit
    
    # Calculate batch size to hit target time
    optimal_size = int(target_batch_time_ms / estimated_time_per_record)
    
    # Clamp to reasonable bounds
    return max(10, min(500, optimal_size))


async def retry_with_backoff(
    operation_func,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True
):
    """Retry an async operation with exponential backoff.
    
    Args:
        operation_func: Async function to retry
        max_attempts: Maximum retry attempts
        base_delay: Base delay in seconds
        backoff_factor: Multiplier for each retry
        jitter: Add randomness to delay
        
    Returns:
        Result of successful operation
        
    Raises:
        Last exception if all attempts fail
    """
    import random
    
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await operation_func()
        except Exception as e:
            last_exception = e
            
            if attempt == max_attempts - 1:
                # Last attempt, don't delay
                break
            
            # Calculate delay with exponential backoff
            delay = base_delay * (backoff_factor ** attempt)
            
            # Add jitter to prevent thundering herd
            if jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(
                "Operation failed, retrying",
                attempt=attempt + 1,
                max_attempts=max_attempts,
                delay_seconds=delay,
                error=str(e)
            )
            
            await asyncio.sleep(delay)
    
    # All attempts failed
    if last_exception:
        raise last_exception
    else:
        raise QueryExecutionError("All retry attempts failed")