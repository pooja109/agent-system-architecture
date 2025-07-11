#!/usr/bin/env python3
"""
Email Processor Runner
======================

Simple script to run the email processor in different modes.
This provides a convenient way to start the email processor without using the full main.py interface.

Usage:
    python run_email_processor.py                    # Run continuously
    python run_email_processor.py --once             # Run once and exit
    python run_email_processor.py --test <email>     # Send test email
"""

import asyncio
import argparse
import logging
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_clients.email_processor import EmailProcessor

def setup_basic_logging():
    """Set up basic logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )

async def main():
    """Main entry point for the email processor runner."""
    parser = argparse.ArgumentParser(
        description="Email Processor Runner - Simple interface for email processing",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--once', 
                       action='store_true',
                       help='Run email processing once and exit')
    
    parser.add_argument('--test', 
                       metavar='EMAIL',
                       help='Send a test email to the specified address')
    
    parser.add_argument('--verbose', '-v',
                       action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set up logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    setup_basic_logging()
    logger = logging.getLogger(__name__)
    
    # Create processor
    processor = EmailProcessor()
    
    try:
        # Initialize processor
        logger.info("Initializing email processor...")
        if not await processor.initialize():
            logger.error("Failed to initialize email processor")
            return 1
        
        logger.info("Email processor initialized successfully")
        
        # Run based on arguments
        if args.test:
            # Send test email
            logger.info(f"Sending test email to: {args.test}")
            result = await processor.test_system(args.test)
            
            if result.get('success', False):
                print(f"✅ Test email sent successfully to {args.test}")
                if 'message_id' in result:
                    print(f"📨 Message ID: {result['message_id']}")
                return 0
            else:
                print(f"❌ Test email failed: {result.get('error', 'Unknown error')}")
                return 1
        
        elif args.once:
            # Run once
            logger.info("Running email processing once...")
            results = await processor.process_emails_once()
            
            if results.get('success', False):
                processed = results.get('processed', 0)
                sent = results.get('sent', 0)
                failed = results.get('failed', 0)
                
                print(f"✅ Email processing completed:")
                print(f"   📊 Processed: {processed} records")
                print(f"   📧 Sent: {sent} emails")
                print(f"   ❌ Failed: {failed} emails")
                
                return 0 if failed == 0 else 1
            else:
                print(f"❌ Email processing failed: {results.get('error', 'Unknown error')}")
                return 1
        
        else:
            # Run continuously
            logger.info("Starting continuous email processor...")
            print("🚀 Email processor started")
            print(f"📧 Processing emails every {processor.settings.processing.interval_minutes} minutes")
            print("🛑 Press Ctrl+C to stop")
            
            processor.run_continuous()
            
            print("✅ Email processor stopped")
            return 0
    
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        print("\n🛑 Email processor stopped by user")
        return 0
    
    except Exception as e:
        logger.error(f"Email processor failed: {e}")
        print(f"❌ Error: {e}")
        return 1
    
    finally:
        # Cleanup
        try:
            await processor.cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)