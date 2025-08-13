#!/usr/bin/env python3
"""
Standalone System Validation
============================

A standalone version of system validation that doesn't rely on the test runner framework.
This avoids any potential issues with test runner path setup or naming conflicts.
"""

import sys
import os
from pathlib import Path

# Ensure we're running from the correct directory
expected_dir = Path(__file__).parent
os.chdir(expected_dir)

# Load environment from repo root
from dotenv import load_dotenv
repo_root = Path(__file__).parent.parent.parent
env_file = repo_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✅ Loaded environment from: {env_file}")
else:
    print(f"❌ Environment file not found: {env_file}")
    sys.exit(1)

# Initialize logging system (required for settings validation)
try:
    from utils.custom_logging import initialize_logging, LoggingConfig, ConsoleConfig, StructuredConfig, LogLevel, OutputFormat
    
    # Create proper logging configuration
    logging_config = LoggingConfig(
        console=ConsoleConfig(
            level=LogLevel.INFO,
            format=OutputFormat.CLEAN
        ),
        structured=StructuredConfig(
            level=LogLevel.INFO
        ),
        environment="development"
    )
    initialize_logging(logging_config)
    print("✅ Logging system initialized")
    logging_ok = True
except Exception as e:
    print(f"❌ Logging initialization failed: {e}")
    logging_ok = False

# Test imports
print("\n🔍 Testing critical imports...")

try:
    import config.settings
    print("✅ config.settings imported successfully")
    
    # Test settings loading (only if logging is working)
    import asyncio
    
    async def test_settings():
        try:
            settings = await config.settings.get_settings(test_mode=False)
            config.settings.validate_settings(settings)
            print("✅ Settings loaded and validated successfully")
            return True
        except Exception as e:
            print(f"❌ Settings validation failed: {e}")
            return False
    
    if logging_ok:
        settings_ok = asyncio.run(test_settings())
    else:
        print("⚠️  Skipping settings validation due to logging initialization failure")
        settings_ok = False
    
except ImportError as e:
    print(f"❌ config.settings import failed: {e}")
    settings_ok = False

try:
    from services.azure_key_vault_client import AzureKeyVaultClient
    print("✅ AzureKeyVaultClient imported successfully")
    key_vault_ok = True
except ImportError as e:
    print(f"❌ AzureKeyVaultClient import failed: {e}")
    key_vault_ok = False

try:
    from services.azure_ai_foundry_client import AzureAIFoundryClient  
    print("✅ AzureAIFoundryClient imported successfully")
    ai_foundry_ok = True
except ImportError as e:
    print(f"❌ AzureAIFoundryClient import failed: {e}")
    ai_foundry_ok = False

try:
    from services.email_processor import EmailProcessor
    from services.graph_api_client import GraphAPIClient
    print("✅ Email processing services imported successfully")
    email_ok = True
except ImportError as e:
    print(f"❌ Email processing services import failed: {e}")
    email_ok = False

# Environment validation
print("\n🌐 Testing environment variables...")

required_env_vars = [
    'AZURE_KEY_VAULT_URL',
    'AZURE_TENANT_ID', 
    'AZURE_CLIENT_ID',
    'AZURE_CLIENT_SECRET',
    'GRAPH_API_MONITORED_EMAIL',
    'DATABRICKS_SERVER_HOSTNAME',
    'DATABRICKS_HTTP_PATH',
    'DATABRICKS_CATALOG',
    'DATABRICKS_SCHEMA',
    'INBOX_MONITOR_TEST_EMAIL',
    'SCENARIO_VICTORIA_GRANT_EMAIL',
    'SCENARIO_ACCOUNT_TEAM_EMAIL'
]

env_missing = []
for var in required_env_vars:
    value = os.getenv(var)
    if not value or value.strip() == '':
        env_missing.append(var)

if env_missing:
    print(f"❌ Missing environment variables: {len(env_missing)}")
    for var in env_missing:
        print(f"   • {var}")
    env_ok = False
else:
    print("✅ All required environment variables present")
    env_ok = True

# Summary
print(f"\n📊 SYSTEM VALIDATION SUMMARY")
print(f"=" * 50)

tests = {
    'Logging System': logging_ok,
    'Settings Loading': settings_ok,
    'Key Vault Client': key_vault_ok,
    'AI Foundry Client': ai_foundry_ok,
    'Email Services': email_ok,
    'Environment Variables': env_ok
}

passed = sum(tests.values())
total = len(tests)

for test_name, result in tests.items():
    status = "✅ PASS" if result else "❌ FAIL"
    print(f"{status} {test_name}")

print(f"\nOverall: {passed}/{total} tests passed")

if passed == total:
    print("🎉 ALL SYSTEM VALIDATION TESTS PASSED!")
    sys.exit(0)
else:
    print("⚠️  SYSTEM VALIDATION FAILED - Environment not ready for production")
    sys.exit(1)