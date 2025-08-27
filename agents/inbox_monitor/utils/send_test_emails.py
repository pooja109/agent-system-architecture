#!/usr/bin/env python3
"""
Simple Test Email Sender
=========================

Quick script to send test emails for AI Agent functionality testing.
"""

import asyncio
import sys
from test_email_generator import main

if __name__ == "__main__":
    print("🧪 Starting Test Email Generator...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Test email generation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test email generation failed: {e}")
        sys.exit(1)