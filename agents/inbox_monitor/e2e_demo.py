#!/usr/bin/env python3
"""
E2E Demo Runner - Enhanced with Professional CLI
"""

import asyncio
import sys
import os
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from e2e_demo.cli_parser import CLIParser
from e2e_demo.config import ConfigManager
from e2e_demo.output_manager import OutputManager
from e2e_demo.runner import DemoRunner


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