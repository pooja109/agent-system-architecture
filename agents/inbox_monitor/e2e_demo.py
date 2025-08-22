#!/usr/bin/env python3
"""
E2E Demo Runner - Enhanced with Professional CLI
"""

import asyncio
import sys
import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv

# Load .env from the project root (two levels up from current directory)
current_dir = Path(__file__).parent
project_root = current_dir.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    print(f"✅ Loaded environment from {env_file}")
else:
    print(f"⚠️  Environment file not found at {env_file}")

# Add current directory to path
sys.path.insert(0, str(current_dir))

from e2e_demo.cli_parser import CLIParser
from e2e_demo.config import ConfigManager
from e2e_demo.output_manager import OutputManager
from e2e_demo.runner import DemoRunner


def verify_databricks_configuration():
    """Verify that Databricks configuration is properly set for scenario tracking."""
    print("\n" + "="*80)
    print("🔍 DATABRICKS CONFIGURATION VERIFICATION")
    print("="*80)
    
    # Check required environment variables
    required_vars = {
        'DATABRICKS_CATALOG': os.getenv('DATABRICKS_CATALOG'),
        'DATABRICKS_SCHEMA': os.getenv('DATABRICKS_SCHEMA'),
        'DATABRICKS_TABLE_SUFFIX': os.getenv('DATABRICKS_TABLE_SUFFIX'),
        'DATABRICKS_SERVER_HOSTNAME': os.getenv('DATABRICKS_SERVER_HOSTNAME'),
        'DATABRICKS_HTTP_PATH': os.getenv('DATABRICKS_HTTP_PATH')
    }
    
    all_set = True
    for var_name, value in required_vars.items():
        if value:
            print(f"✅ {var_name}: {value}")
        else:
            print(f"❌ {var_name}: NOT SET")
            all_set = False
    
    # Calculate expected table name
    catalog = required_vars['DATABRICKS_CATALOG'] or 'unknown'
    schema = required_vars['DATABRICKS_SCHEMA'] or 'unknown'
    suffix = required_vars['DATABRICKS_TABLE_SUFFIX'] or ''
    expected_table = f"{catalog}.{schema}.inbox_monitor_scenario_processing{suffix}"
    
    print(f"\n📊 Expected table name: {expected_table}")
    
    if not all_set:
        print("\n⚠️  WARNING: Some Databricks configuration is missing!")
        print("   The demo may not be able to save data to the Databricks table.")
    else:
        print("\n✅ Databricks configuration appears complete!")
    
    print("="*80)
    return all_set


async def verify_scenario_tracking_data(results):
    """Verify that scenario tracking data was properly saved to Databricks."""
    print("\n" + "="*80)
    print("📊 SCENARIO TRACKING VERIFICATION")
    print("="*80)
    
    try:
        # Import scenario tracking components
        from services.scenario_tracking_integration import get_tracking_integration
        from config.settings import get_settings
        
        # Get the tracking integration instance
        tracking_integration = await get_tracking_integration()
        
        # Check health status
        health_status = await tracking_integration.get_integration_health()
        print(f"🔍 Tracking Integration Status: {health_status.get('status', 'unknown')}")
        print(f"📈 Initialized: {health_status.get('initialized', False)}")
        print(f"⚙️  Configuration Enabled: {health_status.get('config_enabled', False)}")
        
        if health_status.get('tracking_client'):
            client_status = health_status['tracking_client'].get('status', 'unknown')
            print(f"🔗 Tracking Client Status: {client_status}")
            
            # Get metrics if available
            metrics = health_status['tracking_client'].get('metrics', {})
            if metrics:
                print(f"📊 Total Operations: {metrics.get('total_operations', 0)}")
                print(f"✅ Successful Operations: {metrics.get('successful_operations', 0)}")
                print(f"❌ Failed Operations: {metrics.get('failed_operations', 0)}")
        
        # Get settings to show table name
        settings = await get_settings(test_mode=False)
        catalog = settings.databricks_oauth.catalog
        schema = settings.databricks_oauth.schema_name
        suffix = settings.databricks_oauth.table_suffix
        table_name = f"{catalog}.{schema}.inbox_monitor_scenario_processing{suffix}"
        print(f"📋 Target Table: {table_name}")
        
        # Count successful scenarios
        successful_scenarios = len([r for r in results if r.success])
        print(f"🎯 Scenarios Executed Successfully: {successful_scenarios}")
        
        if successful_scenarios > 0 and health_status.get('status') == 'healthy':
            print("\n✅ SCENARIO TRACKING VERIFICATION PASSED")
            print(f"   → {successful_scenarios} scenarios were processed successfully")
            print(f"   → Data should be saved to table: {table_name}")
            print("   → Tracking integration is healthy and operational")
        else:
            print("\n⚠️  SCENARIO TRACKING VERIFICATION WARNING")
            if successful_scenarios == 0:
                print("   → No scenarios were executed successfully")
            if health_status.get('status') != 'healthy':
                print(f"   → Tracking integration status: {health_status.get('status')}")
                print("   → Data may not have been saved to Databricks")
        
    except Exception as e:
        print(f"\n❌ SCENARIO TRACKING VERIFICATION FAILED")
        print(f"   Error: {e}")
        print("   → Unable to verify if data was saved to Databricks table")
    
    print("="*80)


def confirm_live_mode() -> bool:
    """Confirm user wants to run with real services."""
    import os
    
    # Check for environment variable bypass
    if os.getenv('BYPASS_SAFETY_CONFIRMATION', '').lower() in ['true', '1', 'yes']:
        print("\n" + "="*60)
        print("⚠️  LIVE MODE - REAL SERVICES (Auto-confirmed via BYPASS_SAFETY_CONFIRMATION)")
        print("="*60)
        return True
    
    print("\n" + "="*60)
    print("⚠️  LIVE MODE - REAL SERVICES")
    print("="*60)
    print("\nThis will:")
    print("• Send real emails via Azure Communication Services")
    print("• Create real Salesforce cases")
    print("• Use real Azure AI tokens")
    print("\nAre you sure you want to continue? (yes/no): ", end='')
    
    response = input().strip().lower()
    return response in ['yes', 'y']


async def main():
    """Enhanced main entry point with robust error handling."""
    runner = None
    output_manager = None
    
    try:
        # Parse arguments
        cli_parser = CLIParser()
        args = cli_parser.parse_args()
        
        # Handle configuration
        config_manager = ConfigManager()
        
        # Load config file if specified
        if args.config:
            config_manager.load_from_file(args.config)
        
        # Apply CLI overrides
        config_manager.load_from_cli(args)
        
        # Get final configuration
        config = config_manager.get_final_config()
        
        # Verify Databricks configuration before proceeding
        verify_databricks_configuration()
        
        # Handle save config
        if hasattr(args, 'save_config') and args.save_config:
            config_manager.save_to_file(args.save_config, config)
            print(f"Configuration saved to {args.save_config}")
            return 0
        
        # Handle dry run
        if config.dry_run:
            print("DRY RUN - Configuration Preview:")
            print("-" * 40)
            for key, value in config.to_dict().items():
                print(f"{key:20}: {value}")
            print("-" * 40)
            print("No scenarios will be executed.")
            return 0
        
        # Handle live mode confirmation
        if not config.mock_mode and not config.skip_confirmation:
            if not confirm_live_mode():
                print("Aborted. Use mock mode (default) for safe demos.")
                return 1
        
        # Use output manager for all formats - unified output system
        output_manager = OutputManager(config)
        
        try:
            # Write header
            output_manager.write_header()
            
            # Create and run demo
            runner = DemoRunner(config)
            results = await runner.run()
            
            # Dashboard format handles its own output during run()
            if config.output_format != 'dashboard':
                # Display results for other formats
                for result in results:
                    output_manager.write(
                        output_manager.format_scenario_result(result)
                    )
                
                # Write summary with email count
                email_count = runner._validate_email_count(results)
                output_manager.write_summary(results, email_count)
            else:
                # For dashboard format, just validate email count for logging
                email_count = runner._validate_email_count(results)
            
            # Phase 4: Handle export options
            if hasattr(args, 'export') and args.export:
                try:
                    exported_files = runner.export_results(results, args.export)
                    if exported_files:
                        print(f"\n📁 Results exported:")
                        for format_type, filepath in exported_files.items():
                            print(f"  • {format_type.upper()}: {filepath}")
                except Exception as e:
                    print(f"\n⚠️ Export failed: {e}")
            
            # Phase 4: Generate executive summary if requested
            if hasattr(args, 'executive_summary') and args.executive_summary and runner.export_system:
                try:
                    summary = runner.export_system.generate_executive_summary(results)
                    print(f"\n📊 Executive Summary:\n{summary}")
                except Exception as e:
                    print(f"\n⚠️ Executive summary failed: {e}")
            
            # Phase 4: Generate performance report if requested
            if hasattr(args, 'performance_report') and args.performance_report:
                try:
                    from e2e_demo.performance import get_performance_summary
                    perf_report = get_performance_summary()
                    print(f"\n⚡ Performance Report:")
                    print(f"  • Cache hit rate: {perf_report.get('cache_stats', {}).get('hit_rate', 0):.1f}%")
                    print(f"  • Total operations: {perf_report.get('cache_stats', {}).get('total_requests', 0)}")
                    for rec in perf_report.get('recommendations', []):
                        print(f"  • {rec}")
                except Exception as e:
                    print(f"\n⚠️ Performance report failed: {e}")
            
            # Verify scenario tracking data was saved if in live mode
            if not config.mock_mode:
                await verify_scenario_tracking_data(results)
            
            # Success
            return 0
            
        except KeyboardInterrupt:
            try:
                output_manager.write("\n\n❌ Demo interrupted by user")
            except (BrokenPipeError, IOError):
                # Handle pipe breaks silently during interruption
                pass
            return 130
            
        except Exception as e:
            try:
                output_manager.write(f"\n❌ Demo failed: {e}")
                if config.detail_level.value == 'verbose':
                    import traceback
                    output_manager.write(traceback.format_exc())
            except (BrokenPipeError, IOError):
                # Handle pipe breaks during error reporting
                # Try stderr as fallback
                try:
                    print(f"❌ Demo failed: {e}", file=sys.stderr)
                except (BrokenPipeError, IOError):
                    # If stderr also fails, exit silently
                    pass
            return 1
            
    except (BrokenPipeError, IOError):
        # Handle pipe breaks during initialization
        return 1
        
    except KeyboardInterrupt:
        # Handle interruption during initialization
        return 130
        
    except Exception as e:
        # Handle any other initialization errors
        try:
            print(f"❌ Initialization failed: {e}", file=sys.stderr)
        except (BrokenPipeError, IOError):
            # Silent failure if stderr also unavailable
            pass
        return 1
        
    finally:
        # Ensure cleanup happens even with errors
        try:
            if output_manager:
                output_manager.close()
        except (BrokenPipeError, IOError, AttributeError):
            # Ignore cleanup errors
            pass
            
        try:
            if runner and hasattr(runner, 'cleanup'):
                await runner.cleanup()
        except (BrokenPipeError, IOError, AttributeError, Exception):
            # Ignore cleanup errors
            pass


if __name__ == "__main__":
    # Suppress all verbose logging
    import logging
    logging.getLogger().setLevel(logging.CRITICAL)
    
    # Run the demo
    exit_code = asyncio.run(main())
    sys.exit(exit_code)