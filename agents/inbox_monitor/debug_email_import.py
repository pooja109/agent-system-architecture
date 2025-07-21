#!/usr/bin/env python3
"""
Debug Email Service Import
==========================

Script to debug the email service import issue by testing the exact import path
and dependencies that the scenario processor is trying to use.
"""

import os
import sys
import traceback


def debug_email_import():
    """Debug the email service import step by step."""

    print("🔍 Debug Email Service Import")
    print("=" * 60)

    # Calculate paths exactly like scenario processor does
    current_dir = os.path.dirname(os.path.abspath(__file__))  # /inbox_monitor/
    agents_dir = os.path.dirname(current_dir)  # /agents/
    email_dir = os.path.join(agents_dir, "email")  # /agents/email/

    print(f"Current directory: {current_dir}")
    print(f"Agents directory: {agents_dir}")
    print(f"Email directory: {email_dir}")
    print(f"Email directory exists: {os.path.exists(email_dir)}")

    if os.path.exists(email_dir):
        print("Email directory contents:")
        for item in os.listdir(email_dir):
            item_path = os.path.join(email_dir, item)
            if os.path.isdir(item_path):
                print(f"  📁 {item}/")
            else:
                print(f"  📄 {item}")

    # Check services subdirectory
    services_dir = os.path.join(email_dir, "services")
    print(f"\nServices directory: {services_dir}")
    print(f"Services directory exists: {os.path.exists(services_dir)}")

    if os.path.exists(services_dir):
        print("Services directory contents:")
        for item in os.listdir(services_dir):
            print(f"  📄 {item}")

    # Check if email_service.py exists
    email_service_path = os.path.join(services_dir, "email_service.py")
    print(f"\nEmail service file: {email_service_path}")
    print(f"Email service file exists: {os.path.exists(email_service_path)}")

    # Try adding to Python path
    print("\nCurrent Python path (first 5 entries):")
    for i, path in enumerate(sys.path[:5]):
        print(f"  {i}: {path}")

    print("\nAdding email directory to Python path...")
    if email_dir not in sys.path:
        sys.path.insert(0, email_dir)
        print(f"✅ Added {email_dir} to sys.path")
    else:
        print(f"⚠️  {email_dir} already in sys.path")

    # Try importing step by step
    print("\n📦 Testing imports...")

    # Test 1: Import services module
    try:
        import services

        print("✅ Successfully imported 'services' module")
        print(f"   services.__file__ = {getattr(services, '__file__', 'No __file__ attribute')}")
    except ImportError as e:
        print(f"❌ Failed to import 'services' module: {e}")
        traceback.print_exc()

    # Test 2: Import services.email_service directly
    try:
        from services import email_service

        print("✅ Successfully imported 'services.email_service' module")
        print(f"   email_service.__file__ = {email_service.__file__}")
    except ImportError as e:
        print(f"❌ Failed to import 'services.email_service': {e}")
        traceback.print_exc()

    # Test 3: Import EmailService class
    try:
        from services.email_service import EmailService

        print("✅ Successfully imported 'EmailService' class")
        print(f"   EmailService = {EmailService}")
    except ImportError as e:
        print(f"❌ Failed to import 'EmailService' class: {e}")
        traceback.print_exc()

    # Test 4: Import config.settings
    try:
        from config.settings import get_settings

        print("✅ Successfully imported 'get_settings' from config.settings")
        print(f"   get_settings = {get_settings}")
    except ImportError as e:
        print(f"❌ Failed to import from config.settings: {e}")
        traceback.print_exc()

    # Test 5: Check what modules are available in services
    try:
        import services

        if hasattr(services, "__path__"):
            print(f"\nServices module path: {services.__path__}")

        services_modules = []
        services_path = os.path.join(email_dir, "services")
        if os.path.exists(services_path):
            for file in os.listdir(services_path):
                if file.endswith(".py") and not file.startswith("__"):
                    module_name = file[:-3]  # Remove .py
                    services_modules.append(module_name)

            print(f"Available modules in services: {services_modules}")
    except Exception as e:
        print(f"❌ Error checking services modules: {e}")

    print("\n" + "=" * 60)
    print("✅ Debug completed")


if __name__ == "__main__":
    debug_email_import()
