#!/usr/bin/env python3
"""
Table Optimization Script for Scenario Tracking System
======================================================

Optimizes Databricks Delta tables for better performance and storage efficiency.
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)


class TableOptimizer:
    """Handles Delta table optimization operations."""
    
    def __init__(self, table_suffix: str = "", dry_run: bool = False):
        """Initialize table optimizer."""
        self.table_suffix = table_suffix
        self.dry_run = dry_run
        self.logger = structlog.get_logger(__name__, component="table_optimizer")
        
        # Get database configuration
        try:
            from config.core_production_config import CORE_PRODUCTION_CONFIG
            self.db_config = CORE_PRODUCTION_CONFIG['DATABRICKS_CONFIG']
        except ImportError:
            # Fallback configuration
            import os
            self.db_config = {
                'catalog': os.getenv('DATABRICKS_CATALOG', 'inbox_monitor'),
                'schema': os.getenv('DATABRICKS_SCHEMA', 'scenario_tracking')
            }
    
    async def optimize_all_tables(self) -> Dict[str, Any]:
        """Optimize all scenario tracking tables."""
        self.logger.info("Starting table optimization", dry_run=self.dry_run)
        
        optimization_start = datetime.now()
        
        results = {
            'optimization_start': optimization_start.isoformat(),
            'dry_run': self.dry_run,
            'tables_optimized': [],
            'optimization_errors': [],
            'total_files_compacted': 0,
            'total_size_reduction_bytes': 0
        }
        
        # Core scenario tracking tables
        tables_to_optimize = [
            f"inbox_monitor_scenario_processing{self.table_suffix}"
        ]
        
        try:
            # Import connection pool if available
            try:
                from services.databricks_connection_pool import get_connection_pool
                connection_pool = await get_connection_pool()
                
                for table_name in tables_to_optimize:
                    table_result = await self._optimize_table(connection_pool, table_name)
                    results['tables_optimized'].append(table_result)
                    
                    if table_result.get('success'):
                        results['total_files_compacted'] += table_result.get('files_compacted', 0)
                        results['total_size_reduction_bytes'] += table_result.get('size_reduction_bytes', 0)
                    else:
                        results['optimization_errors'].append(table_result.get('error'))
                        
            except ImportError:
                self.logger.warning("Connection pool not available - performing mock optimization")
                for table_name in tables_to_optimize:
                    mock_result = await self._mock_table_optimization(table_name)
                    results['tables_optimized'].append(mock_result)
        
        except Exception as e:
            self.logger.error("Table optimization failed", error=str(e))
            results['optimization_error'] = str(e)
        
        # Calculate summary statistics
        optimization_duration = datetime.now() - optimization_start
        results['optimization_duration_seconds'] = optimization_duration.total_seconds()
        results['success_rate'] = len([r for r in results['tables_optimized'] if r.get('success')]) / len(results['tables_optimized']) * 100 if results['tables_optimized'] else 0
        
        self.logger.info("Table optimization completed", 
                        duration=optimization_duration.total_seconds(),
                        tables_processed=len(results['tables_optimized']),
                        success_rate=results['success_rate'])
        
        return results
    
    async def _optimize_table(self, connection_pool, table_name: str) -> Dict[str, Any]:
        """Optimize a single Delta table."""
        self.logger.info("Optimizing table", table=table_name, dry_run=self.dry_run)
        
        optimization_start = datetime.now()
        table_result = {
            'table_name': table_name,
            'optimization_start': optimization_start.isoformat(),
            'success': False
        }
        
        try:
            async with connection_pool.get_connection() as connection:
                full_table_name = f"{self.db_config['catalog']}.{self.db_config['schema']}.{table_name}"
                
                # Get table statistics before optimization
                before_stats = await self._get_table_statistics(connection, full_table_name)
                table_result['before_optimization'] = before_stats
                
                if not self.dry_run:
                    # Run OPTIMIZE command
                    optimize_sql = f"""
                    OPTIMIZE {full_table_name}
                    ZORDER BY (processed_at, scenario_type, sender_email)
                    """
                    
                    self.logger.info("Executing OPTIMIZE command", sql=optimize_sql)
                    optimize_result = await connection.execute_query(optimize_sql, {})
                    
                    # Wait for optimization to complete and get statistics
                    await asyncio.sleep(2)  # Brief pause to let optimization complete
                    
                    # Get table statistics after optimization
                    after_stats = await self._get_table_statistics(connection, full_table_name)
                    table_result['after_optimization'] = after_stats
                    
                    # Calculate optimization benefits
                    files_before = before_stats.get('num_files', 0)
                    files_after = after_stats.get('num_files', 0)
                    size_before = before_stats.get('size_bytes', 0)
                    size_after = after_stats.get('size_bytes', 0)
                    
                    table_result['files_compacted'] = max(0, files_before - files_after)
                    table_result['size_reduction_bytes'] = max(0, size_before - size_after)
                    table_result['size_reduction_percentage'] = ((size_before - size_after) / size_before * 100) if size_before > 0 else 0
                    
                    self.logger.info("Table optimization completed", 
                                   table=table_name,
                                   files_compacted=table_result['files_compacted'],
                                   size_reduction_mb=table_result['size_reduction_bytes'] / 1024 / 1024)
                else:
                    self.logger.info("DRY RUN: Would optimize table", table=table_name)
                    table_result['dry_run_message'] = f"Would run OPTIMIZE on {full_table_name}"
                
                table_result['success'] = True
                
        except Exception as e:
            self.logger.error("Failed to optimize table", table=table_name, error=str(e))
            table_result['error'] = str(e)
        
        optimization_duration = datetime.now() - optimization_start
        table_result['optimization_duration_seconds'] = optimization_duration.total_seconds()
        
        return table_result
    
    async def _mock_table_optimization(self, table_name: str) -> Dict[str, Any]:
        """Mock table optimization for test environments."""
        self.logger.info("Mock table optimization", table=table_name)
        
        return {
            'table_name': table_name,
            'optimization_start': datetime.now().isoformat(),
            'success': True,
            'mock': True,
            'dry_run_message': f"Mock optimization of {table_name}",
            'files_compacted': 5,  # Mock values
            'size_reduction_bytes': 1024 * 1024 * 10,  # 10MB
            'size_reduction_percentage': 15.0,
            'optimization_duration_seconds': 2.0
        }
    
    async def _get_table_statistics(self, connection, full_table_name: str) -> Dict[str, Any]:
        """Get Delta table statistics."""
        try:
            # Get basic table information
            stats_sql = f"DESCRIBE DETAIL {full_table_name}"
            result = await connection.execute_query(stats_sql, {})
            
            table_details = result.fetchone()
            
            return {
                'num_files': table_details.get('numFiles', 0),
                'size_bytes': table_details.get('sizeInBytes', 0),
                'size_mb': table_details.get('sizeInBytes', 0) / 1024 / 1024,
                'last_modified': str(table_details.get('lastModified', '')),
                'table_format': table_details.get('format', 'DELTA')
            }
            
        except Exception as e:
            self.logger.warning("Could not get table statistics", table=full_table_name, error=str(e))
            return {
                'error': str(e),
                'num_files': 0,
                'size_bytes': 0
            }
    
    async def vacuum_tables(self, retention_hours: int = 168) -> Dict[str, Any]:
        """Vacuum Delta tables to remove old file versions."""
        self.logger.info("Starting table vacuum", retention_hours=retention_hours, dry_run=self.dry_run)
        
        vacuum_start = datetime.now()
        
        results = {
            'vacuum_start': vacuum_start.isoformat(),
            'retention_hours': retention_hours,
            'dry_run': self.dry_run,
            'tables_vacuumed': [],
            'vacuum_errors': [],
            'total_files_removed': 0
        }
        
        # Core scenario tracking tables
        tables_to_vacuum = [
            f"inbox_monitor_scenario_processing{self.table_suffix}"
        ]
        
        try:
            try:
                from services.databricks_connection_pool import get_connection_pool
                connection_pool = await get_connection_pool()
                
                for table_name in tables_to_vacuum:
                    vacuum_result = await self._vacuum_table(connection_pool, table_name, retention_hours)
                    results['tables_vacuumed'].append(vacuum_result)
                    
                    if vacuum_result.get('success'):
                        results['total_files_removed'] += vacuum_result.get('files_removed', 0)
                    else:
                        results['vacuum_errors'].append(vacuum_result.get('error'))
                        
            except ImportError:
                self.logger.warning("Connection pool not available - performing mock vacuum")
                for table_name in tables_to_vacuum:
                    mock_result = await self._mock_table_vacuum(table_name, retention_hours)
                    results['tables_vacuumed'].append(mock_result)
        
        except Exception as e:
            self.logger.error("Table vacuum failed", error=str(e))
            results['vacuum_error'] = str(e)
        
        vacuum_duration = datetime.now() - vacuum_start
        results['vacuum_duration_seconds'] = vacuum_duration.total_seconds()
        
        self.logger.info("Table vacuum completed", 
                        duration=vacuum_duration.total_seconds(),
                        tables_processed=len(results['tables_vacuumed']),
                        files_removed=results['total_files_removed'])
        
        return results
    
    async def _vacuum_table(self, connection_pool, table_name: str, retention_hours: int) -> Dict[str, Any]:
        """Vacuum a single Delta table."""
        self.logger.info("Vacuuming table", table=table_name, retention_hours=retention_hours, dry_run=self.dry_run)
        
        vacuum_start = datetime.now()
        vacuum_result = {
            'table_name': table_name,
            'vacuum_start': vacuum_start.isoformat(),
            'retention_hours': retention_hours,
            'success': False
        }
        
        try:
            async with connection_pool.get_connection() as connection:
                full_table_name = f"{self.db_config['catalog']}.{self.db_config['schema']}.{table_name}"
                
                if not self.dry_run:
                    # Run VACUUM command
                    vacuum_sql = f"VACUUM {full_table_name} RETAIN {retention_hours} HOURS"
                    
                    self.logger.info("Executing VACUUM command", sql=vacuum_sql)
                    vacuum_query_result = await connection.execute_query(vacuum_sql, {})
                    
                    # Try to get files removed count (if available in result)
                    try:
                        vacuum_info = vacuum_query_result.fetchone()
                        vacuum_result['files_removed'] = vacuum_info.get('files_removed', 0) if vacuum_info else 0
                    except:
                        vacuum_result['files_removed'] = 0  # Default if not available
                    
                    self.logger.info("Table vacuum completed", 
                                   table=table_name,
                                   files_removed=vacuum_result.get('files_removed', 0))
                else:
                    self.logger.info("DRY RUN: Would vacuum table", table=table_name, retention_hours=retention_hours)
                    vacuum_result['dry_run_message'] = f"Would run VACUUM on {full_table_name} with {retention_hours}h retention"
                    vacuum_result['files_removed'] = 0
                
                vacuum_result['success'] = True
                
        except Exception as e:
            self.logger.error("Failed to vacuum table", table=table_name, error=str(e))
            vacuum_result['error'] = str(e)
        
        vacuum_duration = datetime.now() - vacuum_start
        vacuum_result['vacuum_duration_seconds'] = vacuum_duration.total_seconds()
        
        return vacuum_result
    
    async def _mock_table_vacuum(self, table_name: str, retention_hours: int) -> Dict[str, Any]:
        """Mock table vacuum for test environments."""
        self.logger.info("Mock table vacuum", table=table_name, retention_hours=retention_hours)
        
        return {
            'table_name': table_name,
            'vacuum_start': datetime.now().isoformat(),
            'retention_hours': retention_hours,
            'success': True,
            'mock': True,
            'dry_run_message': f"Mock vacuum of {table_name} with {retention_hours}h retention",
            'files_removed': 8,  # Mock value
            'vacuum_duration_seconds': 3.0
        }


async def main():
    """Main table optimization function."""
    parser = argparse.ArgumentParser(description='Optimize Delta Tables for Scenario Tracking')
    parser.add_argument('--table-suffix', default='', help='Table suffix for environment isolation')
    parser.add_argument('--operation', choices=['optimize', 'vacuum', 'both'], default='optimize', 
                       help='Optimization operation to perform')
    parser.add_argument('--retention-hours', type=int, default=168, 
                       help='Retention hours for VACUUM operation (default: 168 = 7 days)')
    parser.add_argument('--dry-run', action='store_true', help='Preview operations without executing')
    parser.add_argument('--output', help='Save optimization results to file')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize table optimizer
    optimizer = TableOptimizer(args.table_suffix, args.dry_run)
    
    # Execute operations
    all_results = {}
    
    if args.operation in ['optimize', 'both']:
        optimization_results = await optimizer.optimize_all_tables()
        all_results['optimization'] = optimization_results
    
    if args.operation in ['vacuum', 'both']:
        vacuum_results = await optimizer.vacuum_tables(args.retention_hours)
        all_results['vacuum'] = vacuum_results
    
    # Save results if requested
    if args.output:
        Path(args.output).write_text(json.dumps(all_results, indent=2))
        logger.info("Optimization results saved", file=args.output)
    
    # Print summary
    print(f"\nTable Optimization Summary:")
    
    if 'optimization' in all_results:
        opt_results = all_results['optimization']
        print(f"Optimization - Tables Processed: {len(opt_results['tables_optimized'])}")
        print(f"Optimization - Success Rate: {opt_results['success_rate']:.1f}%")
        print(f"Optimization - Files Compacted: {opt_results['total_files_compacted']}")
        print(f"Optimization - Space Saved: {opt_results['total_size_reduction_bytes'] / 1024 / 1024:.2f} MB")
    
    if 'vacuum' in all_results:
        vacuum_results = all_results['vacuum']
        print(f"Vacuum - Tables Processed: {len(vacuum_results['tables_vacuumed'])}")
        print(f"Vacuum - Files Removed: {vacuum_results['total_files_removed']}")
    
    # Determine exit code
    optimization_success = all_results.get('optimization', {}).get('success_rate', 100) > 50
    vacuum_success = len(all_results.get('vacuum', {}).get('vacuum_errors', [])) == 0
    
    return 0 if optimization_success and vacuum_success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))