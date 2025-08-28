#!/usr/bin/env python3
"""
Example Usage of Inbox Monitor
==============================

This script demonstrates how to use the inbox monitor service.
"""

import os

# Example 1: Check configuration status
print("Example 1: Checking system status")
print("-" * 40)
os.system("python main.py status")

print("\n\nExample 2: Test Graph API connection")
print("-" * 40)
print("python main.py test")
print("(This will fail without proper Graph API credentials)")

print("\n\nExample 3: Check inbox once")
print("-" * 40)
print("python main.py check")
print("(This will fail without proper Graph API credentials)")

print("\n\nExample 4: Run continuous monitor")
print("-" * 40)
print("python main.py run")
print("(This will start the continuous monitoring service)")

print("\n\nEnvironment Variables Required:")
print("-" * 40)
print(
    """
GRAPH_API_TENANT_ID=your-tenant-id
GRAPH_API_CLIENT_ID=your-app-client-id
GRAPH_API_CLIENT_SECRET=your-app-client-secret
GRAPH_API_MONITORED_EMAIL=inbox@yourdomain.com

Optional:
INBOX_MONITOR_POLLING_INTERVAL=300
INBOX_MONITOR_BATCH_SIZE=10
INBOX_MONITOR_DRY_RUN=false
INBOX_MONITOR_OUTPUT_TYPE=file
INBOX_MONITOR_OUTPUT_DIR=./output
LOG_LEVEL=INFO
LOG_FORMAT=json
"""
)

print("\n\nSetting up Azure AD App Registration:")
print("-" * 40)
print(
    """
1. Go to Azure Portal > Azure Active Directory > App registrations
2. Create a new registration
3. Add API permissions:
   - Microsoft Graph > Application permissions > Mail.ReadWrite
   - Grant admin consent
4. Create a client secret
5. Use the Application (client) ID, Directory (tenant) ID, and client secret
"""
)

print("\n\nExample output format saved to:", "./test_output/")
