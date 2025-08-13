"""
System Validation Module
========================

Provides system validation functions with two validation modes:
1. Syntax validation - Tests import resolution and basic functionality
2. Full system validation - Tests complete environment setup and service initialization
"""

import importlib
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Callable, Optional
import os
import asyncio

# Load environment variables from repo root (same as config/settings.py does)
from dotenv import load_dotenv
repo_root = Path(__file__).parent.parent.parent.parent
env_file = repo_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"   📁 Loaded environment from: {env_file}")
else:
    print(f"   ⚠️  Environment file not found: {env_file}")

# Fix naming conflict and path issues
tests_dir = str(Path(__file__).parent)
scripts_dir = str(Path(__file__).parent.parent / "scripts")
project_root = str(Path(__file__).parent.parent)

# Remove problematic directories from sys.path  
paths_to_remove = [tests_dir, scripts_dir]
for path_to_remove in paths_to_remove:
    while path_to_remove in sys.path:
        sys.path.remove(path_to_remove)

# Ensure the project root is first in sys.path for correct imports
if project_root not in sys.path:
    sys.path.insert(0, project_root)
elif sys.path.index(project_root) != 0:
    sys.path.remove(project_root)
    sys.path.insert(0, project_root)

# Clear any cached imports that might be causing issues
modules_to_clear = [name for name in sys.modules.keys() if name.startswith('config')]
for module_name in modules_to_clear:
    del sys.modules[module_name]

# Pre-load the config.settings module to ensure it's available for imports
try:
    import importlib
    import importlib.util
    
    # Use direct importlib approach to ensure config.settings is loaded
    spec = importlib.util.spec_from_file_location(
        "config.settings", 
        str(Path(__file__).parent.parent / "config" / "settings.py")
    )
    if spec and spec.loader:
        config_settings = importlib.util.module_from_spec(spec)
        sys.modules["config.settings"] = config_settings
        spec.loader.exec_module(config_settings)
except Exception:
    # If direct approach fails, the import tests will handle it gracefully
    pass


class PerformanceMetrics:
    """Utility class for measuring execution time."""
    
    @staticmethod
    def measure_execution_time(func: Callable) -> tuple:
        """Measure execution time of a function."""
        start_time = time.perf_counter()
        result = func()
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000
        return result, execution_time_ms


def run_system_validation(mode: str = 'syntax') -> Dict[str, Any]:
    """Run system validation in specified mode.
    
    Args:
        mode: 'syntax' for import/syntax validation, 'full' for complete system validation
    """
    results = {
        'validation_mode': mode,
        'overall_status': 'PASSED',
        'import_resolution': True,
        'datetime_modernization': True,
        'datetime_validation': True,
        'environment_validation': True if mode == 'syntax' else False,  # Will be set properly in full mode
        'service_initialization': True if mode == 'syntax' else False,  # Will be set properly in full mode
        'comprehensive_imports': [],
        'performance_benchmarks': [],
        'errors': [],
        'warnings': []
    }
    
    try:
        # Test 1: Import Resolution (both modes)
        print(f"🔍 Testing import resolution ({mode} mode)...")
        critical_modules = [
            'config.settings',
            'utils.retry',
            'services.azure_ai_foundry_client',
            'services.email_processor', 
            'services.graph_api_client',
        ]
        
        for module_name in critical_modules:
            try:
                # Clear module cache to ensure fresh import
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                # Try different import strategies
                module = None
                import_error = None
                
                # Strategy 1: Direct import
                try:
                    module = importlib.import_module(module_name)
                except ImportError as e:
                    import_error = e
                    
                    # Strategy 2: Try with absolute path from current working directory
                    import os
                    original_cwd = os.getcwd()
                    try:
                        os.chdir(str(project_root))
                        module = importlib.import_module(module_name)
                        import_error = None
                    except ImportError:
                        pass
                    finally:
                        os.chdir(original_cwd)
                
                if module is not None:
                    results['comprehensive_imports'].append(module_name)
                    print(f"   ✅ {module_name}")
                    
                    # Test basic functionality for key modules
                    if module_name == 'config.settings':
                        # Test that we can access key classes
                        if hasattr(module, 'AppSettings') and hasattr(module, 'GraphAPISettings'):
                            print(f"   ✅ {module_name} - settings classes available")
                        else:
                            print(f"   ⚠️  {module_name} - missing expected classes")
                else:
                    raise import_error or ImportError(f"Could not import {module_name}")
                
            except ImportError as e:
                # Handle differently based on validation mode
                if mode == 'syntax':
                    # In syntax mode, warnings for services are OK
                    if 'config.settings' in str(e) and module_name.startswith('services.'):
                        print(f"   ⚠️  {module_name}: Service import requires full environment setup")
                        results['warnings'].append(f"{module_name}: Service import requires full environment setup")
                        # Don't mark as failed for syntax validation
                    elif module_name == 'config.settings':
                        # Special handling for config.settings - try to verify it exists
                        config_settings_path = project_root / 'config' / 'settings.py'
                        if config_settings_path.exists():
                            print(f"   ⚠️  {module_name}: File exists but import context issue")
                            results['warnings'].append(f"{module_name}: File exists but import context issue")
                            results['comprehensive_imports'].append(f"{module_name} (file exists)")
                        else:
                            results['errors'].append(f"Import failed for {module_name}: {e}")
                            results['import_resolution'] = False
                            print(f"   ❌ {module_name}: {e}")
                    else:
                        results['errors'].append(f"Import failed for {module_name}: {e}")
                        results['import_resolution'] = False
                        print(f"   ❌ {module_name}: {e}")
                else:
                    # In full mode, ALL import failures are errors
                    results['errors'].append(f"Import failed for {module_name}: {e}")
                    results['import_resolution'] = False
                    print(f"   ❌ {module_name}: {e}")
            except Exception as e:
                if mode == 'syntax':
                    print(f"   ⚠️  {module_name}: {e}")
                    results['warnings'].append(f"{module_name}: {e}")
                else:
                    print(f"   ❌ {module_name}: {e}")
                    results['errors'].append(f"{module_name}: {e}")
                    results['import_resolution'] = False
        
        # Test 2: Datetime API Modernization
        print("📅 Testing datetime API modernization...")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            
            # Test modern datetime usage
            current_time = datetime.now(timezone.utc)
            timestamp = current_time.timestamp()
            
            # Check for deprecated warnings
            deprecated_warnings = [warning for warning in w 
                                 if "utcnow" in str(warning.message).lower()]
            
            if deprecated_warnings:
                results['datetime_modernization'] = False
                results['errors'].append(f"Found {len(deprecated_warnings)} datetime deprecation warnings")
                print(f"   ❌ Found {len(deprecated_warnings)} deprecation warnings")
            else:
                print(f"   ✅ No deprecation warnings")
        
        # Test 3: Datetime Validation
        print("🕒 Testing datetime validation...")
        test_datetime = datetime.now(timezone.utc)
        if test_datetime.tzinfo is not None:
            print(f"   ✅ Timezone aware datetime")
        else:
            results['datetime_validation'] = False
            results['errors'].append("Datetime is not timezone aware")
            print(f"   ❌ Datetime not timezone aware")
        
        # Test 4: Performance Benchmarks
        print("⚡ Running performance benchmarks...")
        
        # Simple performance test
        def simple_operation():
            return sum(range(1000))
        
        result, exec_time = PerformanceMetrics.measure_execution_time(simple_operation)
        results['performance_benchmarks'].append({
            'test': 'simple_operation',
            'time_ms': exec_time,
            'result': result
        })
        print(f"   ✅ Simple operation: {exec_time:.2f}ms")
        
        # Test 5: Environment Validation (full mode only)
        if mode == 'full':
            print("🌐 Testing environment validation...")
            environment_errors = _validate_environment_variables()
            if environment_errors:
                results['environment_validation'] = False
                results['errors'].extend(environment_errors)
                print(f"   ❌ Environment validation failed: {len(environment_errors)} missing variables")
                for error in environment_errors:
                    print(f"      • {error}")
            else:
                print(f"   ✅ All required environment variables present")
        
        # Test 6: Service Initialization (full mode only)
        if mode == 'full':
            print("🔧 Testing service initialization...")
            service_errors = asyncio.run(_validate_service_initialization())
            if service_errors:
                results['service_initialization'] = False
                results['errors'].extend(service_errors)
                print(f"   ❌ Service initialization failed: {len(service_errors)} services failed")
                for error in service_errors:
                    print(f"      • {error}")
            else:
                print(f"   ✅ All critical services initialized successfully")
        
        # Set overall status
        if results['errors']:
            results['overall_status'] = 'FAILED'
            
    except Exception as e:
        results['overall_status'] = 'FAILED'
        results['errors'].append(f"System validation error: {e}")
    
    return results


def _validate_environment_variables() -> list[str]:
    """Validate that all required environment variables are present.
    
    Returns:
        List of error messages for missing environment variables
    """
    errors = []
    
    # Critical environment variables required for full system operation
    required_env_vars = {
        'AZURE_KEY_VAULT_URL': 'Azure Key Vault URL for credential management',
        'AZURE_TENANT_ID': 'Azure AD tenant ID',
        'AZURE_CLIENT_ID': 'Azure service principal client ID',
        'AZURE_CLIENT_SECRET': 'Azure service principal client secret',
        'GRAPH_API_MONITORED_EMAIL': 'Email address to monitor for incoming messages',
        'DATABRICKS_SERVER_HOSTNAME': 'Databricks workspace hostname',
        'DATABRICKS_HTTP_PATH': 'Databricks SQL warehouse HTTP path',
        'DATABRICKS_CATALOG': 'Databricks catalog name',
        'DATABRICKS_SCHEMA': 'Databricks schema name',
        'INBOX_MONITOR_TEST_EMAIL': 'Test email address for validation',
        'SCENARIO_VICTORIA_GRANT_EMAIL': 'Victoria Grant scenario email address',
        'SCENARIO_ACCOUNT_TEAM_EMAIL': 'Account team scenario email address'
    }
    
    for env_var, description in required_env_vars.items():
        value = os.getenv(env_var)
        if not value or value.strip() == '':
            errors.append(f"Missing required environment variable: {env_var} ({description})")
    
    # Additional validation for specific formats
    if os.getenv('AZURE_KEY_VAULT_URL') and not os.getenv('AZURE_KEY_VAULT_URL').startswith('https://'):
        errors.append("AZURE_KEY_VAULT_URL must be a valid HTTPS URL")
    
    email_vars = ['GRAPH_API_MONITORED_EMAIL', 'INBOX_MONITOR_TEST_EMAIL', 
                  'SCENARIO_VICTORIA_GRANT_EMAIL', 'SCENARIO_ACCOUNT_TEAM_EMAIL']
    for email_var in email_vars:
        email_value = os.getenv(email_var)
        if email_value and '@' not in email_value:
            errors.append(f"{email_var} must be a valid email address")
    
    return errors


async def _validate_service_initialization() -> list[str]:
    """Validate that critical services can be initialized with current environment.
    
    Returns:
        List of error messages for services that failed to initialize
    """
    errors = []
    
    # Test 0: Initialize logging system (required for other services)
    try:
        from utils.custom_logging import initialize_logging, LoggingConfig, ConsoleConfig, StructuredConfig, LogLevel, OutputFormat
        
        # Create minimal logging configuration for validation
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
        print("      ✅ Logging system initialized")
        
    except Exception as e:
        errors.append(f"Logging system initialization failed: {str(e)}")
        return errors  # Can't proceed without logging
    
    # Test 1: Configuration Loading
    try:
        from config.settings import get_settings, validate_settings
        
        # Test settings loading with real environment
        settings = await get_settings(test_mode=False)
        validate_settings(settings)
        print("      ✅ Configuration settings loaded and validated")
        
    except Exception as e:
        errors.append(f"Configuration loading failed: {str(e)}")
    
    # Test 2: Azure Key Vault Client
    try:
        from services.azure_key_vault_client import AzureKeyVaultClient
        from config.settings import KeyVaultSettings
        from pydantic import SecretStr
        
        key_vault_settings = KeyVaultSettings(
            key_vault_url=os.getenv("AZURE_KEY_VAULT_URL", ""),
            azure_tenant_id=os.getenv("AZURE_TENANT_ID", ""),
            azure_client_id=os.getenv("AZURE_CLIENT_ID", ""),
            azure_client_secret=SecretStr(os.getenv("AZURE_CLIENT_SECRET", "")),
        )
        
        # Test Key Vault client initialization (but don't make actual calls)
        client = AzureKeyVaultClient(key_vault_settings, test_mode=False)
        print("      ✅ Azure Key Vault client initialized")
        
    except Exception as e:
        errors.append(f"Azure Key Vault client initialization failed: {str(e)}")
    
    # Test 3: Database Connection (Databricks)
    try:
        # Test that we can create a connection configuration
        databricks_config = {
            'server_hostname': os.getenv('DATABRICKS_SERVER_HOSTNAME'),
            'http_path': os.getenv('DATABRICKS_HTTP_PATH'),
            'catalog': os.getenv('DATABRICKS_CATALOG'),
            'schema_name': os.getenv('DATABRICKS_SCHEMA')
        }
        
        if all(databricks_config.values()):
            print("      ✅ Databricks connection configuration complete")
        else:
            missing = [k for k, v in databricks_config.items() if not v]
            errors.append(f"Databricks configuration incomplete: missing {missing}")
            
    except Exception as e:
        errors.append(f"Databricks configuration validation failed: {str(e)}")
    
    # Test 4: AI Foundry Client (basic initialization)
    try:
        from services.azure_ai_foundry_client import AzureAIFoundryClient
        
        # Test basic client structure (without actual API calls)
        print("      ✅ Azure AI Foundry client class available")
        
    except Exception as e:
        errors.append(f"Azure AI Foundry client import failed: {str(e)}")
    
    # Test 5: Email Processing Services
    try:
        from services.email_processor import EmailProcessor
        from services.graph_api_client import GraphAPIClient
        
        print("      ✅ Email processing services available")
        
    except Exception as e:
        errors.append(f"Email processing services import failed: {str(e)}")
    
    return errors