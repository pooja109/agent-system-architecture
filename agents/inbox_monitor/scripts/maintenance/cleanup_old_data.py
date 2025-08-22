#!/usr/bin/env python3
"""
Core Data Cleanup Script for Scenario Tracking System
======================================================

Maintenance script to clean up old data and optimize storage.
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)


class CoreDataCleanupManager:
    """Manages data cleanup operations for core scenario tracking system."""
    
    def __init__(self, table_suffix: str = "", retention_days: int = 365):
        """Initialize data cleanup manager."""
        self.table_suffix = table_suffix
        self.retention_days = retention_days
        self.logger = structlog.get_logger(__name__, component="data_cleanup")
        self.cleanup_results = {}
    
    async def execute_cleanup(self, dry_run: bool = True) -> Dict[str, Any]:
        """Execute comprehensive data cleanup."""
        self.logger.info("Starting core data cleanup", 
                        retention_days=self.retention_days,
                        dry_run=dry_run)
        
        cleanup_start = datetime.now()
        
        try:
            # Step 1: Analyze current data
            analysis_result = await self._analyze_current_data()
            self.cleanup_results['data_analysis'] = analysis_result
            
            # Step 2: Identify data for cleanup
            cleanup_candidates = await self._identify_cleanup_candidates()
            self.cleanup_results['cleanup_candidates'] = cleanup_candidates
            
            # Step 3: Archive old data (if not dry run)
            if not dry_run:
                archive_result = await self._archive_old_data(cleanup_candidates)
                self.cleanup_results['data_archive'] = archive_result
            
            # Step 4: Delete expired data (if not dry run)
            if not dry_run:
                deletion_result = await self._delete_expired_data(cleanup_candidates)
                self.cleanup_results['data_deletion'] = deletion_result
            
            # Step 5: Optimize table structure
            optimization_result = await self._optimize_table_structure(dry_run)
            self.cleanup_results['table_optimization'] = optimization_result
            
            # Step 6: Update statistics
            stats_result = await self._update_table_statistics(dry_run)
            self.cleanup_results['statistics_update'] = stats_result
            
            cleanup_duration = datetime.now() - cleanup_start
            
            # Generate cleanup summary
            summary = await self._generate_cleanup_summary(cleanup_duration)
            
            return summary
            
        except Exception as e:
            cleanup_duration = datetime.now() - cleanup_start
            self.logger.error("Data cleanup failed", error=str(e))
            
            summary = await self._generate_cleanup_summary(cleanup_duration, False, str(e))
            return summary
    
    async def _analyze_current_data(self) -> Dict[str, Any]:
        """Analyze current data in the scenario tracking table."""
        self.logger.info("Analyzing current data")
        
        try:
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                # Get table information
                table_name = f"inbox_monitor_scenario_processing{self.table_suffix}"
                
                # Count total records
                total_count_query = f"SELECT COUNT(*) as total_records FROM {table_name}"
                total_result = await connection.execute_query(total_count_query, {})
                total_records = total_result.fetchone()['total_records']
                
                # Analyze data by date ranges
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
                
                date_analysis_query = f"""
                SELECT 
                    CASE 
                        WHEN processed_at >= '{cutoff_date.isoformat()}' THEN 'recent'
                        WHEN processed_at >= '{(cutoff_date - timedelta(days=90)).isoformat()}' THEN 'old'
                        ELSE 'expired'
                    END as age_category,
                    COUNT(*) as record_count,
                    MIN(processed_at) as earliest_timestamp,
                    MAX(processed_at) as latest_timestamp
                FROM {table_name}
                GROUP BY age_category
                ORDER BY age_category
                """
                
                date_result = await connection.execute_query(date_analysis_query, {})
                date_analysis = date_result.fetchall()
                
                # Storage size analysis
                table_info_query = f"DESCRIBE DETAIL {table_name}"
                table_info_result = await connection.execute_query(table_info_query, {})
                table_info = table_info_result.fetchone()
                
                analysis = {
                    'total_records': total_records,
                    'table_size_bytes': table_info.get('sizeInBytes', 0) if table_info else 0,
                    'num_files': table_info.get('numFiles', 0) if table_info else 0,
                    'date_analysis': [dict(row) for row in date_analysis],
                    'retention_cutoff_date': cutoff_date.isoformat(),
                    'analysis_timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                self.logger.info("Data analysis completed",
                               total_records=total_records,
                               table_size_mb=analysis['table_size_bytes'] / (1024 * 1024))
                
                return analysis
                
        except ImportError:
            self.logger.warning("Database connection not available for analysis")
            return {
                'status': 'skipped',
                'reason': 'database_connection_not_available'
            }
        except Exception as e:
            self.logger.error("Data analysis failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _identify_cleanup_candidates(self) -> Dict[str, Any]:
        """Identify data candidates for cleanup operations."""
        self.logger.info("Identifying cleanup candidates")
        
        try:
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                table_name = f"inbox_monitor_scenario_processing{self.table_suffix}"
                
                # Identify expired data
                retention_cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
                archive_cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days // 2)
                
                expired_data_query = f"""
                SELECT COUNT(*) as expired_count
                FROM {table_name}
                WHERE processed_at < '{retention_cutoff.isoformat()}'
                """
                
                expired_result = await connection.execute_query(expired_data_query, {})
                expired_count = expired_result.fetchone()['expired_count']
                
                # Identify archive candidates
                archive_data_query = f"""
                SELECT COUNT(*) as archive_count
                FROM {table_name}
                WHERE processed_at >= '{retention_cutoff.isoformat()}'
                  AND processed_at < '{archive_cutoff.isoformat()}'
                """
                
                archive_result = await connection.execute_query(archive_data_query, {})
                archive_count = archive_result.fetchone()['archive_count']
                
                # Identify duplicate/corrupt data
                duplicate_check_query = f"""
                SELECT 
                    process_id,
                    COUNT(*) as duplicate_count
                FROM {table_name}
                GROUP BY process_id
                HAVING COUNT(*) > 1
                """
                
                duplicate_result = await connection.execute_query(duplicate_check_query, {})
                duplicates = duplicate_result.fetchall()
                
                candidates = {
                    'expired_records': expired_count,
                    'archive_candidates': archive_count,
                    'duplicate_records': len(duplicates),
                    'retention_cutoff_date': retention_cutoff.isoformat(),
                    'archive_cutoff_date': archive_cutoff.isoformat(),
                    'duplicates_detail': [dict(row) for row in duplicates[:10]]  # First 10 duplicates
                }
                
                self.logger.info("Cleanup candidates identified",
                               expired_records=expired_count,
                               archive_candidates=archive_count,
                               duplicate_records=len(duplicates))
                
                return candidates
                
        except Exception as e:
            self.logger.error("Failed to identify cleanup candidates", error=str(e))
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _archive_old_data(self, candidates: Dict[str, Any]) -> Dict[str, Any]:
        """Archive old data to separate storage."""
        self.logger.info("Archiving old data")
        
        try:
            # Create archive table if it doesn't exist
            archive_table_name = f"inbox_monitor_scenario_processing_archive{self.table_suffix}"
            
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                # Create archive table structure
                source_table = f"inbox_monitor_scenario_processing{self.table_suffix}"
                
                create_archive_query = f"""
                CREATE TABLE IF NOT EXISTS {archive_table_name}
                USING DELTA
                AS SELECT * FROM {source_table} WHERE 1=0
                """
                
                await connection.execute_query(create_archive_query, {})
                
                # Move data to archive
                cutoff_date = candidates.get('archive_cutoff_date')
                if cutoff_date:
                    archive_insert_query = f"""
                    INSERT INTO {archive_table_name}
                    SELECT * FROM {source_table}
                    WHERE processed_at < '{cutoff_date}'
                      AND processed_at >= '{candidates.get("retention_cutoff_date")}'
                    """
                    
                    await connection.execute_query(archive_insert_query, {})
                    
                    # Verify archive operation
                    archive_count_query = f"SELECT COUNT(*) as archived_count FROM {archive_table_name}"
                    archive_count_result = await connection.execute_query(archive_count_query, {})
                    archived_count = archive_count_result.fetchone()['archived_count']
                    
                    return {
                        'status': 'completed',
                        'archive_table': archive_table_name,
                        'archived_records': archived_count,
                        'archive_cutoff_date': cutoff_date
                    }
                else:
                    return {
                        'status': 'skipped',
                        'reason': 'no_archive_candidates'
                    }
                    
        except Exception as e:
            self.logger.error("Data archiving failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _delete_expired_data(self, candidates: Dict[str, Any]) -> Dict[str, Any]:
        """Delete expired data beyond retention period."""
        self.logger.warning("Deleting expired data - DESTRUCTIVE OPERATION")
        
        try:
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                table_name = f"inbox_monitor_scenario_processing{self.table_suffix}"
                
                # Count records to be deleted
                cutoff_date = candidates.get('retention_cutoff_date')
                if not cutoff_date:
                    return {
                        'status': 'skipped',
                        'reason': 'no_cutoff_date_specified'
                    }
                
                # Delete expired records
                delete_query = f"""
                DELETE FROM {table_name}
                WHERE processed_at < '{cutoff_date}'
                """
                
                await connection.execute_query(delete_query, {})
                
                # Verify deletion
                remaining_count_query = f"SELECT COUNT(*) as remaining_count FROM {table_name}"
                remaining_result = await connection.execute_query(remaining_count_query, {})
                remaining_count = remaining_result.fetchone()['remaining_count']
                
                deleted_count = candidates.get('expired_records', 0)
                
                return {
                    'status': 'completed',
                    'deleted_records': deleted_count,
                    'remaining_records': remaining_count,
                    'retention_cutoff_date': cutoff_date
                }
                
        except Exception as e:
            self.logger.error("Data deletion failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _optimize_table_structure(self, dry_run: bool) -> Dict[str, Any]:
        """Optimize table structure for better performance."""
        self.logger.info("Optimizing table structure", dry_run=dry_run)
        
        try:
            if dry_run:
                return {
                    'status': 'dry_run',
                    'would_optimize': 'table_compaction_and_statistics'
                }
            
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                table_name = f"inbox_monitor_scenario_processing{self.table_suffix}"
                
                # Run OPTIMIZE command
                optimize_query = f"OPTIMIZE {table_name}"
                await connection.execute_query(optimize_query, {})
                
                # Run ZORDER optimization on frequently queried columns
                zorder_query = f"OPTIMIZE {table_name} ZORDER BY (processed_at, sender_email, scenario_type)"
                await connection.execute_query(zorder_query, {})
                
                return {
                    'status': 'completed',
                    'optimizations_applied': [
                        'table_compaction',
                        'zorder_optimization'
                    ],
                    'optimized_columns': ['processed_at', 'sender_email', 'scenario_type']
                }
                
        except Exception as e:
            self.logger.error("Table optimization failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _update_table_statistics(self, dry_run: bool) -> Dict[str, Any]:
        """Update table statistics for query optimization."""
        self.logger.info("Updating table statistics", dry_run=dry_run)
        
        try:
            if dry_run:
                return {
                    'status': 'dry_run',
                    'would_update': 'table_statistics'
                }
            
            from services.databricks_connection_pool import get_connection_pool
            
            connection_pool = await get_connection_pool()
            async with connection_pool.get_connection() as connection:
                table_name = f"inbox_monitor_scenario_processing{self.table_suffix}"
                
                # Update table statistics
                analyze_query = f"ANALYZE TABLE {table_name} COMPUTE STATISTICS"
                await connection.execute_query(analyze_query, {})
                
                return {
                    'status': 'completed',
                    'statistics_updated': True,
                    'table_analyzed': table_name
                }
                
        except Exception as e:
            self.logger.error("Statistics update failed", error=str(e))
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    async def _generate_cleanup_summary(self, cleanup_duration, success: bool = True, 
                                      error: str = None) -> Dict[str, Any]:
        """Generate comprehensive cleanup summary."""
        
        summary = {
            'cleanup_timestamp': datetime.now(timezone.utc).isoformat(),
            'cleanup_duration_seconds': cleanup_duration.total_seconds(),
            'table_suffix': self.table_suffix,
            'retention_days': self.retention_days,
            'cleanup_success': success,
            'error': error,
            'operations_performed': self.cleanup_results,
            'summary_statistics': self._calculate_summary_statistics()
        }
        
        return summary
    
    def _calculate_summary_statistics(self) -> Dict[str, Any]:
        """Calculate summary statistics from cleanup results."""
        
        stats = {
            'total_operations': len(self.cleanup_results),
            'successful_operations': 0,
            'failed_operations': 0,
            'skipped_operations': 0
        }
        
        for operation, result in self.cleanup_results.items():
            if isinstance(result, dict):
                status = result.get('status', 'unknown')
                if status == 'completed':
                    stats['successful_operations'] += 1
                elif status == 'failed':
                    stats['failed_operations'] += 1
                elif status in ['skipped', 'dry_run']:
                    stats['skipped_operations'] += 1
        
        return stats


async def main():
    """Main data cleanup function."""
    parser = argparse.ArgumentParser(description='Core Data Cleanup for Scenario Tracking')
    parser.add_argument('--table-suffix', default='', help='Table suffix for environment isolation')
    parser.add_argument('--retention-days', type=int, default=365, help='Data retention period in days')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without executing')
    parser.add_argument('--confirm', action='store_true', help='Confirm destructive operations')
    parser.add_argument('--output', help='Save cleanup results to file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Safety confirmation for destructive operations
    if not args.dry_run and not args.confirm:
        print("WARNING: This will perform data deletion operations.")
        print("Use --confirm flag to proceed or --dry-run to see what would be done.")
        return 1
    
    # Execute cleanup
    cleanup_manager = CoreDataCleanupManager(args.table_suffix, args.retention_days)
    cleanup_summary = await cleanup_manager.execute_cleanup(args.dry_run)
    
    # Output results
    if args.output:
        Path(args.output).write_text(json.dumps(cleanup_summary, indent=2))
        logger.info("Cleanup results saved", file=args.output)
    else:
        print(json.dumps(cleanup_summary, indent=2))
    
    # Print summary
    print(f"\nData Cleanup Summary:")
    print(f"Success: {cleanup_summary['cleanup_success']}")
    print(f"Duration: {cleanup_summary['cleanup_duration_seconds']:.2f} seconds")
    print(f"Retention Period: {cleanup_summary['retention_days']} days")
    
    stats = cleanup_summary.get('summary_statistics', {})
    print(f"Operations: {stats.get('total_operations', 0)} total")
    print(f"  Successful: {stats.get('successful_operations', 0)}")
    print(f"  Failed: {stats.get('failed_operations', 0)}")
    print(f"  Skipped: {stats.get('skipped_operations', 0)}")
    
    # Return appropriate exit code
    return 0 if cleanup_summary['cleanup_success'] else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))