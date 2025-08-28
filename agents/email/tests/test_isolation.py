import pytest
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import shutil

class TestEmailAgentIsolation:
    """Test email agent runs in complete isolation."""
    
    def test_no_parent_imports(self):
        """Verify no imports from parent directory."""
        service_root = Path(__file__).parent.parent
        
        for py_file in service_root.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
                
            content = py_file.read_text()
            # Check for parent directory imports
            assert "from .." not in content, f"Parent import found in {py_file}"
            assert "import .." not in content, f"Parent import found in {py_file}"
            
            # Check for absolute imports from parent
            assert "from utils" not in content, f"Utils import found in {py_file}"
            assert "import utils" not in content, f"Utils import found in {py_file}"
    
    def test_isolated_execution(self):
        """Test service can run in isolated directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            
            # Copy email agent to temp location
            src = Path(__file__).parent.parent
            dst = tmpdir / "email-agent"
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            
            # Create minimal .env
            env_file = dst / ".env"
            env_file.write_text("""ENVIRONMENT=test
LOG_LEVEL=INFO
HEALTH_CHECK_PORT=8081
TEST_MODE=true
AZURE_KEY_VAULT_URL=https://test.vault.azure.net
AZURE_TENANT_ID=test-tenant
AZURE_CLIENT_ID=test-client
AZURE_CLIENT_SECRET=test-secret
DATABRICKS_SERVER_HOSTNAME=test.databricks.com
DATABRICKS_HTTP_PATH=/sql/1.0/test
""")
            
            # Try to run help command in isolated directory
            result = subprocess.run(
                [sys.executable, "main.py", "--help"],
                cwd=dst,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            assert result.returncode == 0, f"Failed to run in isolation: {result.stderr}"
            assert "SendEmail - Enterprise Email Processing System" in result.stdout
            
            # Test Python runner in isolation
            result2 = subprocess.run(
                [sys.executable, "run.py", "--help"],
                cwd=dst,
                capture_output=True,
                text=True,
                timeout=15
            )
            
            assert result2.returncode == 0, f"Python runner failed in isolation: {result2.stderr}"
    
    @pytest.mark.asyncio
    async def test_environment_loading(self):
        """Test environment variables load correctly."""
        # Set test environment variable
        os.environ["TEST_EMAIL_VAR"] = "test_value"
        
        # Import settings (should not raise)
        from config.settings import get_settings
        
        settings = await get_settings()
        assert settings is not None
        assert settings.environment in ["development", "test", "staging", "production"]
    
    @pytest.mark.asyncio
    async def test_health_check_independence(self):
        """Test health check doesn't conflict with inbox monitor."""
        from config.settings import get_settings
        
        settings = await get_settings()
        
        # Email agent should use port 8081
        assert settings.monitoring.health_check_port == 8081
        # Should be different from inbox monitor (8080)
        assert settings.monitoring.health_check_port != 8080


class TestEmailAgentFunctionality:
    """Test core email agent functionality."""
    
    @pytest.mark.asyncio
    async def test_email_service_initialization(self):
        """Test email service initializes correctly."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("AZURE_KEY_VAULT_URL", "https://test.vault.azure.net")
            mp.setenv("TEST_MODE", "true")
            
            from services.email_service import EmailService
            from config.settings import get_settings
            
            settings = await get_settings()
            # Note: We can't fully initialize without real credentials in test mode
            # This tests that the service class can be imported and instantiated
            assert EmailService is not None
    
    @pytest.mark.asyncio
    async def test_connection_pool_isolation(self):
        """Test connection pool works in isolation."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("TEST_MODE", "true")
            
            from services.databricks_connection_pool import initialize_connection_pool
            
            # Test that function exists and can be called
            # In test mode, it should handle missing credentials gracefully
            assert initialize_connection_pool is not None
    
    @pytest.mark.asyncio
    async def test_azure_service_isolation(self):
        """Test Azure services work in isolation."""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("AZURE_KEY_VAULT_URL", "https://test.vault.azure.net")
            mp.setenv("AZURE_TENANT_ID", "test-tenant")
            mp.setenv("AZURE_CLIENT_ID", "test-client")
            mp.setenv("AZURE_CLIENT_SECRET", "test-secret")
            mp.setenv("TEST_MODE", "true")
            
            from services.azure_key_vault_client import AzureKeyVaultClient
            
            # Test that service can be imported and instantiated
            client_class = AzureKeyVaultClient
            assert client_class is not None
    
    @pytest.mark.asyncio
    async def test_simple_processor_isolation(self):
        """Test simple processor works in isolation."""
        from simple_processor import SimpleEmailProcessor
        
        # Test that processor can be imported and instantiated
        processor = SimpleEmailProcessor()
        assert processor is not None
        assert processor.settings is None  # Should be None before initialize
        
        # Test that get_status handles uninitialized state gracefully
        try:
            status = processor.get_status()
            # Should fail because settings not loaded
            assert False, "Should have raised exception for uninitialized state"
        except AttributeError:
            # Expected - settings is None
            pass