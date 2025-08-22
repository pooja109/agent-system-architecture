#!/usr/bin/env python3
"""
Test Environment Configuration Isolation
=========================================

Verifies that environment configurations are properly isolated for each agent.
This script tests that both agents can load and validate their environments independently.
"""

import subprocess
import sys
from pathlib import Path


def test_inbox_monitor_env():
    """Test inbox monitor can load its environment."""
    print("Testing Inbox Monitor environment validation...")
    result = subprocess.run(
        ["python", "config/env_validator.py"],
        cwd=Path(__file__).parent / "agents/inbox_monitor",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("  ✅ Inbox Monitor validation passed")
    else:
        print("  ❌ Inbox Monitor validation failed")
        print(f"  Output: {result.stdout}")
        if result.stderr:
            print(f"  Errors: {result.stderr}")
    
    return result.returncode == 0


def test_email_agent_env():
    """Test email agent can load its environment."""
    print("Testing Email Agent environment validation...")
    result = subprocess.run(
        ["python", "config/env_validator.py"],
        cwd=Path(__file__).parent / "agents/email",
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("  ✅ Email Agent validation passed")
    else:
        print("  ❌ Email Agent validation failed")
        print(f"  Output: {result.stdout}")
        if result.stderr:
            print(f"  Errors: {result.stderr}")
    
    return result.returncode == 0


def test_environment_isolation():
    """Test that environments are properly isolated."""
    print("Testing environment isolation...")
    
    # Check that each agent has its own .env.sample
    inbox_env = Path(__file__).parent / "agents/inbox_monitor/.env.sample"
    email_env = Path(__file__).parent / "agents/email/.env.sample"
    
    if not inbox_env.exists():
        print("  ❌ Inbox Monitor .env.sample missing")
        return False
    
    if not email_env.exists():
        print("  ❌ Email Agent .env.sample missing")
        return False
    
    # Read and check for agent-specific variables
    with open(inbox_env) as f:
        inbox_content = f.read()
    
    with open(email_env) as f:
        email_content = f.read()
    
    # Check for inbox monitor specific variables
    inbox_specific = [
        "GRAPH_API_MONITORED_EMAIL",
        "INBOX_MONITOR_POLLING_INTERVAL",
        "SCENARIO_TRACKING_ENABLED",
        "PROMPT_CACHE_TTL_SECONDS"
    ]
    
    for var in inbox_specific:
        if var not in inbox_content:
            print(f"  ❌ Missing inbox monitor variable: {var}")
            return False
    
    # Check for email agent specific variables
    email_specific = [
        "PROCESSING_INTERVAL_MINUTES",
        "CONNECTION_POOL_MAX_CONNECTIONS",
        "BLOB_CONTAINER_NAME"
    ]
    
    for var in email_specific:
        if var not in email_content:
            print(f"  ❌ Missing email agent variable: {var}")
            return False
    
    print("  ✅ Environment isolation verified")
    return True


def test_validator_functionality():
    """Test validator error detection capabilities."""
    print("Testing validator error detection...")
    
    # Test with invalid environment variable
    import os
    original_value = os.environ.get("AZURE_KEY_VAULT_URL")
    
    # Set invalid value
    os.environ["AZURE_KEY_VAULT_URL"] = "invalid-url"
    
    # Import and test inbox monitor validator
    sys.path.insert(0, str(Path(__file__).parent / "agents/inbox_monitor"))
    from config.env_validator import EnvironmentValidator as InboxValidator
    
    validator = InboxValidator()
    is_valid, issues = validator.validate()
    
    # Restore original value
    if original_value:
        os.environ["AZURE_KEY_VAULT_URL"] = original_value
    else:
        del os.environ["AZURE_KEY_VAULT_URL"]
    
    # Check that error was detected
    has_error = any("AZURE_KEY_VAULT_URL" in error and "invalid-url" in error 
                   for error in issues.get("errors", []))
    
    if has_error:
        print("  ✅ Validator correctly detects invalid values")
    else:
        print("  ❌ Validator failed to detect invalid value")
        return False
    
    # Check for helpful hints
    has_hint = any("Must be format:" in error 
                  for error in issues.get("errors", []))
    
    if has_hint:
        print("  ✅ Validator provides helpful error hints")
    else:
        print("  ⚠️  Validator could provide better error hints")
    
    return True


def test_documentation():
    """Test that documentation exists and is comprehensive."""
    print("Testing documentation...")
    
    doc_path = Path(__file__).parent / "docs/ENVIRONMENT_MIGRATION.md"
    
    if not doc_path.exists():
        print("  ❌ Migration documentation missing")
        return False
    
    with open(doc_path) as f:
        content = f.read()
    
    required_sections = [
        "Quick Start",
        "Environment Variables Reference",
        "Security Considerations",
        "Kubernetes Deployment",
        "Migration Steps",
        "Troubleshooting"
    ]
    
    missing_sections = []
    for section in required_sections:
        if section not in content:
            missing_sections.append(section)
    
    if missing_sections:
        print(f"  ⚠️  Documentation missing sections: {', '.join(missing_sections)}")
        return False
    
    print("  ✅ Documentation is comprehensive")
    return True


def main():
    """Run all environment tests."""
    print("\n" + "="*60)
    print("ENVIRONMENT CONFIGURATION ISOLATION TEST SUITE")
    print("="*60 + "\n")
    
    tests = [
        ("Environment Isolation", test_environment_isolation),
        ("Inbox Monitor Validation", test_inbox_monitor_env),
        ("Email Agent Validation", test_email_agent_env),
        ("Validator Functionality", test_validator_functionality),
        ("Documentation", test_documentation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name}: ERROR - {str(e)}")
            results.append((name, False))
        print()
    
    # Print summary
    print("="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{name}: {status}")
    
    print("-"*60)
    print(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Environment configuration is properly isolated!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - Review and fix issues above")
        return 1


if __name__ == "__main__":
    sys.exit(main())